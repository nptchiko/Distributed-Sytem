"""
client_gui.py

Tkinter-based GUI for the Distributed File System client.
This UI uses dfs_client.DFSClient to talk to the Python DFS server.

Features:
- Connect / Disconnect to server
- Show list of files on server with name, size, sha256
- Upload local files (with progress)
- Download selected file to a chosen local path (with progress)
- Delete file on server
- Simple status / logs area

Usage:
    python client_gui.py [host] [port]

This GUI is intentionally simple but maps to standard actions present in the original C# client.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import sys
from dfs_client import DFSClient, DFSProtocolError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_PATH = "./"


class App(tk.Tk):
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, path=DEFAULT_PATH):
        super().__init__()
        self.title("DFS Client (Tkinter)")
        self.geometry("800x520")
        self.resizable(True, True)

        self.host = host
        self.port = port
        self.path = path
        self.client = DFSClient(self.host, self.port)
        self.worker_lock = threading.Lock()

        # Top frame: connection
        conn_frame = ttk.Frame(self)
        conn_frame.pack(fill="x", padx=8, pady=6)

        ttk.Label(conn_frame, text="Host:").pack(side="left")
        self.host_var = tk.StringVar(value=self.host)
        ttk.Entry(conn_frame, textvariable=self.host_var, width=18).pack(
            side="left", padx=(4, 8)
        )

        ttk.Label(conn_frame, text="Port:").pack(side="left")
        self.port_var = tk.StringVar(value=str(self.port))
        ttk.Entry(conn_frame, textvariable=self.port_var, width=7).pack(
            side="left", padx=(4, 8)
        )

        ttk.Label(conn_frame, text="Path:").pack(side="left")
        self.path_var = tk.StringVar(value=str(self.path))
        ttk.Entry(conn_frame, textvariable=self.path_var, width=20).pack(
            side="left", padx=(4, 8)
        )

        self.btn_connect = ttk.Button(
            conn_frame, text="Connect", command=self.on_connect
        )
        self.btn_connect.pack(side="left", padx=(6, 4))

        self.btn_disconnect = ttk.Button(
            conn_frame, text="Disconnect", command=self.on_disconnect, state="disabled"
        )
        self.btn_disconnect.pack(side="left")

        # Middle: file list and actions
        mid_frame = ttk.Frame(self)
        mid_frame.pack(fill="both", expand=True, padx=8, pady=6)

        # File list tree
        cols = ("name", "size", "sha256")
        self.tree = ttk.Treeview(mid_frame, columns=cols, show="headings")
        self.tree.heading("name", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("sha256", text="SHA256")
        self.tree.column("name", width=280, anchor="w")
        self.tree.column("size", width=90, anchor="center")
        self.tree.column("sha256", width=380, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(mid_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="left", fill="y")
        self.tree.configure(yscroll=vsb.set)

        # Action buttons
        action_frame = ttk.Frame(mid_frame)
        action_frame.pack(side="left", fill="y", padx=8)
        ttk.Button(action_frame, text="Refresh List", command=self.refresh_list).pack(
            fill="x", pady=(0, 6)
        )
        ttk.Button(
            action_frame, text="Upload File...", command=self.upload_file_dialog
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            action_frame, text="Download Selected...", command=self.download_selected
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            action_frame, text="Delete Selected", command=self.delete_selected
        ).pack(fill="x", pady=(0, 6))

        # Bottom: status and progress
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.status_var = tk.StringVar(value="Disconnected")
        ttk.Label(bottom_frame, textvariable=self.status_var).pack(side="left")

        self.progress = ttk.Progressbar(
            bottom_frame, orient="horizontal", length=300, mode="determinate"
        )
        self.progress.pack(side="right")

        # Log area
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=False, padx=8, pady=(0, 8))
        ttk.Label(log_frame, text="Logs:").pack(anchor="w")
        self.log = tk.Text(log_frame, height=6)
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

    # ---- UI helpers ----
    def log_msg(self, s: str):
        self.log.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] {s}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_status(self, s: str):
        self.status_var.set(s)

    def set_progress(self, value: int, maximum: int = 100):
        if maximum <= 0:
            self.progress.configure(mode="indeterminate")
            return
        self.progress.configure(mode="determinate", maximum=maximum)
        self.progress["value"] = value
        self.update_idletasks()

    # ---- Connection actions ----
    def on_connect(self):
        host = self.host_var.get().strip() or DEFAULT_HOST
        try:
            port = int(self.port_var.get().strip())
        except Exception:
            messagebox.showerror("Invalid port", "Port must be an integer")
            return
        self.set_status("Connecting...")
        self.log_msg(f"Connecting to {host}:{port}...")

        def work():
            try:
                self.client = DFSClient(host, port)
                self.client.connect()
                self.set_status(f"Connected to {host}:{port}")
                self.log_msg("Connected")
                self.btn_connect.configure(state="disabled")
                self.btn_disconnect.configure(state="normal")
                # initial list
                self.refresh_list()
            except Exception as e:
                self.log_msg(f"Connect failed: {e}")
                self.set_status("Disconnected")

        threading.Thread(target=work, daemon=True).start()

    def on_disconnect(self):
        try:
            self.client.close()
        except Exception:
            pass
        self.btn_connect.configure(state="normal")
        self.btn_disconnect.configure(state="disabled")
        self.set_status("Disconnected")
        self.log_msg("Disconnected")

    # ---- File operations ----
    def refresh_list(self):
        def work():
            try:
                resp = self.client.list_files()
                if resp.get("command") == "list":
                    files = resp.get("payload", [])
                    self.tree.delete(*self.tree.get_children())
                    for f in files:
                        name = f.get("name")
                        size = f.get("size")
                        sha = f.get("sha256")
                        self.tree.insert("", "end", values=(name, size, sha))
                    self.log_msg("File list refreshed")
                else:
                    self.log_msg(f"Unexpected list response: {resp}")
            except Exception as e:
                self.log_msg(f"Refresh failed: {e}")

        threading.Thread(target=work, daemon=True).start()

    def upload_file_dialog(self):
        path = filedialog.askopenfilename()
        if not path:
            return
        remote_name = None
        # optional prompt for remote name
        if messagebox.askyesno(
            "Remote name",
            "Use original filename as remote name? (No = choose different name)",
        ):
            remote_name = None
        else:
            remote_name = tk.simpledialog.askstring(
                "Remote name", "Enter remote name (leave blank to use original):"
            )

        def progress(sent, total):
            self.set_progress(sent, total)

        def work():
            try:
                self.set_progress(0, 100)
                self.log_msg(f"Uploading {path}...")
                result = self.client.upload_file(
                    path, remote_name, progress_callback=progress
                )
                self.log_msg(f"Upload result: {result}")
                self.refresh_list()
            except Exception as e:
                self.log_msg(f"Upload failed: {e}")
            finally:
                self.set_progress(0, 100)

        threading.Thread(target=work, daemon=True).start()

    def _get_selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        values = self.tree.item(sel[0], "values")
        if not values:
            return None
        return values[0]

    def download_selected(self):
        name = self._get_selected()
        if not name:
            messagebox.showinfo("Download", "Please select a file to download")
            return
        local = filedialog.asksaveasfilename(initialfile=name)
        if not local:
            return

        def progress(received, total):
            self.set_progress(received, total)

        def work():
            try:
                self.set_progress(0, 100)
                self.log_msg(f"Downloading {name} -> {local} ...")
                res = self.client.download_file(name, local, progress_callback=progress)
                self.log_msg(f"Download finished: {res}")
            except Exception as e:
                self.log_msg(f"Download failed: {e}")
            finally:
                self.set_progress(0, 100)

        threading.Thread(target=work, daemon=True).start()

    def delete_selected(self):
        name = self._get_selected()
        if not name:
            messagebox.showinfo("Delete", "Please select a file to delete")
            return
        if not messagebox.askyesno("Delete", f"Delete remote file '{name}'?"):
            return

        def work():
            try:
                self.log_msg(f"Deleting {name}...")
                res = self.client.delete_file(name)
                self.log_msg(f"Delete result: {res}")
                self.refresh_list()
            except Exception as e:
                self.log_msg(f"Delete failed: {e}")

        threading.Thread(target=work, daemon=True).start()


def main():
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    path = DEFAULT_PATH
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except Exception:
            port = DEFAULT_PORT
    if len(sys.argv) > 3:
        try:
            path = int(sys.argv[3])
        except Exception:
            path = DEFAULT_PATH

    app = App(host, port, path)
    app.mainloop()


if __name__ == "__main__":
    main()
