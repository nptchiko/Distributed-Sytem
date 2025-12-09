# A simple Python TCP server for a Distributed File System (DFS)-style application.
# Protocol: length-prefixed JSON control messages + raw binary file data for uploads/downloads.
#
# Features implemented to match the "ServerSide" C# DFS intent:
# - Multiple concurrent clients (thread-per-connection)
# - List files in server storage
# - Upload a file (client sends control msg then raw bytes streamed in chunks)
# - Download a file (server streams file bytes after control msg)
# - Delete a file
# - Basic integrity check using SHA256 (sent after upload, validated by server)
# - Notification broadcasts when files are added/removed
#
# Notes:
# - This is a headless server (no GUI). It stores files under ./storage.
# - It uses a simple JSON control protocol with a 4-byte length prefix on each control message.
# - File transfers are chunked and preceded by a control message describing the operation.
#
# Example control messages (JSON):
# {"type":"list"} -> server responds {"type":"list","payload":[{"name":"f.txt","size":1234,"sha256":"..."}]}
# {"type":"upload","payload":{"name":"f.txt","size":1234,"sha256":"..."}}
#      After server replies {"type":"ready","payload":null}, client streams exactly `size` bytes raw.
# {"type":"download","payload":{"name":"f.txt"}} -> server replies {"type":"ready","payload":{"size":1234,"sha256":"..."}} then streams file bytes.
# {"type":"delete","payload":{"name":"f.txt"}}
#
# Run: python server.py [host] [port]
# Default host=0.0.0.0 port=9000

import os
import socket
import threading
import json
import hashlib
import time
from typing import Dict, Tuple
from PIL import Image
import io

import cv2  # OpenCV cho video
import fitz # PyMuPDF cho PDF
import numpy as np
import tempfile 
from pydub import AudioSegment

HOST = "0.0.0.0"
PORT = 9002     #video
# PORT = 9001   #image
ENCODING = "utf-8"
STORAGE_DIR = os.path.join(os.getcwd(), "storage")
RECV_BUFFER = 8192

SOUND_EXTENSIONS = {"mp3", "m4p", "m4a", "flac", "ogg"}
VIDEO_EXTENSIONS = {"mp4", "mkv", "webm", "flv"}
TEXT_EXTENSIONS = {"txt", "md", "pdf"}
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
COMPRESSED_EXTENSIONS = {"7z", "rar", "zip"}

if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR, exist_ok=True)

clients_lock = threading.Lock()
clients = {}  # socket -> {"addr": (host,port), "name": optional}


