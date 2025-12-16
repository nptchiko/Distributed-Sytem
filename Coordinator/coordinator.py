import socket
import threading
import json
import sys
import struct
from typing import final
import yaml


HOST = "0.0.0.0"
PORT = 9000

# Server addresses
SERVER_NODE = {}
SERVER_NAME = ["image", "video", "text", "sound", "compressed"]

# format extensions
video_exts = {".mp4", ".mkv", ".webm", ".flv", ".avi"}
image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
docs_exts = {".txt", ".md", ".doc", ".pdf"}
sound_exts = {".mp3", ".m4p", ".m4a", ".flac", ".ogg"}
compressed_exts = {".7z", ".rar", ".zip"}


DEFAULT_PATH = "storage"


def load_config(filename: str = "./config.yaml"):
    with open(filename, "r") as file:
        config = yaml.safe_load(file)
    return config


class Coordinator:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.ip, self.port))
        self.sock.listen(5)

        app_config = load_config()

        print(f"[COORDINATOR] Started on {self.ip}:{self.port}")
        for name in SERVER_NAME:
            node = name + "_server"
            SERVER_NODE[name] = (app_config[node]["host"], app_config[node]["port"])
            print(f"[COORDINATOR] {name.upper()} SERVER: {SERVER_NODE[name]}")

    def _send_packet(self, sock, data_dict):

        try:
            json_bytes = json.dumps(data_dict).encode("utf-8")
            # Quang minh ghi nhé: stuct -> struct :))
            header = struct.pack("!I", len(json_bytes))
            sock.sendall(header + json_bytes)
        except Exception as e:
            print(f"[ERROR] Sending packet: {e}")

    def _recv_packet(self, sock):
        try:
            # Đọc header (4 bytes)
            len_bytes = sock.recv(4)
            if not len_bytes:
                return None
            payload_len = struct.unpack("!I", len_bytes)[0]

            # Đọc payload
            payload = b""
            while len(payload) < payload_len:
                chunk = sock.recv(payload_len - len(payload))
                if not chunk:
                    return None
                payload += chunk

            return json.loads(payload.decode("utf-8"))
        except Exception as e:
            print(f"[ERROR] Receiving packet: {e}")
            return None

    def _get_target_server_by_path(self, path: str):
        # define target server based on file extension

        if not path or "." not in path:
            return None

        ### FIX
        ### Author: chiko
        ### Description: xử lý nếu kèm theo folder

        path = path.split("/")[-1]
        ext = "." + path.split(".")[-1]

        if ext in image_exts:
            return SERVER_NODE["image"]

        elif ext in video_exts:
            return SERVER_NODE["video"]

        elif ext in docs_exts:
            return SERVER_NODE["text"]

        elif ext in sound_exts:
            return SERVER_NODE["sound"]

        elif ext in compressed_exts:
            return SERVER_NODE["compressed"]
        else:
            return None

    def forward_json_request(self, server_address, request_dict):

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect(server_address)

            self._send_packet(s, request_dict)
            # s.close()
            response = self._recv_packet(s)

            return response if response else {"type": "error", "payload": "No response"}
        except socket.timeout:
            print(f"[ERROR] Timeout connecting to {server_address}")
            return {"type": "error", "payload": "server_timeout"}
        except ConnectionRefusedError:
            print(f"[ERROR] Connection refused by {server_address}")
            return {"type": "error", "payload": "server_offline"}
        except Exception as e:
            print(f"[ERROR] Forwarding to {server_address}: {e}")
            return {"type": "error", "payload": "server_error"}

    def forward_request(self, server_address, request_dict):

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(server_address)
            self._send_packet(s, request_dict)

            # Receive response
            res = self._recv_packet(s)
            s.close()
            return res
        except Exception as e:
            print(f"Error forwarding to {server_address}: {e}")
            return {"status": "error", "message": "Server offline"}

    def handle_upload(self, sock: socket.socket, req: dict):
        payload = req["payload"]
        path = payload["name"]
        size = int(payload.get("size", 0))

        target_server = self._get_target_server_by_path(path)

        if not target_server:
            self._send_packet(
                sock, {"type": "error", "payload": "File type not supported"}
            )
            return

        try:
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv_sock.settimeout(10)
            srv_sock.connect(target_server)
            self._send_packet(srv_sock, req)

            # Forward Header
            len_bytes = srv_sock.recv(4)
            if not len_bytes:
                self._send_packet(
                    sock, {"type": "error", "payload": "server_no_response"}
                )
                srv_sock.close()
                return
            sock.sendall(len_bytes)

            # Forward JSON
            json_len = struct.unpack("!I", len_bytes)[0]
            json_data = b""
            while len(json_data) < json_len:
                chunk = srv_sock.recv(min(4096, json_len - len(json_data)))
                if not chunk:
                    break
                json_data += chunk
            sock.sendall(json_data)

            resp = json.loads(json_data.decode("utf-8"))

            if resp.get("type") == "ready":
                data = bytearray()

                chunk = sock.recv(size)
                if not chunk:
                    raise EOFError("Connection closed while reading")
                data.extend(chunk)

                data = bytes(data)
                srv_sock.sendall(data)

            # Return result
            # Forward Header
            len_bytes = srv_sock.recv(4)
            if not len_bytes:
                self._send_packet(
                    sock, {"type": "error", "payload": "server_no_response"}
                )
                srv_sock.close()
                return
            sock.sendall(len_bytes)

            # Forward JSON
            json_len = struct.unpack("!I", len_bytes)[0]
            json_data = b""
            while len(json_data) < json_len:
                chunk = srv_sock.recv(min(4096, json_len - len(json_data)))
                if not chunk:
                    break
                json_data += chunk
            sock.sendall(json_data)

            srv_sock.close()
        except Exception as e:
            print(f"[ERROR] Uploading: {e}")

    def handle_preview(self, sock: socket.socket, req: dict):
        path = req["path"]
        target_server = self._get_target_server_by_path(path)

        if not target_server:
            self._send_packet(sock, {"type": "error", "payload": "file not found"})
            return

        print(f"[COORDINATOR] Forward to server: {target_server}")

        try:
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv_sock.settimeout(10)
            srv_sock.connect(target_server)
            self._send_packet(srv_sock, req)

            # Forward Header
            len_bytes = srv_sock.recv(4)
            if not len_bytes:
                self._send_packet(
                    sock, {"type": "error", "payload": "server_no_response"}
                )
                srv_sock.close()
                return
            sock.sendall(len_bytes)

            # Forward JSON
            json_len = struct.unpack("!I", len_bytes)[0]
            json_data = b""
            while len(json_data) < json_len:
                chunk = srv_sock.recv(min(4096, json_len - len(json_data)))
                if not chunk:
                    break
                json_data += chunk
            sock.sendall(json_data)

            # Check ready and Stream Data
            resp = json.loads(json_data.decode("utf-8"))
            if resp.get("type") == "preview_ready":
                file_size = resp["payload"].get("size", 0)
                received = 0
                while received < file_size:
                    chunk = srv_sock.recv(min(8192, file_size - received))
                    if not chunk:
                        break
                    sock.sendall(chunk)
                    received += len(chunk)
            srv_sock.close()
        except Exception as e:
            print(f"[ERROR] Download: {e}")

    # download function
    def handle_download(self, client_sock, request_dict):
        path = request_dict.get("path")
        target_server = self._get_target_server_by_path(path)

        if not target_server:
            self._send_packet(
                client_sock, {"type": "error", "payload": "file_not_found"}
            )
            return

        try:
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv_sock.settimeout(10)
            srv_sock.connect(target_server)
            self._send_packet(srv_sock, request_dict)

            # Forward Header
            len_bytes = srv_sock.recv(4)
            if not len_bytes:
                self._send_packet(
                    client_sock, {"type": "error", "payload": "server_no_response"}
                )
                srv_sock.close()
                return
            client_sock.sendall(len_bytes)

            # Forward JSON
            json_len = struct.unpack("!I", len_bytes)[0]
            json_data = b""
            while len(json_data) < json_len:
                chunk = srv_sock.recv(min(4096, json_len - len(json_data)))
                if not chunk:
                    break
                json_data += chunk
            client_sock.sendall(json_data)

            # Check ready and Stream Data
            resp = json.loads(json_data.decode("utf-8"))
            if resp.get("type") == "ready":
                file_size = resp["payload"].get("size", 0)
                received = 0
                while received < file_size:
                    chunk = srv_sock.recv(min(8192, file_size - received))
                    if not chunk:
                        break
                    client_sock.sendall(chunk)
                    received += len(chunk)
            srv_sock.close()
        except Exception as e:
            print(f"[ERROR] Download: {e}")

    # seacrh function
    def handle_search(self, client_sock, request_dict):
        # trim input query
        raw_query = request_dict.get("query", "").strip()

        if not raw_query:
            self._send_packet(
                client_sock, {"type": "error", "payload": "query_required"}
            )
            return

        query_norm = raw_query.lower()
        filters = request_dict.get("filters", ["all"])

        print(f"[SEARCH] Raw Query: '{raw_query}'")

        # extension detection
        detected_video = False

        for ext in video_exts:
            if query_norm.endswith(ext):
                filters = ["video"]
                detected_video = True
                print(
                    f"[SEARCH] Detected video extension '{ext}' -> Filter set to VIDEO"
                )
                break

        if not detected_video:
            for ext in image_exts:
                if query_norm.endswith(ext):
                    filters = ["image"]
                    print(
                        f"[SEARCH] Detected image extension '{ext}' -> Filter set to IMAGE"
                    )
                    break

        backend_req = {"command": "list", "filters": filters, "path": "/"}

        # forward to relevant servers based on filters
        servers_to_query = []
        if "image" in filters or "all" in filters:
            servers_to_query.append(SERVER_NODE["image"])
        if "video" in filters or "all" in filters:
            servers_to_query.append(SERVER_NODE["video"])
        if "text" in filters or "all" in filters:
            servers_to_query.append(SERVER_NODE["text"])
        if "sound" in filters or "all" in filters:
            servers_to_query.append(SERVER_NODE["sound"])
        if "compressed" in filters or "all" in filters:
            servers_to_query.append(SERVER_NODE["compressed"])

        final_response = {
            "type": "list",
            "payload": {
                "name": "search_results",
                "path": "search/",
                "subdirectories": [],
                "files": [],
            },
        }

        found_files = []

        for srv_addr in servers_to_query:

            res = self.forward_json_request(srv_addr, backend_req)

            if res and res.get("type") == "list":
                root_node = res.get("payload", {})

                self._recursive_search(root_node, query_norm, found_files)

        final_response["payload"]["files"] = found_files

        print(f"[SEARCH] Found {len(found_files)} files matching '{raw_query}'")
        self._send_packet(client_sock, final_response)

    def _recursive_search(self, current_dir_node, query_norm, results_list):
        for file_info in current_dir_node.get("files", []):
            file_name = file_info.get("name", "").lower()
            if query_norm in file_name:
                results_list.append(file_info)

        for subdir in current_dir_node.get("subdirectories", []):
            self._recursive_search(subdir, query_norm, results_list)

    def merge_directory_nodes(self, target_node, source_node):
        """
        Hàm đệ quy để gộp source_node vào target_node.
        """
        # 1. Gộp Files (Tránh trùng lặp dựa trên path của file)
        existing_file_paths = {f["path"] for f in target_node["files"]}
        for file_obj in source_node["files"]:
            if file_obj["path"] not in existing_file_paths:
                target_node["files"].append(file_obj)
                existing_file_paths.add(file_obj["path"])

        # 2. Gộp Subdirectories
        # Tạo map để tra cứu nhanh thư mục con hiện có trong target
        target_subs_map = {sub["path"]: sub for sub in target_node["subdirectories"]}

        for source_sub in source_node["subdirectories"]:
            path = source_sub["path"]
            if path in target_subs_map:
                # Nếu thư mục con đã tồn tại, đệ quy để gộp nội dung bên trong
                self.merge_directory_nodes(target_subs_map[path], source_sub)
            else:
                # Nếu chưa tồn tại, thêm mới vào
                target_node["subdirectories"].append(source_sub)
                # Cập nhật map (dù không dùng lại ngay nhưng tốt cho logic)
                target_subs_map[path] = source_sub

    def merge_response_list(self, data_list):
        """
        Hàm chính để quản lý việc gộp các root folders
        """
        merged_roots = {}  # Key: folder path, Value: folder object

        for item in data_list:
            root_path = item["path"]

            if root_path not in merged_roots:
                # Nếu root chưa có, copy làm gốc
                # Dùng deepcopy nếu dữ liệu phức tạp, ở đây dict đơn giản có thể gán hoặc copy nông
                import copy

                merged_roots[root_path] = copy.deepcopy(item)
            else:
                # Nếu root đã có, tiến hành merge
                self.merge_directory_nodes(merged_roots[root_path], item)

        return list(merged_roots.values())

    def handle_list(self, client_sock: socket.socket, request: dict):
        path = request.get("path", DEFAULT_PATH)
        filters = request.get("filters", ["all"])

        final_response = {
            "type": "list",
            "payload": {
                "name": "storage",
                "path": path,
                "subdirectories": [],
                "files": [],
            },
        }

        servers_to_query = []
        for node in SERVER_NODE.keys():
            if node in filters or "all" in filters:
                servers_to_query.append((node, SERVER_NODE[node]))

        # Use a dictionary to merge subdirectories by name
        dir_map = {}

        for server_type, server_addr in servers_to_query:
            backend_req = {
                "command": "list",
                "path": path,
                "filters": [server_type],
            }
            res = self.forward_json_request(server_addr, backend_req)

            if res and res.get("type") == "list":
                payload = res.get("payload", {})

                # Append files, adding server metadata
                for file_info in payload.get("files", []):
                    file_info["server_type"] = server_type
                    file_info["server"] = f"{server_addr[0]}:{server_addr[1]}"
                    final_response["payload"]["files"].append(file_info)

                # Merge subdirectories
                for dir_info in payload.get("subdirectories", []):
                    final_response["payload"]["subdirectories"].append(dir_info)
                    # dir_name = dir_info.get("name")
                    # if not dir_name:
                    #     continue
                    # print((f"dir name = {dir_info}"))
                    # if dir_name not in dir_map:
                    #     # First time seeing this directory, add server metadata and store it
                    #     dir_info["server_type"] = server_type
                    #     dir_info["server"] = f"{server_addr[0]}:{server_addr[1]}"
                    #     dir_map[dir_name] = dir_info
                    # else:
                    #     # Directory already exists, merge files and subdirectories
                    #     existing_dir = dir_map[dir_name]
                    #     existing_dir["files"].extend(dir_info.get("files", []))
                    #     existing_dir["subdirectories"].extend(
                    #         dir_info.get("subdirectories", [])
                    #     )

        # Add the merged directories to the final response
        final_response["payload"]["subdirectories"] = self.merge_response_list(
            final_response["payload"]["subdirectories"]
        )

        self._send_packet(client_sock, final_response)

    def handle_client(self, client_sock, client_addr):
        try:
            client_addr = client_sock.getpeername()
        except:
            client_addr = "unknown"
        print(f"[CLIENT] Connected: {client_addr}")

        try:
            # Chiko was here -> them while True giu ket noi voi client
            while True:
                # Nhận request từ client
                request = self._recv_packet(client_sock)
                if not request:
                    print(f"[CLIENT] No request from {client_addr}")
                    return

                command = request.get("command")
                path = request.get("path", DEFAULT_PATH)
                print(f"[REQUEST] {client_addr} - Command: {command} - Path: {path}")

                # --- COMMAND: LIST ---
                if command == "list":
                    self.handle_list(client_sock, request)
                # --- COMMAND: DOWNLOAD ---
                elif command == "download":
                    self.handle_download(client_sock, request)

                # --- COMMAND: SEARCH ---
                elif command == "search":
                    self.handle_search(client_sock, request)

                elif command == "preview":
                    self.handle_preview(client_sock, request)

                elif command == "upload":
                    self.handle_upload(client_sock, request)

                # --- UNKNOWN COMMAND ---
                else:
                    self._send_packet(
                        client_sock,
                        {"type": "error", "payload": f"unknown_command: {command}"},
                    )
        except Exception as e:
            print(f"[ERROR] Handling client {client_addr}: {e}")
            try:
                self._send_packet(client_sock, {"type": "error", "payload": str(e)})
            except:
                pass
        finally:
            client_sock.close()
            print(f"[CLIENT] Disconnected: {client_addr}")

    def start(self):
        print(f"[COORDINATOR] Waiting for connections...")

        try:
            while True:
                client_sock, client_addr = self.sock.accept()

                client_thread = threading.Thread(
                    target=self.handle_client, args=(client_sock, client_addr)
                )
                client_thread.daemon = True
                client_thread.start()

        except KeyboardInterrupt:
            print("\n[COORDINATOR] Shutting down...")
        finally:
            self.sock.close()
            print("[COORDINATOR] Stopped")


if __name__ == "__main__":
    print("=" * 60)
    print("DISTRIBUTED FILE SYSTEM - COORDINATOR")
    print("=" * 60)
    try:
        host = sys.argv[1] if len(sys.argv) > 1 else HOST
        port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
        coordinator = Coordinator(host, port)
        coordinator.start()
    except KeyboardInterrupt:
        print("\n[COORDINATOR] Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        sys.exit(1)
