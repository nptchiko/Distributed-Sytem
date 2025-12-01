import socket
import threading
import json
import sys

# Server addresses (Backend)
server1 = ("127.0.0.1", 8001) # Image server
server2 = ("127.0.0.1", 8002) # Video server

class Coordinator:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Đổi tên thành self.sock cho thống nhất
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.ip, self.port))
        self.sock.listen(5)
        print(f"[COORDINATOR] Load Balancer started on {self.ip}:{self.port}")

    def forward_request(self, server_address, request_dict):

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(server_address)
            s.send(json.dumps(request_dict).encode('utf-8'))

            # Receive response
            res_data = s.recv(8192)
            s.close()
            return json.loads(res_data.decode('utf-8'))
        except Exception as e:
            print(f"Error forwarding to {server_address}: {e}")
            return {"status": "error", "message": "Server offline"}

    def handle_client(self, client):

        try:
            raw_data = client.recv(4096).decode('utf-8')
            if not raw_data: return

            request = json.loads(raw_data)
            print(f"[REQUEST] Received: {request}")

            command = request.get('command')
            filters = request.get('filters', [])

            final_result = {"files": [], "errors": []}

            if command == 'list':
                #image -> server1
                if "image" in filters:
                    res = self.forward_request(server1, request)
                    if res.get("status") == "success":
                        final_result["files"].extend(res.get("data", []))
                    else:
                        final_result["errors"].append(f"ImageServer: {res.get('message')}")

                # video -> server2
                if "video" in filters:
                    res = self.forward_request(server2, request)
                    if res.get("status") == "success":
                        final_result["files"].extend(res.get("data", []))
                    else:
                        final_result["errors"].append(f"VideoServer: {res.get('message')}")

            #send final response to client
            client.send(json.dumps(final_result, indent=2).encode('utf-8'))

        except Exception as e:
            print(f"Error handling client: {e}")
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