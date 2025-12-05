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
        print(f"[COORDINATOR] Load Balancer started on {self.ip}:{self.port}")

    def _send_packet(self, sock, data_dict):
        try:
            json_bytes = json.dumps(data_dict).encode('utf-8')
            header = stuct.pack('!I', len(json_bytes))
            sock.sendall(header + json_bytes)
        except Exception as e:
            print(f"Error sending packet: {e}")

    def _recv_packet(self, sock):
        try:
            len_bytes = sock.recv(4)
            if not len_bytes: return None
            payload_len = struct.unpack('!I', len_bytes)[0]

            payload = b''
            while len(payload) < payload_len:
                chunk = sock.recv(payload_len - len(payload))
                if not chunk: return None
                payload += chunk
            return json.loads(payload.decode('utf-8'))
        except Exception as e:
            print(f"Error receiving packet: {e}")
            return None
    def _get_target_server_by_path(self, path):
        ext = path[path.rfind('.'):].lower()
        if ext in image_exts:
            return server1
        elif ext in video_exts:
            return server2
        else:
            return None
    def forward_json_request(self, server_address, request_dict):
        """Gửi request JSON tới server con và nhận lại JSON (Dùng cho List)"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect(server_address)


            self._send_packet(s, request_dict)


            response = self._recv_packet(s)
            s.close()
            return response
        except Exception as e:
            print(f"Error forwarding to {server_address}: {e}")
            return {"type": "error", "message": "Server offline"}
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

    def handle_download(self, client_sock, request_dict):
        path = request_dict.get("path")
        target_server = self._get_target_server_by_path(path)

        print(f"[PROXY] Downloading {path} from {target_server}")
        try:
            # 1. Kết nối
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv_sock.connect(target_server)

            # 2. Gửi lệnh Download
            self._send_packet(srv_sock, request_dict)

            # 3. Đọc Header từ Backend -> Forward ngay cho Client
            len_bytes = srv_sock.recv(4)
            if not len_bytes: return
            client_sock.sendall(len_bytes)

            # 4. Đọc JSON từ Backend -> Forward ngay cho Client
            json_len = struct.unpack('!I', len_bytes)[0]
            json_data = b""
            while len(json_data) < json_len:
                chunk = srv_sock.recv(min(4096, json_len - len(json_data)))
                if not chunk: break
                json_data += chunk
            client_sock.sendall(json_data)

            # 5. Check xem Server ready?
            resp = json.loads(json_data.decode('utf-8'))
            if resp.get("type") == "ready":
                file_size = resp["payload"]["size"]
                print(f"[PROXY] Streaming {file_size} bytes...")

                # 6. Stream Binary Data
                received = 0
                while received < file_size:
                    chunk = srv_sock.recv(min(8192, file_size - received))
                    if not chunk: break
                    client_sock.sendall(chunk)
                    received += len(chunk)
                print("[PROXY] Transfer complete.")

            srv_sock.close()

        except Exception as e:
            print(f"Download Proxy Error: {e}")
            try:
                self._send_packet(client_sock, {"type": "error", "payload": str(e)})
            except: pass

    def handle_client(self, client):

        try:

            request = self._recv_packet(client)
            if not request: return

            print(f"[REQUEST] {request}")
            command = request.get('command')
            filters = request.get('filters', [])

            # --- COMMAND: LIST ---
            if command == 'list':


                final_response = {
                    "type": "list",
                    "payload": {
                        "name": "root",
                        "path": "/",
                        "subdirectories": [],
                        "files": []
                    }
                }

                # Helper query function
                def query_and_merge(server_addr):
                    res = self.forward_json_request(server_addr, request)
                    if res and res.get("type") == "list":
                        data = res.get("payload", {})
                        # Merge files
                        if "files" in data:
                            final_response["payload"]["files"].extend(data["files"])
                        if "subdirectories" in data:
                            final_response["payload"]["subdirectories"].extend(data["subdirectories"])

                if "image" in filters or "all" in filters:
                    query_and_merge(server1)

                if "video" in filters or "all" in filters:
                    query_and_merge(server2)

                self._send_packet(client, final_response)

            # --- COMMAND: DOWNLOAD ---
            elif command == 'download':
                self.handle_download_proxy(client, request)

            # --- UNKNOWN ---
            else:
                self._send_packet(client, {"type": "error", "payload": "Unknown command"})

        except Exception as e:
            print(f"Client Handle Error: {e}")
        finally:
            client.close()

    def start(self):
        while True:
            client, addr = self.sock.accept()

            threading.Thread(target=self.handle_client, args=(client,)).start()

if __name__ == "__main__":

    try:
        Coordinator("127.0.0.1", 9000).start()
    except KeyboardInterrupt:
        print("\nStopping Coordinator...")
        sys.exit(0)