def _recv_all(sock: socket.socket, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        try:
            chunk = sock.recv(n - len(data))
        except Exception:
            return b""
        if not chunk:
            return b""
        data.extend(chunk)
    return bytes(data)


def _recv_control(sock: socket.socket) -> dict:
    """Receive a 4-byte length-prefixed JSON control message. Returns dict or None on EOF."""
    length_bytes = _recv_all(sock, 4)
    if not length_bytes:
        return None
    length = int.from_bytes(length_bytes, "big")
    payload = _recv_all(sock, length)
    if not payload:
        return None
    try:
        return json.loads(payload.decode(ENCODING))
    except Exception:
        return None


def _send_control(sock: socket.socket, obj: dict):
    b = json.dumps(obj).encode(ENCODING)
    try:
        sock.sendall(len(b).to_bytes(4, "big") + b)
    except Exception:
        _remove_client(sock)


def _broadcast_system(msg: str, exclude: socket.socket = None):
    with clients_lock:
        to_remove = []
        for s in list(clients.keys()):
            if s is exclude:
                continue
            try:
                _send_control(s, {"type": "system", "payload": msg})
            except Exception:
                to_remove.append(s)
        for s in to_remove:
            _remove_client(s)


def _remove_client(sock: socket.socket):
    with clients_lock:
        info = clients.pop(sock, None)
    try:
        sock.close()
    except Exception:
        pass
    if info:
        print(f"Client disconnected: {info['addr']}")


def _list_storage():
    res = []
    for fname in os.listdir(STORAGE_DIR):
        path = os.path.join(STORAGE_DIR, fname)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            sha256 = _file_sha256(path)
            res.append({"name": fname, "size": size, "sha256": sha256})
    return res


def is_end_with(file_type, path):
    try:
        extension = path.split(".")[-1].lower()
    except IndexError:
        return False  # No extension

    if file_type == "sound":
        return extension in SOUND_EXTENSIONS
    if file_type == "video":
        return extension in VIDEO_EXTENSIONS
    if file_type == "text":
        return extension in TEXT_EXTENSIONS
    if file_type == "image":
        return extension in IMAGE_EXTENSIONS
    if file_type == "compressed":
        return extension in COMPRESSED_EXTENSIONS
    if file_type == "all":
        return True

    # Check for a specific custom extension
    return extension == file_type.lower()


def load_directory(root_path, filters):

    if not os.path.isdir(root_path):
        return {"error": "Path is not a valid directory."}

    storage_parent_dir = os.path.dirname(STORAGE_DIR)

    # The root of our directory tree
    dir_tree = {
        "name": os.path.basename(root_path),
        "path": os.path.relpath(root_path, storage_parent_dir),
        "subdirectories": [],
        "files": [],
    }

    # A map to keep track of directory objects to append children to the right parent
    dir_map = {root_path: dir_tree}

    for parent_path, subdirs, files in os.walk(root_path):
        parent_node = dir_map[parent_path]

        # Process subdirectories
        if "folder" not in filters:
            for subdir_name in subdirs:
                sub_path = os.path.join(parent_path, subdir_name)
                subdir_node = {
                    "name": subdir_name,
                    "path": os.path.relpath(sub_path, storage_parent_dir),
                    "subdirectories": [],
                    "files": [],
                }
                parent_node["subdirectories"].append(subdir_node)
                dir_map[sub_path] = subdir_node

        # Process files
        for filename in files:
            file_path = os.path.join(parent_path, filename)

            # Check if the file matches any of the filters
            if any(is_end_with(f, file_path) for f in filters):
                parent_node["files"].append({"name": filename, "path": os.path.relpath(file_path, storage_parent_dir)})

    return dir_tree


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(RECV_BUFFER)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def handle_upload(sock: socket.socket, payload: dict):
    name = payload.get("name")
    size = int(payload.get("size", 0))
    expected_sha = payload.get("sha256")
    if not name or size <= 0:
        _send_control(sock, {"type": "error", "payload": "Invalid upload parameters"})
        return

    try:
        dst_path = _safe_path(name)
    except ValueError:
        _send_control(sock, {"type": "error", "payload": "Invalid path"})
        return

    # If file exists, we overwrite (could be changed to reject)
    _send_control(sock, {"type": "ready", "payload": None})

    # Receive exactly `size` bytes and write to disk, compute sha256 while writing
    bytes_received = 0
    h = hashlib.sha256()
    try:
        with open(dst_path + ".tmp", "wb") as f:
            while bytes_received < size:
                to_read = min(RECV_BUFFER, size - bytes_received)
                chunk = sock.recv(to_read)
                if not chunk:
                    raise ConnectionError("Client disconnected during upload")
                f.write(chunk)
                h.update(chunk)
                bytes_received += len(chunk)
        actual_sha = h.hexdigest()
        if expected_sha and actual_sha != expected_sha:
            # Integrity failed
            os.remove(dst_path + ".tmp")
            _send_control(
                sock,
                {
                    "type": "error",
                    "payload": "sha_mismatch",
                },
            )
            return
        # Move tmp -> final
        os.replace(dst_path + ".tmp", dst_path)
        _send_control(
            sock,
            {"type": "upload_result", "payload": {"ok": True, "sha256": actual_sha}},
        )
        safe_name = os.path.basename(dst_path)
        print(f"Uploaded file: {safe_name} ({size} bytes) sha256={actual_sha}")
        _broadcast_system(f"file_added:{safe_name}")
    except Exception as e:
        try:
            if os.path.exists(dst_path + ".tmp"):
                os.remove(dst_path + ".tmp")
        except Exception:
            pass
        _send_control(sock, {"type": "error", "payload": str(e)})


def handle_download(sock: socket.socket, path: str):
    # The `path` is expected to be an absolute and safe path from `_safe_path()`
    if not os.path.isfile(path):
        _send_control(sock, {"type": "error", "payload": "file_not_found"})
        return

    size = os.path.getsize(path)
    sha = _file_sha256(path)
    _send_control(sock, {"type": "ready", "payload": {"size": size, "sha256": sha}})
    # Stream file bytes
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(RECV_BUFFER)
                if not chunk:
                    break
                sock.sendall(chunk)
    except Exception as e:
        print("Error while sending file:", e)
        _send_control(sock, {"type": "error", "payload": str(e)})


def _generate_thumbnail(path: str, max_size=(256, 256)) -> bytes:
    """
    Generates a thumbnail for image files. 
    Returns raw bytes of the PNG thumbnail.
    """
    try:
        # Open the file
        with Image.open(path) as img:
            # Create a copy to not modify original (and convert to RGB for safety)
            img = img.convert("RGB")
            img.thumbnail(max_size)
            
            # Save to memory buffer
            buf = io.BytesIO()
            img.save(buf, format="PNG", quality = 70)
            return buf.getvalue()
    except Exception:
        return None
    

def _get_pdf_thumbnail(path: str, num_pages=3) -> bytes:
    """
    Captures the first n pages of a PDF and stitches them into a single vertical image.
    Uses higher DPI for better quality.
    """
    try:
        doc = fitz.open(path)
        if len(doc) < 1:
            return None
            
        count = min(num_pages, len(doc))
        
        images = []
        total_height = 0
        max_width = 0

        # Use higher DPI (e.g., 150) for sharper text. 72 is too blurry.
        zoom_matrix = fitz.Matrix(2.0, 2.0) # Zoom 2x ~ 144 DPI

        for i in range(count):
            page = doc.load_page(i)
            
            # Render page to an image (pixmap) with higher resolution
            pix = page.get_pixmap(matrix=zoom_matrix, alpha=False)
            
            # Convert raw bytes to PIL Image
            img_data = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))
            
            images.append(img)
            total_height += img.height
            max_width = max(max_width, img.width)

        # Create a blank canvas
        long_image = Image.new('RGB', (max_width, total_height), (255, 255, 255))

        # Stitch images vertically
        y_offset = 0
        for img in images:
            # Center the image if it's narrower than max_width
            x_offset = (max_width - img.width) // 2
            long_image.paste(img, (x_offset, y_offset))
            y_offset += img.height

        # Optional: Resize if the result is too huge (e.g., restrict width to 1024px)
        # using LANCZOS filter for high-quality downsampling
        if max_width > 1024:
            ratio = 1024 / max_width
            new_height = int(total_height * ratio)
            long_image = long_image.resize((1024, new_height), Image.Resampling.LANCZOS)

        # Save to buffer as JPEG (lighter than PNG for photos/scans) with high quality
        buf = io.BytesIO()
        long_image.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    except Exception as e:
        print(f"Error PDF thumb: {e}")
        return None


