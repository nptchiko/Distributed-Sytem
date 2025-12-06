import socket
import threading
import json
import sys
import struct
# Server addresses
server1 = ("127.0.0.1", 8001) # Image server
server2 = ("127.0.0.1", 8002) # Video server

# format extensions
video_exts = {".mp4", ".mkv", ".webm", ".flv", ".avi"}
image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

class Coordinator:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.ip, self.port))
        self.sock.listen(5)
        print(f"[COORDINATOR] Started on {self.ip}:{self.port}")
        print(f"[COORDINATOR] Image Server: {server1}")
        print(f"[COORDINATOR] Video Server: {server2}")

    def _send_packet(self, sock, data_dict):
        try:
            json_bytes = json.dumps(data_dict).encode('utf-8')
            header = struct.pack('!I', len(json_bytes))
            sock.sendall(header + json_bytes)
        except Exception as e:
            print(f"[ERROR] Sending packet: {e}")

    def _recv_packet(self, sock):
        try:
            # Đọc header (4 bytes)
            len_bytes = sock.recv(4)
            if not len_bytes:
                return None
            payload_len = struct.unpack('!I', len_bytes)[0]

            # Đọc payload
            payload = b''
            while len(payload) < payload_len:
                chunk = sock.recv(payload_len - len(payload))
                if not chunk:
                    return None
                payload += chunk

            return json.loads(payload.decode('utf-8'))
        except Exception as e:
            print(f"[ERROR] Receiving packet: {e}")
            return None

    def _get_target_server_by_path(self, path):
        # define target server based on file extension
        if not path or '.' not in path:
            return None

        ext = path[path.rfind('.'):].lower()
        if ext in image_exts:
            return server1
        elif ext in video_exts:
            return server2
        else:
            return None

    def forward_json_request(self, server_address, request_dict):

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect(server_address)


            self._send_packet(s, request_dict)


            response = self._recv_packet(s)
            s.close()

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

    #download function
    def handle_download(self, client_sock, request_dict):
        path = request_dict.get("path")
        target_server = self._get_target_server_by_path(path)

        if not target_server:
            self._send_packet(client_sock, {"type": "error", "payload": "file_not_found"})
            return

        try:
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv_sock.settimeout(10)
            srv_sock.connect(target_server)
            self._send_packet(srv_sock, request_dict)

            # Forward Header
            len_bytes = srv_sock.recv(4)
            if not len_bytes:
                self._send_packet(client_sock, {"type": "error", "payload": "server_no_response"})
                srv_sock.close()
                return
            client_sock.sendall(len_bytes)

            # Forward JSON
            json_len = struct.unpack('!I', len_bytes)[0]
            json_data = b""
            while len(json_data) < json_len:
                chunk = srv_sock.recv(min(4096, json_len - len(json_data)))
                if not chunk: break
                json_data += chunk
            client_sock.sendall(json_data)

            # Check ready and Stream Data
            resp = json.loads(json_data.decode('utf-8'))
            if resp.get("type") == "ready":
                file_size = resp["payload"].get("size", 0)
                received = 0
                while received < file_size:
                    chunk = srv_sock.recv(min(8192, file_size - received))
                    if not chunk: break
                    client_sock.sendall(chunk)
                    received += len(chunk)
            srv_sock.close()
        except Exception as e:
            print(f"[ERROR] Download: {e}")
    #seacrh function
    def handle_search(self, client_sock, request_dict):
        # trim input query
        raw_query = request_dict.get("query", "").strip()


        if not raw_query:
            self._send_packet(client_sock, {"type": "error", "payload": "query_required"})
            return

        query_norm = raw_query.lower()
        filters = request_dict.get("filters", ["all"])

        print(f"[SEARCH] Raw Query: '{raw_query}'")

        # extension detection
        detected_video = False
        detected_image = False


        for ext in video_exts:
            if query_norm.endswith(ext):
                filters = ["video"]
                detected_video = True
                print(f"[SEARCH] Detected video extension '{ext}' -> Filter set to VIDEO")
                break


        if not detected_video:
            for ext in image_exts:
                if query_norm.endswith(ext):
                    filters = ["image"]
                    detected_image = True
                    print(f"[SEARCH] Detected image extension '{ext}' -> Filter set to IMAGE")
                    break


        backend_req = {
            "command": "list",
            "filters": filters,
            "path": "/"
        }

        # forward to relevant servers based on filters
        servers_to_query = []
        if "image" in filters or "all" in filters:
            servers_to_query.append(server1)
        if "video" in filters or "all" in filters:
            servers_to_query.append(server2)


        final_response = {
            "type": "list",
            "payload": {
                "name": "search_results",
                "path": "search/",
                "subdirectories": [],
                "files": []
            }
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

    def _merge_directories(self, existing_list, new_list):
        """
        merge by directory name
        """
        dir_map = {d["name"]: d for d in existing_list}

        for new_dir in new_list:
            name = new_dir.get("name")
            if name in dir_map:

                existing_files = dir_map[name].get("files", [])
                new_files = new_dir.get("files", [])
                existing_files.extend(new_files)

            else:
                existing_list.append(new_dir)
                dir_map[name] = new_dir

        return existing_list
    def _recursive_search(self, current_dir_node, query_norm, results_list):
        for file_info in current_dir_node.get("files", []):
            file_name = file_info.get("name", "").lower()
            if query_norm in file_name:
                results_list.append(file_info)

        for subdir in current_dir_node.get("subdirectories", []):
            self._recursive_search(subdir, query_norm, results_list)
#info function
    def handle_info(self, client_sock, request_dict):

        path = request_dict.get("path")
        if not path:
            self._send_packet(client_sock, {"type": "error", "payload": "path_required"})
            return


        target_server = self._get_target_server_by_path(path)

        if target_server:

            res = self.forward_json_request(target_server, request_dict)
            self._send_packet(client_sock, res)
        else:
            # search both servers
            for server_addr in [server1, server2]:
                res = self.forward_json_request(server_addr, request_dict)
                if res and res.get("type") != "error":
                    self._send_packet(client_sock, res)
                    return


            self._send_packet(client_sock, {"type": "error", "payload": "file_not_found"})

    def handle_client(self, client_sock, client_addr):
        try:
            client_addr = client_sock.getpeername()
        except:
            client_addr = "unknown"
        print(f"[CLIENT] Connected: {client_addr}")

        try:
            # Nhận request từ client
            request = self._recv_packet(client_sock)
            if not request:
                print(f"[CLIENT] No request from {client_addr}")
                return

            command = request.get('command')
            print(f"[REQUEST] {client_addr} - Command: {command}")

            # --- COMMAND: LIST ---
            if command == 'list':
                filters = request.get('filters', ['all'])

                final_response = {
                    "type": "list",
                    "payload": {
                        "name": "root",
                        "path": request.get("path", "/"),
                        "subdirectories": [],
                        "files": []
                    }
                }

                # Query servers dựa trên filters
                servers_to_query = []
                if "image" in filters or "all" in filters:
                    servers_to_query.append(("image", server1))
                if "video" in filters or "all" in filters:
                    servers_to_query.append(("video", server2))

                for server_type, server_addr in servers_to_query:
                    res = self.forward_json_request(server_addr, request)
                    if res and res.get("type") == "list":
                        payload = res.get("payload", {})

                        # Merge files
                        for file_info in payload.get("files", []):
                            file_info["server_type"] = server_type
                            file_info["server"] = f"{server_addr[0]}:{server_addr[1]}"
                            final_response["payload"]["files"].append(file_info)

                        # Merge subdirectories
                        for dir_info in payload.get("subdirectories", []):
                            dir_info["server_type"] = server_type
                            dir_info["server"] = f"{server_addr[0]}:{server_addr[1]}"
                            final_response["payload"]["subdirectories"].append(dir_info)

                self._send_packet(client_sock, final_response)

            # --- COMMAND: DOWNLOAD ---
            elif command == 'download':
                self.handle_download(client_sock, request)

            # --- COMMAND: SEARCH ---
            elif command == 'search':
                self.handle_search(client_sock, request)

            # # --- COMMAND: INFO ---
            # elif command == 'info':
            #     self.handle_info(client_sock, request)

            # --- UNKNOWN COMMAND ---
            else:
                self._send_packet(client_sock, {
                    "type": "error",
                    "payload": f"unknown_command: {command}"
                })

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
                    target=self.handle_client,
                    args=(client_sock, client_addr)
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
        coordinator = Coordinator("127.0.0.1", 9000)
        coordinator.start()
    except KeyboardInterrupt:
        print("\n[COORDINATOR] Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        sys.exit(1)