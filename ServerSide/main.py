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

HOST = "0.0.0.0"
PORT = 9000
ENCODING = "utf-8"
STORAGE_DIR = os.path.join(os.getcwd(), "storage")
RECV_BUFFER = 8192

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

    safe_name = os.path.basename(name)
    dst_path = os.path.join(STORAGE_DIR, safe_name)

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
                    "type": "upload_result",
                    "payload": {
                        "ok": False,
                        "reason": "sha_mismatch",
                        "actual_sha": actual_sha,
                    },
                },
            )
            return
        # Move tmp -> final
        os.replace(dst_path + ".tmp", dst_path)
        _send_control(
            sock,
            {"type": "upload_result", "payload": {"ok": True, "sha256": actual_sha}},
        )
        print(f"Uploaded file: {safe_name} ({size} bytes) sha256={actual_sha}")
        _broadcast_system(f"file_added:{safe_name}")
    except Exception as e:
        try:
            if os.path.exists(dst_path + ".tmp"):
                os.remove(dst_path + ".tmp")
        except Exception:
            pass
        _send_control(
            sock, {"type": "upload_result", "payload": {"ok": False, "reason": str(e)}}
        )


def handle_download(sock: socket.socket, payload: dict):
    name = payload.get("name")
    if not name:
        _send_control(sock, {"type": "error", "payload": "Missing name for download"})
        return
    safe_name = os.path.basename(name)
    path = os.path.join(STORAGE_DIR, safe_name)
    if not os.path.exists(path) or not os.path.isfile(path):
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


def handle_delete(sock: socket.socket, payload: dict):
    name = payload.get("name")
    if not name:
        _send_control(sock, {"type": "error", "payload": "Missing name for delete"})
        return
    safe_name = os.path.basename(name)
    path = os.path.join(STORAGE_DIR, safe_name)
    if not os.path.exists(path):
        _send_control(sock, {"type": "error", "payload": "file_not_found"})
        return
    try:
        os.remove(path)
        _send_control(sock, {"type": "delete_result", "payload": {"ok": True}})
        _broadcast_system(f"file_removed:{safe_name}")
        print(f"Deleted file: {safe_name}")
    except Exception as e:
        _send_control(
            sock, {"type": "delete_result", "payload": {"ok": False, "reason": str(e)}}
        )


def handle_client(client_sock: socket.socket, addr: Tuple[str, int]):
    with clients_lock:
        clients[client_sock] = {"addr": addr, "connected_at": time.time()}
    print(f"New client: {addr}")
    try:
        while True:
            data = client_sock.recv(4096)
            jsonData = data.decode(ENCODING)
            print(f"-> Json requested: {jsonData}")
            jsonData = json.loads(jsonData)

            if  jsonData is None:
                print("error")
                break
            
            command = jsonData.get("command")
            payload = jsonData.get("payload")
            path = jsonData.get("path")
            filter = jsonData.get("filter")
            
            if payload is None:
                payload = {}
            
            if path is None:
                path = STORAGE_DIR
            
            print(f"path requested: {path}")

            # ctrl = _recv_control(client_sock)
            # if ctrl is None:
            #     break
            # typ = ctrl.get("type")
            # payload = ctrl.get("payload")
            if command == "list":
                files = load_directory(path, filter)
                _send_control(client_sock, {"type": "list", "payload": files})

            elif command == "upload":
                # payload: {"name":..., "size":..., "sha256":...}
                handle_upload(client_sock, payload or {})

            elif command == "download":
                # payload: {"name":...}
                handle_download(client_sock, payload or {})

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
        print("Client handler error:", e)
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