def _generate_video_snippet(path: str, duration_sec: int = 5, target_width: int = 640) -> bytes:
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return None

        # Get original properties
        orig_fps = cap.get(cv2.CAP_PROP_FPS)
        if orig_fps <= 0: orig_fps = 24.0
        
        orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # CALCULATE NEW DIMENSIONS (Resize)
        if orig_width > target_width:
            scale_ratio = target_width / orig_width
            new_width = target_width
            new_height = int(orig_height * scale_ratio)
        else:
            new_width = orig_width
            new_height = orig_height

        target_fps = 24.0
        
        # If original is already low FPS (e.g. 10fps), keep it, don't fake frames.
        final_fps = min(orig_fps, target_fps)
        
        # Calculate frame skipping step
        max_frames_to_read = int(orig_fps * duration_sec)

        # Temp file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            temp_path = tmp_file.name

        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        out = cv2.VideoWriter(temp_path, fourcc, final_fps, (new_width, new_height))

        frames_read = 0
        frames_written = 0
        
        while frames_read < max_frames_to_read:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Smart frame dropping logic to match target FPS
            # 'frames_written' to match the time of 'frames_read'
            expected_frames = int(frames_read * (final_fps / orig_fps))
            
            if frames_written <= expected_frames:
                # Resize uses INTER_LINEAR which is faster than INTER_AREA and good for up to 640px
                resized_frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
                out.write(resized_frame)
                frames_written += 1
            
            frames_read += 1

        cap.release()
        out.release()
        
        # Read bytes
        video_bytes = None
        with open(temp_path, "rb") as f:
            video_bytes = f.read()
            
        try:
            os.remove(temp_path)
        except:
            pass
            
        return video_bytes

    except Exception as e:
        print(f"Error generating video snippet: {e}")
        return None


