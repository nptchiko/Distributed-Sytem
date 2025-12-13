"""
dfs_client.py

Low-level DFS client utilities for connecting to the Python DFS server
(the protocol matches the server I provided earlier: 4-byte big-endian length-prefixed
JSON control messages followed by raw bytes for file transfers).

This is a reusable module that the Tkinter UI will import and use.

Usage:
    from dfs_client import DFSClient
    c = DFSClient('127.0.0.1', 9000)
    c.connect()
    c.list_files()
    c.upload_file(local_path, remote_name)
    c.download_file(remote_name, local_path)
    c.delete_file(remote_name)
    c.close()
"""

from __future__ import print_function
import socket
import json
import hashlib
import os
from typing import Optional, Dict, Any

ENCODING = "utf-8"
DEFAULT_BUFSIZE = 8192


class DFSProtocolError(Exception):
    pass


class DFSClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9000,
        path: str = "",
        bufsize: int = DEFAULT_BUFSIZE,
    ):
        self.host = host
        self.port = port
        self.path = path
        self.sock: Optional[socket.socket] = None
        self.bufsize = bufsize

    def connect(self, timeout: Optional[float] = None):
        if self.sock:
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout:
            s.settimeout(timeout)
        s.connect((self.host, self.port))
        s.settimeout(None)
        self.sock = s

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _recv_all(self, n: int) -> bytes:
        assert self.sock is not None
        data = bytearray()
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise EOFError("Connection closed while reading")
            data.extend(chunk)
        return bytes(data)

    def _recv_control(self) -> Dict[str, Any]:
        assert self.sock is not None
        length_bytes = self._recv_all(4)
        length = int.from_bytes(length_bytes, "big")
        payload = self._recv_all(length)
        try:
            print(f"=========== RESPONSE ============")
            print(json.dumps(payload.decode(ENCODING), indent=2))
            print("=================================")
            print()
            return json.loads(payload.decode(ENCODING))
        except Exception as e:
            raise DFSProtocolError("Invalid control JSON") from e

    def _send_control(self, obj: Dict[str, Any]):
        assert self.sock is not None
        b = json.dumps(obj).encode(ENCODING)
        print(f"=========== REQUEST ============")
        print(obj)
        print("=================================")
        self.sock.sendall(len(b).to_bytes(4, "big") + b)

    # author: Quang Minh
    # agruemnt: filter
    # example: "all", "image", "video"
    def list_files(self, filter: list[str]):
        self._send_control(
            {
                "command": "list",
                "filters": filter or [],
                "path": self.path,
            }
        )
        return self._recv_control()

    def ping(self):
        self._send_control({"command": "ping"})
        return self._recv_control()

    def delete_file(self, remote_name: str):
        self._send_control(
            {"command": "delete", "payload": {"path": f"{self.path}{remote_name}"}}
        )
        return self._recv_control()

    def upload_file(
        self, local_path: str, remote_name: Optional[str] = None, progress_callback=None
    ):
        assert self.sock is not None
        if not os.path.exists(local_path) or not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)
        size = os.path.getsize(local_path)
        h = hashlib.sha256()
        with open(local_path, "rb") as f:
            while True:
                chunk = f.read(self.bufsize)
                if not chunk:
                    break
                h.update(chunk)
        sha = h.hexdigest()
        print(f"[DEBUG] LOCAL PATH: {local_path} {remote_name}")

        name = os.path.dirname(remote_name) + "/" + os.path.basename(local_path)

        print(f"[DEBUG] FILE NAME: {name}")
        # Send control
        self._send_control(
            {
                "command": "upload",
                "payload": {"name": name, "size": size, "sha256": sha},
            }
        )
        ready = self._recv_control()
        if not ready or ready.get("type") != "ready":
            raise DFSProtocolError(f"Server refused upload: {ready}")
        # stream file bytes
        sent = 0
        with open(local_path, "rb") as f:
            while True:
                chunk = f.read(self.bufsize)
                if not chunk:
                    break
                self.sock.sendall(chunk)
                sent += len(chunk)
                if progress_callback:
                    progress_callback(sent, size)
        # receive result
        return self._recv_control()

    # author: QuangMinh
    # Description: filter function use for check type of file to navigate image-server or video server
    # input: str: absolute path of file
    # output: filter -> image or video
    # def _filter(self, remote_name: str):
    #     if remote_name.endswith(".jpg") or remote_name.endswith(".jpeg") or remote_name.endswith(".png"):
    #         return "image"
    #     elif remote_name.endswith(".mp4") or remote_name.endswith(".mkv") or remote_name.endswith(".webm") or remote_name.endswith(".flv"):
    #         return "video"
    #     else:
    #         return None

    # author: QuangMinh
    # Description: add filter of file to load-balancing server with filter
    # Example: {"command": "download", "payload": {"name": "/home/public/Documents/a.jpg", "filter": "image"}}
    def download_file(self, remote_name: str, local_path: str, progress_callback=None):

        # remote_name -> file name

        if not os.path.exists(os.path.dirname(local_path)):
            os.makedirs(os.path.dirname(local_path))
        # send control
        self._send_control(
            {
                # Author:
                # Description: Sua lai cai schema
                # OLD
                # "command": "download",
                # "payload": {
                #     "path": f"{self.path}{remote_name}",
                #     "filter": _filter(remote_name),
                # },
                # NEW
                "command": "download",
                "path": f"{os.path.join(self.path, remote_name)}",
            }
        )
        ready = self._recv_control()
        if not ready:
            raise DFSProtocolError("No response from server")
        # FIX
        # Author: chiko
        # Description: sua lai schema :)
        #
        # if ready.get("command") == "error":
        #     return ready
        # if ready.get("command") != "ready":
        #     raise DFSProtocolError(f"Unexpected control reply: {ready}")

        if ready["type"] == "error":
            raise DFSProtocolError(f"Error when downloading: {ready}")
        if ready["type"] != "ready":
            raise DFSProtocolError(f"Unexpected control reply: {ready}")

        size = int(ready["payload"]["size"])
        expected_sha = ready["payload"].get("sha256")
        # receive raw bytes
        received = 0
        h = hashlib.sha256()
        tmp_path = local_path + ".tmp"
        with open(tmp_path, "wb") as f:
            while received < size:
                chunk = self.sock.recv(min(self.bufsize, size - received))
                if not chunk:
                    raise EOFError("Connection closed during download")
                f.write(chunk)
                h.update(chunk)
                received += len(chunk)
                if progress_callback:
                    progress_callback(received, size)
        actual_sha = h.hexdigest()
        if expected_sha and expected_sha != actual_sha:
            os.remove(tmp_path)
            raise DFSProtocolError("SHA mismatch after download")
        os.replace(tmp_path, local_path)

        return {
            "command": "download_result",
            "payload": {"ok": True, "size": size, "sha256": actual_sha},
        }

    def preview_file(self, remote_name: str):
        self._send_control(
            {
                "command": "preview",
                # "payload": {
                #     "path": os.path.join(self.path, remote_name),
                #     "filter": _filter(remote_name),
                # },
                "path": os.path.join(self.path, remote_name),
            }
        )

        ready = self._recv_control()
        if not ready:
            raise DFSProtocolError("No response from server")
        if ready.get("type") == "error":
            return ready, None

        if ready.get("type") != "preview_ready":
            raise DFSProtocolError(f"Unexpected control reply: {ready}")

        size = int(ready["payload"]["size"])
        file_type = ready["payload"]["type"]

        data = self._recv_all(size)
        return data, file_type


def _filter(remote_name: str):
    if remote_name.endswith((".jpg", ".jpeg", ".png", ".gif")):
        return "image"
    elif remote_name.endswith((".txt", ".md", ".py", ".json", ".xml")):
        return "text"
    else:
        return "binary"