def _generate_audio_snippet(path: str, duration_sec: int = 5) -> bytes:
    try:
        # Load audio file (pydub handles mp3, wav, ogg, m4a, etc.)
        audio = AudioSegment.from_file(path)
        
        # pydub works in milliseconds
        duration_ms = duration_sec * 1000
        
        # Slice the audio (if original is shorter, it takes the whole thing)
        snippet = audio[:duration_ms]
        
        # Export to memory buffer as MP3
        buf = io.BytesIO()
        snippet.export(buf, format="mp3", bitrate="128k") # 128k is good for preview
        
        return buf.getvalue()
        
    except Exception as e:
        print(f"Error generating audio snippet: {e}")
        # Common error: ffmpeg not found
        if "ffmpeg" in str(e).lower():
            print("HINT: Make sure ffmpeg is installed and in your PATH.")
        return None
    

def handle_preview(sock: socket.socket, path: str):
    safe_name = os.path.basename(path)
    
    if not os.path.exists(path):
        _send_control(sock, {"type": "error", "payload": "file_not_found"})
        return
    # Check file extension to determine how to preview
    ext = os.path.splitext(safe_name)[1].lower()
    
    preview_data = None
    preview_type = "unknown"

    # STRATEGY 1: Images (Generate Thumbnail)
    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif"]:
        preview_data = _generate_thumbnail(path)
        preview_type = "image"

    elif ext in [".pdf"]:
        preview_data = _get_pdf_thumbnail(path)
        preview_type = "image" 

    elif ext in [".mp4", ".avi", ".mkv", ".mov", ".webm"]:
        print(f"Generating 4s preview for {safe_name}...")
        preview_data = _generate_video_snippet(path, duration_sec=5, target_width=640)
        preview_type = "video"
    
    elif ext in [".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"]:
        print(f"Generating 5s audio preview for {safe_name}...")
        preview_data = _generate_audio_snippet(path, duration_sec=1)
        preview_type = "audio"
    
    # STRATEGY 2: Text Files (Read first 500 bytes)
    elif ext in [".txt", ".py", ".json", ".md", ".log"]:
        try:
            with open(path, "rb") as f:
                preview_data = f.read(500) # Read only header
            preview_type = "text"
        except:
            pass
            
    # STRATEGY 3: Others (Return null or a generic icon logic)
    else:
        # For videos/PDFs, you would need complex libraries like opencv-python
        preview_type = "unsupported"

    if preview_data:
        size = len(preview_data)
        # 1. Send Ready signal
        _send_control(sock, {
            "type": "preview_ready", 
            "payload": {"type": preview_type, "size": size}
        })
        # 2. Stream the small thumbnail bytes
        sock.sendall(preview_data)
        print(f"Sent preview for {safe_name}")
    else:
        _send_control(sock, {"type": "error", "payload": "preview_unavailable"})


def handle_delete(sock: socket.socket, payload: dict):
    name = payload.get("name")
    if not name:
        _send_control(sock, {"type": "error", "payload": "Missing name for delete"})
        return
    
    # safe_name = os.path.basename(name)
    # path = os.path.join(STORAGE_DIR, safe_name)
    try:
        path = _safe_path(name)
    except ValueError:
        _send_control(sock, {"type": "error", "payload": "Invalid path"})
        return
    
    if not os.path.exists(path):
        _send_control(sock, {"type": "error", "payload": "file_not_found"})
        return
    try:
        os.remove(path)
        _send_control(sock, {"type": "delete_result", "payload": {"ok": True}})
        safe_name = os.path.basename(path)
        _broadcast_system(f"file_removed:{safe_name}")
        print(f"Deleted file: {safe_name}")
    except Exception as e:
        _send_control(sock, {"type": "error", "payload": str(e)})


def _safe_path(requested_path):

    safe_path = requested_path.lstrip('/')

    full_path = os.path.join(STORAGE_DIR, safe_path)

    real_path = os.path.realpath(full_path)

    if os.path.commonpath([real_path, STORAGE_DIR]) == STORAGE_DIR: 
        return real_path
    raise ValueError("Invalid path")


def handle_client(client_sock: socket.socket, addr: Tuple[str, int]):
    with clients_lock:
        clients[client_sock] = {"addr": addr, "connected_at": time.time()}
    print(f"New client: {addr}")
    try:
        while True:

            print(f"=========== NEW REQUEST ============")
            # data = client_sock.recv(4096)
            # jsonData = data.decode(ENCODING)
            jsonData = _recv_control(client_sock)
            if jsonData is None:
                print(f"Client {addr} disconnected properly.")
                break
            print(f"-> Json requested: {jsonData}")
            # jsonData = json.loads(jsonData)
            
            command = jsonData.get("command")
            payload = jsonData.get("payload")
            # path = jsonData.get("path")
            filters = jsonData.get("filters")

            try:
                path = jsonData.get("path")
                if path:
                    path = _safe_path(path)
                else:
                    path = STORAGE_DIR
            except ValueError as e:
                _send_control(client_sock, {"type": "error", "payload": str(e)})
                break
            
            if payload is None:
                payload = {}
            
            if path is None:
                path = STORAGE_DIR

            if filters is None:
                filters = ["all"]
            
            print(f"path requested: {path}")

            # ctrl = _recv_control(client_sock)
            # if ctrl is None:
            #     break
            # typ = ctrl.get("type")
            # payload = ctrl.get("payload")
            if command == "list":
                if not os.path.isdir(path):
                    _send_control(client_sock, {"type": "error", "payload": "file_not_found"})
                    continue

                files = load_directory(path, filters)
                _send_control(client_sock, {"type": "list", "payload": files})

            elif command == "upload":
                # payload: {"name":..., "size":..., "sha256":...}
                handle_upload(client_sock, payload or {})

            elif command == "download":
                # The 'path' variable is sanitized by _safe_path and passed directly.
                handle_download(client_sock, path)
            elif command == "preview":
                handle_preview(client_sock, path)

            elif command == "delete":
                handle_delete(client_sock, payload or {})

            elif command == "ping":
                _send_control(client_sock, {"type": "pong", "payload": None})

            else:
                _send_control(
                    client_sock, {"type": "error", "payload": "unknown_control_type"}
                )
    except ConnectionResetError:
        pass
    except Exception as e:
        print(f"Client handler error for {addr}: {e}")
        try:
            # Attempt to send a generic error response to the client
            _send_control(client_sock, {"type": "error", "payload": str(e)})
        except Exception as send_error:
            print(f"Failed to send error message to {addr}: {send_error}")
    finally:
        _remove_client(client_sock)


def start_server(host=HOST, port=PORT):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(100)
    print(f"DFS server listening on {host}:{port}, storage={STORAGE_DIR}")
    try:
        while True:
            c, a = srv.accept()
            t = threading.Thread(target=handle_client, args=(c, a), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        with clients_lock:
            for s in list(clients.keys()):
                try:
                    _send_control(
                        s, {"type": "system", "payload": "server_shutting_down"}
                    )
                except Exception:
                    pass
                try:
                    s.close()
                except Exception:
                    pass
            clients.clear()
        srv.close()


if __name__ == "__main__":
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    start_server(host, port)
