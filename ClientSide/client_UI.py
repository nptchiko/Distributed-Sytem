# This is new UI client code with improved structure and features.
# Designed by Ngoc Huy
# Imported and modified logic by Quang Minh
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dfs_client import DFSClient, DFSProtocolError
from VideoPreviewPlayer import VideoPreviewPlayer
import threading
import time
import os
import io
import pygame  # -> de xu li am thanh
import tempfile
from PIL import Image, ImageTk

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_PATH = "storage/"


class FileClientApp:
    def __init__(self, root, host=DEFAULT_HOST, port=DEFAULT_PORT, path=DEFAULT_PATH):
        self.root = root
        self.root.title("Distributed File System")
        self.root.geometry("1200x950")

        self.host = host
        self.port = port
        self.path = path
        self.client = DFSClient(self.host, self.port)
        self.worker_lock = threading.Lock()

        pygame.mixer.init()

        self.client = None
        self.is_connected = False

        self.colors = {
            "primary": "#2c3e50",
            "secondary": "#ecf0f1",
            "accent": "#3498db",
            "text": "#2c3e50",
            "white": "#ffffff",
        }

        self.setup_styles()
        self.create_layout()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")  # 'clam' cho phép tùy chỉnh màu tốt nhất

        # --- MÀU SẮC ---
        bg_color = self.colors["secondary"]
        header_bg = self.colors["primary"]
        accent_color = self.colors["accent"]
        text_color = self.colors["text"]

        # --- GENERAL ---
        style.configure("TFrame", background=bg_color)
        style.configure(
            "TLabel", background=bg_color, foreground=text_color, font=("Segoe UI", 10)
        )
        style.configure(
            "Header.TLabel",
            background=header_bg,
            foreground="white",
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Card.TFrame", background="white", relief="flat"
        )  # Card nền trắng

        # --- TREEVIEW (QUAN TRỌNG) ---
        # Tăng chiều cao dòng lên 30px cho thoáng
        style.configure(
            "Treeview",
            font=("Segoe UI", 10),
            rowheight=35,
            background="white",
            fieldbackground="white",
            borderwidth=0,
        )

        # Header của bảng
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background="#ecf0f1",
            foreground="#2c3e50",
            relief="flat",
        )

        # Màu khi chọn (Selection)
        style.map(
            "Treeview",
            background=[("selected", accent_color)],
            foreground=[("selected", "white")],
        )

        self.icons = {}
        self.load_icons()

    # def setup_styles(self):
    #     # ... (Your existing styles code remain exactly the same) ...
    #     style = ttk.Style()
    #     style.theme_use("clam")

    #     style.configure("TFrame", background=self.colors["secondary"])
    #     style.configure(
    #         "TLabel",
    #         background=self.colors["secondary"],
    #         foreground=self.colors["text"],
    #         font=("Segoe UI", 10),
    #     )
    #     style.configure("TButton", font=("Segoe UI", 10), padding=6)
    #     style.configure(
    #         "Header.TLabel",
    #         background=self.colors["primary"],
    #         foreground=self.colors["white"],
    #         font=("Segoe UI", 20, "bold"),
    #     )
    #     style.configure("Card.TFrame", background=self.colors["white"], relief="flat")
    #     style.configure(
    #         "Treeview",
    #         font=("Segoe UI", 10),
    #         rowheight=25,
    #         background="white",
    #         fieldbackground="white",
    #     )
    #     style.configure(
    #         "Treeview.Heading",
    #         font=("Segoe UI", 10, "bold"),
    #         background="#bdc3c7",
    #         foreground=self.colors["text"],
    #     )
    #     style.map(
    #         "TButton",
    #         background=[("active", self.colors["accent"]), ("!disabled", "#bdc3c7")],
    #     )
    #     self.icons = {}
    #     self.load_icons()
    # Hàm tạo nút bấm đẹp (CTA - Call To Action)
    def create_cta_btn(self, parent, text, cmd, bg_color="#3498db"):
        btn = tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg_color,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            bd=0,  # Không viền
            padx=20,
            pady=8,  # Đệm nút rộng ra
            cursor="hand2",
            activebackground="#2980b9",  # Màu khi nhấn đậm hơn chút
            activeforeground="white",
        )
        return btn
        self.icons = {}
        self.load_icons()

    def load_icons(self):
        self.icons["file"] = tk.PhotoImage(file="./assets/ic_file.png")
        self.icons["folder"] = tk.PhotoImage(file="./assets/ic_dir.png")
        self.icons["image"] = tk.PhotoImage(file="./assets/ic_image.png")
        self.icons["sound"] = tk.PhotoImage(file="./assets/ic_sound.png")
        self.icons["video"] = tk.PhotoImage(file="./assets/ic_video.png")
        self.icons["zip"] = tk.PhotoImage(file="./assets/ic_zip.png")
        self.icons["docs"] = tk.PhotoImage(file="./assets/ic_text.png")

    def _get_icon(self, file_path):
        """Return a specific icon based on file extension, or a default."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext in [".jpg", ".jpeg", ".png", ".gif"]:
            return self.icons.get("image")

        if ext in [".mp4", ".mkv", ".webm", ".flv"]:
            return self.icons.get("video")

        if ext in [".mp3", ".m4p", ".m4a", ".flac"]:
            return self.icons.get("sound")

        if ext in [".txt", ".pdf", ".doc", ".docx"]:
            return self.icons.get("docs")

        if ext in [".rar", ".zip"]:
            return self.icons.get("zip")
        # Add more rules here for video, text, etc.
        return self.icons.get("file")

    # Author: Tien
    #### EXAMPLE
    #    {
    #   "name": "storage",
    #   "path": "storage/",
    #   "subdirectories": [
    #     {
    #       "name": "dir1",
    #       "path": "storage/dir1",
    #       "subdirectories": [],
    #       "files": [
    #         {
    #           "name": "text.txt",
    #           "path": "storage/dir1/text.txt"
    #         }
    #
    #     }
    #   ],
    #   "files": [
    #     {
    #       "name": "0dca72984a2f14751488c6b37068ca2e.jpg",
    #       "path": "storage/0dca72984a2f14751488c6b37068ca2e.jpg"
    #     },
    #     {
    #       "name": "Video_2025-11-15_01-49-29.mp4",
    #       "path": "storage/a.mp4"
    #     }
    #   ]
    # }
    #

    def populate_tree(self, parent, data: dict):

        # Assuming 'data' is a list of dicts with 'name' and 'children' keys

        name = data.get("name")
        path = data.get("path")
        subdir: list = data.get("subdirectories")
        files: list = data.get("files")
        self.tree.tag_configure("even", background="#f7f9fa")
        self.tree.tag_configure("odd", background="white")
        directory_icon = self.icons.get("folder")

        directory_node = {"text": " " + name, "values": ("--", "Folder")}

        if directory_icon:
            directory_node["image"] = directory_icon

        node = self.tree.insert(parent, "end", **directory_node)

        if subdir is not []:
            for dir in subdir:
                self.populate_tree(node, dir)

        for file in files:
            file_name = file.get("name") or "Untitled"
            # file_path = file.get("path")
            raw_size = file.get("size", 0)
            size_str = self._format_size(raw_size)
            # kind_str = self._get_kind_str(file_name)
            kind_str = self._get_kind(file_name)
            file_icon = self._get_icon(file_name)
            tag = "even" if self.row_count % 2 == 0 else "odd"
            file_node = {
                "text": " " + file_name,
                "image": file_icon,
                "values": (size_str, kind_str),
                "tags": (tag),
            }
            self.row_count += 1
            self.tree.insert(node, tk.END, **file_node)

    def create_layout(self):
        # ... (Keep Header and Left Frame code exactly the same until 'File Response List') ...

        # --- HEADER ---
        header_frame = tk.Frame(self.root, bg=self.colors["primary"], height=80)
        header_frame.pack(side="top", fill="x")
        header_frame.pack_propagate(False)

        lbl_title = ttk.Label(
            header_frame, text="Distributed File System", style="Header.TLabel"
        )
        lbl_title.pack(side="left", padx=20, pady=20)

        toolbar_frame = tk.Frame(header_frame, bg=self.colors["primary"])
        toolbar_frame.pack(side="right", padx=20)

        self.btn_connect = self.create_toolbar_btn(
            toolbar_frame, "Connect", "▶", self.on_connect
        )
        self.btn_disconnect = self.create_toolbar_btn(
            toolbar_frame, "Disconnect", "■", self.on_disconnect
        )
        self.btn_disconnect.config(state="disabled")
        self.create_toolbar_btn(toolbar_frame, "Refresh", "⟳", self.refresh_list)
        self.create_toolbar_btn(toolbar_frame, "Exit", "✖", self.root.quit)

        # --- BODY ---

        body_frame = ttk.Frame(self.root, padding=20)
        body_frame.pack(fill="both", expand=True)

        left_frame = ttk.Frame(body_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 20))

        input_card = ttk.Frame(left_frame, style="Card.TFrame", padding=15)
        input_card.pack(fill="x", pady=(0, 15))
        input_card.columnconfigure(1, weight=1)

        ttk.Label(input_card, text="Status:", background="white").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.entry_status = ttk.Entry(input_card, width=20)
        self.entry_status.insert(0, "Disconnected")
        self.entry_status.config(state="readonly")
        self.entry_status.grid(row=0, column=1, sticky="w", padx=10)

        ttk.Label(input_card, text="Host IP:", background="white").grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.host_var_entry = ttk.Entry(input_card)
        self.host_var_entry.insert(0, self.host)
        self.host_var_entry.grid(row=1, column=1, sticky="ew", padx=10)

        ttk.Label(input_card, text="Port:", background="white").grid(
            row=2, column=0, sticky="w", pady=5
        )
        self.port_var_entry = ttk.Entry(input_card)
        self.port_var_entry.insert(0, str(self.port))
        self.port_var_entry.grid(row=2, column=1, sticky="ew", padx=10)

        ttk.Label(input_card, text="Request:", background="white").grid(
            row=3, column=0, sticky="w", pady=5
        )
        req_sub_frame = ttk.Frame(input_card, style="Card.TFrame")
        req_sub_frame.grid(row=3, column=1, sticky="ew", padx=10)

        self.entry_req = ttk.Entry(req_sub_frame)
        self.entry_req.pack(side="left", fill="x", expand=True)
        ttk.Button(
            req_sub_frame, text="Browse", width=8, command=self.browse_folder
        ).pack(side="right", padx=(5, 0))

        action_frame = ttk.Frame(input_card, style="Card.TFrame")
        action_frame.grid(row=4, column=1, sticky="w", padx=10, pady=10)
        ttk.Button(action_frame, text="SEND REQUEST", command=self.on_send_click).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(action_frame, text="DOWNLOAD", command=self.on_download_click).pack(
            side="left"
        )
        ttk.Button(action_frame, text="UPLOAD", command=self.on_upload_click).pack(
            side="left", padx=(5, 0)
        )

        ttk.Label(
            left_frame, text="File Response List", font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 5))

        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill="both", expand=True)

        tree_scroll = ttk.Scrollbar(tree_frame)
        self.tree = ttk.Treeview(
            tree_frame,
            yscrollcommand=tree_scroll.set,
            height=10,
            columns=("size", "kind"),
        )
        tree_scroll.config(command=self.tree.yview)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.tree.heading("#0", text="Folder / File Name", anchor="w")
        self.tree.column("#0", width=300)
        self.tree.heading("size", text="Size", anchor="w")
        self.tree.column("size", width=100, anchor="w")
        self.tree.heading("kind", text="Type", anchor="w")
        self.tree.column("kind", width=100, anchor="w")
        # --- RIGHT FRAME (Modified for Preview) ---
        right_frame = ttk.Frame(body_frame, style="Card.TFrame", padding=15)
        right_frame.pack(side="right", fill="y", anchor="n")

        ttk.Label(
            right_frame,
            text="Filter Options",
            font=("Segoe UI", 12, "bold"),
            background="white",
        ).pack(anchor="w", pady=(0, 15))

        self.check_vars = {}
        options = [
            "All files",
            "Image files",
            "Video files",
            "Text files",
            "Sound files",
            "Compressed files",
        ]

        for opt in options:
            var = tk.IntVar()
            if opt == "All files":
                var.set(1)
            chk = ttk.Checkbutton(
                right_frame, text=opt, variable=var, style="TCheckbutton"
            )

            style = ttk.Style()
            style.configure("TCheckbutton", background="white", font=("Segoe UI", 10))
            chk.pack(fill="x", pady=2, anchor="w")
            self.check_vars[opt] = var

        ttk.Separator(right_frame, orient="horizontal").pack(fill="x", pady=(10, 5))

        ttk.Label(right_frame, text="Custom Extensions:", background="white").pack(
            anchor="w", pady=(0, 5)
        )
        self.entry_ext = ttk.Entry(right_frame)
        self.entry_ext.pack(fill="x")
        ttk.Label(
            right_frame,
            text="(e.g. .pnj; .pdf)",
            font=("Segoe UI", 8, "italic"),
            background="white",
            foreground="#7f8c8d",
        ).pack(anchor="w")

        # Log Box Area
        ttk.Label(
            right_frame,
            text="System Log:",
            font=("Segoe UI", 10, "bold"),
            background="white",
        ).pack(anchor="w")
        self.log_text = tk.Text(right_frame, height=10, width=30, font=("Consolas", 8))
        self.log_text.pack(fill="both", expand=True, pady=(5, 0))
        self.log_text.config(state="disabled")

        # Handle event when a file is selected
        self.tree.bind("<<TreeviewSelect>>", self.on_file_select)

        ### PREVIEW SECTION
        ttk.Label(
            right_frame,
            text="File Preview",
            font=("Segoe UI", 12, "bold"),
            background="white",
        ).pack(anchor="w", pady=(0, 10))

        self.preview_container = tk.Frame(
            right_frame, bg="white", height=250, width=250
        )
        self.preview_container.pack(fill="both", expand=True)
        self.preview_container.pack_propagate(False)  # Force size

        # Label for Image Previews
        self.lbl_preview_img = tk.Label(
            self.preview_container, bg="#ecf0f1", text="No Preview"
        )
        self.lbl_preview_img.place(relx=0.5, rely=0.5, anchor="center")
        self.lbl_preview_img.pack(fill="both", expand=True)

        # Text Widget for Text Previews (Initially Hidden)
        self.txt_preview = tk.Text(
            self.preview_container, height=15, width=30, font=("Consolas", 8)
        )
        self.video_player = VideoPreviewPlayer(self.lbl_preview_img)

    # ---- UI helpers ----
    # Author: Quang Minh
    # Function: log_msg
    # Description: Log a message to the log text area with timestamp
    def log_msg(self, s: str):
        self.log_text.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {s}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # Author: Quang Minh
    # Function: browse_folder
    # Description: Open a dialog to browse folder and set the path to entry_req
    def set_status(self, s: str):
        self.entry_status.config(state="normal")
        self.entry_status.delete(0, tk.END)
        self.entry_status.insert(0, s)
        self.entry_status.config(state="readonly")

    def set_request(self, s: str):

        self.entry_req.config(state="normal")
        self.entry_req.delete(0, tk.END)
        self.entry_req.insert(0, s)
        self.entry_req.config(state="readonly")

    # Author: Quang Minh
    # Function: browse_folder
    # Description: Open a dialog to browse folder and set the path to entry_req
    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_req.delete(0, tk.END)
            self.entry_req.insert(0, path)

    # Author: Quang Minh
    # Function: create_toolbar_btn
    # Description: Create a toolbar button with icon and text
    def create_toolbar_btn(self, parent, text, icon, cmd):
        # Màu sắc từ cấu hình
        default_bg = self.colors["primary"]  # Màu nền trùng với Header (#2c3e50)
        hover_bg = "#34495e"  # Màu khi di chuột (Sáng hơn một chút)
        text_color = self.colors["white"]

        btn = tk.Button(
            parent,
            text=f"{icon}  {text}",
            command=cmd,
            bg=default_bg,  # Nền mặc định tệp với header
            fg=text_color,  # Màu chữ trắng
            bd=0,  # Không viền (Border = 0)
            padx=20,  # Khoảng cách ngang rộng hơn cho thoáng
            pady=10,  # Chiều cao nút
            activebackground=hover_bg,  # Màu khi click
            activeforeground=text_color,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",  # Con trỏ hình bàn tay
            relief="flat",  # Kiểu nút phẳng
        )

        # --- HIỆU ỨNG HOVER (Di chuột vào đổi màu) ---
        def on_enter(e):
            btn.config(bg=hover_bg)

        def on_leave(e):
            btn.config(bg=default_bg)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

        btn.pack(side="left", padx=1)

        return btn

    # def create_toolbar_btn(self, parent, text, icon, cmd):
    #     btn = tk.Button(
    #         parent,
    #         text=f"{icon}  {text}",
    #         command=cmd,
    #         bg="#34495e",
    #         fg="white",
    #         bd=0,
    #         padx=15,
    #         pady=5,
    #         activebackground="#2c3e50",
    #         activeforeground="white",
    #         font=("Segoe UI", 9, "bold"),
    #     )
    #     btn.pack(side="left", padx=5)
    #     return btn

    # Author: Quang Minh
    # Function: browse_folder
    # Description: Open a dialog to browse folder and set the path to entry_req
    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_req.delete(0, tk.END)
            self.entry_req.insert(0, path)

    # ---- Connection actions ----
    # Author: Quang Minh
    # Function: on_connect
    # Description: Handle connect button click, establish connection in a separate thread
    def on_connect(self):
        host = self.host_var_entry.get().strip() or DEFAULT_HOST
        try:
            port = int(self.port_var_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Port must be an integer")
            return

        self.set_status("Connecting...")
        self.log_msg(f"Connecting to {host}:{port}...")

        def work():
            try:
                # Init client and connect
                self.client = DFSClient(host, port)
                self.client.connect(timeout=5)

                # update UI on main thread
                self.root.after(0, lambda: self._connect_success(host, port))

                # Initial file list refresh
                # self.refresh_list()

            except Exception as e:
                self.root.after(0, lambda: self._connect_failed(str(e)))

        threading.Thread(target=work, daemon=True).start()

    # Author: Quang Minh
    # Function: _connect_success
    # Description: Update UI on successful connection
    def _connect_success(self, host, port):
        self.is_connected = True
        self.set_status(f"Connected {host}:{port}")
        self.log_msg("Connection successful.")
        self.btn_connect.config(state="disabled")
        self.btn_disconnect.config(state="normal")

    # Author: Quang Minh
    # Function: _connect_failed
    # Description: Update UI on failed connection
    def _connect_failed(self, error_msg):
        self.is_connected = False
        self.set_status("Disconnected")
        self.log_msg(f"Error: {error_msg}")
        messagebox.showerror("Connection Failed", error_msg)

    # Author: Quang Minh
    # Function: on_disconnect
    # Description: Handle disconnect button click, close connection
    def on_disconnect(self):
        try:
            self.client.close()
        except Exception:
            pass
        self.btn_connect.configure(state="normal")
        self.btn_disconnect.configure(state="disabled")
        self.set_status("Disconnected")
        self.log_msg("Disconnected")

    # Author: Quang Minh
    # Function: _get_active_filters
    # Description:
    def _get_active_filters(self):
        """Chuyển đổi trạng thái checkbox thành list filters cho server"""
        filters = []
        if self.check_vars["All files"].get():
            filters.append("all")
        if self.check_vars["Image files"].get():
            filters.append("image")
        if self.check_vars["Video files"].get():
            filters.append("video")
        if self.check_vars["Text files"].get():
            filters.append("text")
        if self.check_vars["Sound files"].get():
            filters.append("sound")
        if self.check_vars["Compressed files"].get():
            filters.append("compressed")

        # Nếu không chọn gì cả, mặc định là all
        if not filters:
            filters = ["all"]
        return filters

    # ---- Request actions ----
    # Author: Quang Minh
    # Function: on_send_click
    # Description: Handle Send Request button click
    def on_send_click(self):
        if not self.is_connected:
            messagebox.showwarning(
                "Not Connected", "Please connect to the server first."
            )
            return

        local_path = filedialog.askopenfilename(
            title="Select File to Upload",
            filetypes=[("All Files", "*.*")],
        )

        if not local_path:
            return  # User cancelled

        remote_name_str = self.entry_req.get()
        remote_name = remote_name_str if remote_name_str.strip() else None

        # Use a thread to avoid blocking the UI
        threading.Thread(
            target=self._execute_upload, args=(local_path, remote_name), daemon=True
        ).start()

    # def _execute_download(self, remote_path, local_path):
    #     """Helper function to run the download in a separate thread."""
    #     try:
    #         if not self.client:
    #             # This should not happen if is_connected is true, but as a safeguard
    #             raise Exception("Client not initialized.")
    #
    #         result = self.client.download_file(remote_path, local_path)
    #
    #         if result and result.get("payload", {}).get("ok"):
    #             self.root.after(
    #                 0,
    #                 lambda: messagebox.showinfo(
    #                     "Success",
    #                     f"File '{os.path.basename(remote_path)}' downloaded successfully.",
    #                 ),
    #             )
    #         else:
    #             error_msg = result.get("payload", {}).get(
    #                 "error", "Unknown download error."
    #             )
    #             self.root.after(
    #                 0,
    #                 lambda: messagebox.showerror(
    #                     "Download Failed",
    #                     f"Failed to download '{os.path.basename(remote_path)}': {error_msg}",
    #                 ),
    #             )
    #     except Exception as e:
    #         self.root.after(
    #             0,
    #             lambda: messagebox.showerror(
    #                 "Download Error", f"An error occurred during download: {e}"
    #             ),
    #         )
    #     """Nút Send Request: Thực chất là gửi lệnh List với các Filter đã chọn"""
    #     if not self.is_connected:
    #         messagebox.showwarning("Warning", "Please connect to server first.")
    #         return
    #     self.refresh_list()
    #
    # ---- File operations ----
    # Author: Quang Minh
    # Function: refresh_list
    # Description: Refresh the file list from server based on active filters
    # def refresh_list(self):
    #     if not self.is_connected:
    #         return

    #     filters = self._get_active_filters()
    #     self.log_msg(f"Requesting list. Filters: {filters}")

    #     def work():
    #         try:

    #             for i in self.tree.get_children():
    #                 self.tree.delete(i)
    #             # Call list_files with filters
    #             resp = self.client.list_files(filter=filters)
    #             if resp and resp.get("type") == "list":  # Server returned file list
    #                 files = resp["payload"].get("files", [])
    #                 # Update request
    #                 self.set_request(f"{DEFAULT_PATH}")
    #                 # Update treeview on main thread
    #                 self.root.after(0, lambda: self.populate_tree("", resp["payload"]))

    #             elif resp and resp.get("type") == "error":
    #                 msg = resp.get("payload")
    #                 self.root.after(0, lambda: self.log_msg(f"Server Error: {msg}"))
    #             else:

    #                 self.root.after(
    #                     0, lambda: self.log_msg(f"Unknown response: {resp}")
    #                 )

    #         except Exception as e:
    #             self.root.after(0, lambda e=e: self.log_msg(f"List failed: {e}"))

    # threading.Thread(target=work, daemon=True).start()
    # Author: Quang Minh
    # Function: refresh_list
    # Description: Lấy danh sách thật từ Server và hiển thị với giao diện đẹp
    def refresh_list(self):
        if not self.is_connected:
            # Thêm thông báo nếu chưa kết nối
            messagebox.showwarning("Warning", "Please connect to server first.")
            return

        filters = self._get_active_filters()
        self.log_msg(f"Requesting list. Filters: {filters}")

        def work():
            try:
                # 1. Gửi request lên Server (vẫn giữ nguyên logic cũ)
                resp = self.client.list_files(filter=filters)

                # 2. Xử lý kết quả
                if resp and resp.get("type") == "list":  # Server returned file list
                    payload = resp["payload"]  # Lấy dữ liệu thực

                    # --- CẬP NHẬT GIAO DIỆN (Main Thread) ---
                    def update_ui():
                        # a. Xóa dữ liệu cũ trên cây
                        for i in self.tree.get_children():
                            self.tree.delete(i)

                        # b. [QUAN TRỌNG] Reset biến đếm màu về 0
                        # (Để tính năng tô màu xen kẽ hoạt động đúng từ dòng đầu tiên)
                        self.row_count = 0

                        # c. Đổ dữ liệu thật vào cây (Gọi đệ quy)
                        self.populate_tree("", payload)

                        # d. Cập nhật thanh trạng thái
                        self.set_request(f"{DEFAULT_PATH}")
                        self.log_msg("File list updated.")

                    # Đẩy việc cập nhật UI về luồng chính
                    self.root.after(0, update_ui)

                elif resp and resp.get("type") == "error":
                    msg = resp.get("payload")
                    self.root.after(0, lambda: self.log_msg(f"Server Error: {msg}"))
                else:

                    self.root.after(
                        0, lambda: self.log_msg(f"Unknown response: {resp}")
                    )

            except Exception as e:
                self.root.after(0, lambda e=e: self.log_msg(f"List failed: {e}"))

        threading.Thread(target=work, daemon=True).start()

    #
    # # Author: Quang Minh
    # # Function: _update_treeview
    # # Description: Update the file list in the treeview
    # def _update_treeview(self, files):
    #     self.tree.delete(*self.tree.get_children())
    #     if not files:
    #         self.log_msg("No files found.")
    #         return
    #
    #     for i, f in enumerate(files):
    #         name = f.get("name", "Unknown")
    #         size = f.get("size", 0)
    #         sha = f.get("sha256", "")
    #
    #         tag = "odd" if i % 2 != 0 else "even"
    #         # Insert vào treeview
    #         self.tree.insert("", "end", text=name, values=(size, sha), tags=(tag,))
    #
    #     self.log_msg(f"Updated list with {len(files)} files.")

    # Author: Ngoc Huy
    # Function: on_download_click
    # Description: Handle file download with safe directory creation and threading
    def on_download_click(self):
        if not self.is_connected or not self.client:
            messagebox.showwarning("Cảnh Báo", "Hãy kết nối với sever trước khi tải !")
            return

        selected_item = self.tree.selection()

        if not selected_item:
            messagebox.showwarning("Cảnh Báo", "Hãy chọn file bạn muốn tải !")
            return
        print(len(selected_item))
        file_name = self.tree.item(selected_item[0])["text"]
        file_name = file_name.removeprefix(" ")
        print(file_name)

        local_path = filedialog.asksaveasfilename(
            title="Save File", initialfile=file_name, defaultextension=".*"
        )

        if not local_path:
            return

        self.log_msg(f"Starting download: {file_name} -> {local_path}")

        def work():
            try:
                directory = os.path.dirname(local_path)

                if directory and not os.path.exists(directory):
                    os.makedirs(directory)
                    self.root.after(
                        0, lambda: self.log_msg(f"Created directory: {directory}")
                    )
                ### FIX
                ### Author: chiko
                ### Description: handle khi tải file trong folder

                remote_path = ""  # -> storage
                child_id = selected_item[0]
                parent_id = self.tree.parent(child_id)

                while child_id:
                    remote_path = os.path.join(
                        self.tree.item(child_id, "text").removeprefix(" "), remote_path
                    )
                    child_id = parent_id
                    parent_id = self.tree.parent(child_id)

                # Xoa dau / cuoi
                remote_path = remote_path[:-1]

                self.set_request(remote_path)
                print(f"remote path: {remote_path}")

                self.client.download_file(remote_path, local_path)

                # Cập nhật UI khi thành công
                self.root.after(
                    0, lambda: self.log_msg(f"Download success: {file_name}")
                )
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success", f"File downloaded successfully to:\n{local_path}"
                    ),
                )

            except Exception as e:

                # Cập nhật UI khi lỗi
                error_msg = str(e)

                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error", f"Failed to download file:\n {error_msg}"
                    ),
                )
                self.root.after(
                    0, lambda: self.log_msg(f"Download failed: {error_msg}")
                )

        threading.Thread(target=work, daemon=True).start()

    # ---  Hàm chuyển đổi kích thước file sang KB/MB ---
    def _format_size(self, size_in_bytes):
        if not size_in_bytes:
            return "--"
        try:
            size = float(size_in_bytes)
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        except (ValueError, TypeError):
            return "0 B"

    def on_upload_click(self):
        if not self.is_connected:
            messagebox.showwarning(
                "Not Connected", "Please connect to the server first."
            )
            return

        local_path = filedialog.askopenfilename(
            title="Select File to Upload",
            filetypes=[("All Files", "*.*")],
        )

        if not local_path:
            return  # User cancelled

        remote_name_str = self.entry_req.get()
        remote_name = remote_name_str if remote_name_str.strip() else None

        def work():
            try:
                self.client.upload_file(local_path, remote_name)
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success",
                        f"File '{os.path.basename(local_path)}' uploaded successfully.",
                    ),
                )
            except Exception as e:
                self.root.after(
                    0,
                    lambda e=e: messagebox.showerror(
                        "Upload Failed",
                        f"Failed to upload '{os.path.basename(local_path)}': {e}",
                    ),
                )

        threading.Thread(target=work, daemon=True).start()

    # Author: Ngoc Huy
    # Function: _get_full_remote_path
    # Description: Dùng để lấy full path từ node con
    def _get_full_remote_path(self, item_id):
        path_parts = []
        current_id = item_id

        while current_id:
            item_text = self.tree.item(current_id, "text")
            clean_name = item_text.lstrip()
            path_parts.insert(0, clean_name)
            current_id = self.tree.parent(current_id)
        return "/".join(path_parts)

    # Author: Ngoc Huy
    # Function: on_file_select
    # Description:
    def on_file_select(self, event):

        self.stop_audio()
        self.video_player.stop()

        if not self.is_connected:
            return
        selected_items = self.tree.selection()
        if not selected_items:
            return

        selected_id = selected_items[0]
        full_path = self._get_full_remote_path(selected_id)
        if "." not in os.path.basename(full_path):
            return

        self.set_request(full_path)

        self.txt_preview.pack_forget()
        self.lbl_preview_img.place(relx=0.5, rely=0.5, anchor="center")
        self.lbl_preview_img.config(
            image="", text=f"Loading...\n{os.path.basename(full_path)}"
        )
        # Author: Quang Minh
        # FIX: Call fetch_preview_data in a separate thread to avoid blocking UI
        # OLD:
        # threading.Thread(target=self.fetch_preview_data, args=(full_path,), daemon=True).start()
        # NEW:
        self.fetch_preview_data(full_path)

    # Author: chiko
    # Description: Lay file am thanh tu client roi update UI
    # Function: play_audio_data
    def stop_audio(self):
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

    def play_audio_data(self, data):

        try:
            self.stop_audio()  # Stop any previous song

            # Use io.BytesIO to treat raw bytes like a file
            audio_file = io.BytesIO(data)

            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Audio playback error: {e}")
            self.lbl_preview_img.config(text="Audio Error")

    # Author: Ngoc Huy
    # Function: on_file_select
    # Description:
    def fetch_preview_data(self, remote_path):
        # Author: Quang Minh
        # Fix: Implement timeout mechanism using threading
        # Shared state to track if result is ready
        # OLD:
        # try:
        #     data, file_type = self.client.preview_file(remote_path)
        #     self.update_ui_preview(data, file_type)
        # except Exception as e:
        #     messagebox.showerror("Preview Error", f"Failed to preview file:\n {e}")
        # NEW:
        # Shared state to track if result is ready
        result_state = {"finished": False}
        data_lock = threading.Lock()

        def timer_task():
            time.sleep(5)  # Ngủ đúng 5 giây

            with data_lock:
                # Dậy kiểm tra xem Worker xong chưa
                if not result_state["finished"]:
                    # Nếu chưa xong -> Đánh dấu là đã xong (để chặn Worker update sau này)
                    result_state["finished"] = True

                    # Update UI báo lỗi Timeout -> Ngắt luồng hiển thị
                    self.root.after(
                        0,
                        lambda: self.update_ui_preview(
                            None, None, error="Preview Timeout (5s)"
                        ),
                    )
                    # Lưu ý: Thread worker vẫn có thể chạy ngầm đến khi socket timeout,
                    # nhưng kết quả của nó sẽ bị bỏ qua nhờ biến 'finished'.

        def work():
            try:
                data, file_type = self.client.preview_file(remote_path)
                with data_lock:
                    # Kiểm tra xem đã timeout chưa
                    if result_state["finished"]:
                        return  # Đã timeout, bỏ qua kết quả này

                    # Đánh dấu là đã hoàn thành
                    result_state["finished"] = True
                    # Cập nhật UI từ luồng chính
                    self.root.after(0, lambda: self.update_ui_preview(data, file_type))

            except Exception as e:
                with data_lock:
                    if result_state["finished"]:
                        return
                    result_state["finished"] = True
                self.root.after(
                    0,
                    lambda e=e: messagebox.showerror(
                        "Preview Error", f"Failed to preview file:\n {e}"
                    ),
                )

        threading.Thread(target=timer_task, daemon=True).start()
        threading.Thread(target=work, daemon=True).start()

    def update_ui_preview(self, data, p_type):
        """
        Called by the thread to update the UI safely.
        """
        # pass

        if not data:
            self.lbl_preview_img.config(text="No Data")
            return

        if p_type == "image" and data:
            try:
                # Load image from bytes
                pil_image = Image.open(io.BytesIO(data))

                # Resize to fit container (250x250)
                pil_image.thumbnail((240, 240))
                tk_img = ImageTk.PhotoImage(pil_image)

                # Update Label
                self.current_image = tk_img  # Keep reference!
                self.lbl_preview_img.config(image=tk_img, text="")
            except Exception:
                self.lbl_preview_img.config(image="", text="Image Error")
        # ================= TRƯỜNG HỢP: ẢNH =================

        elif p_type == "text" and data:
            self.lbl_preview_img.pack_forget()
            self.txt_preview.pack(fill="both", expand=True)
            self.txt_preview.delete("1.0", tk.END)
            self.txt_preview.insert("1.0", data.decode("utf-8"))

        elif p_type == "audio" and data:
            self.lbl_preview_img.pack(fill="both", expand=True)
            # You can replace this text with a "Music Note" icon if you have one
            self.lbl_preview_img.config(
                image="", text="🎵\nPlaying Audio Snippet...", font=("Segoe UI", 12)
            )
            # Play the sound
            self.play_audio_data(data)

        elif p_type == "tree" and data:
            # tree_data = json.dumps(data.decode("utf-8"))
            # self.lbl_preview_img.pack_forget()
            # self.txt_preview.pack(fill="both", expand=True)
            # self.txt_preview.delete("1.0", tk.END)
            # self.txt_preview.insert(tk.END, tree_data)
            #
            try:
                # 1. Decode JSON
                json_string = data.decode("utf-8")
                tree_data = json.loads(json_string)

                # 2. Xóa khung preview cũ
                self.lbl_preview_img.pack_forget()
                self.txt_preview.pack(fill="both", expand=True)
                self.txt_preview.delete("1.0", tk.END)

                # 3. Hàm đệ quy để vẽ cây thư mục
                def draw_tree(node, prefix="", is_last=True, is_root=True):
                    # Lấy tên file/folder
                    name = node.get("name", "Unknown")
                    
                    # Xác định icon và ký tự nối (connector)
                    if is_root:
                        connector = ""
                        child_prefix = ""
                        icon = "📦"  # Icon cho file Zip gốc
                        display_text = f"{icon} {name}\n"
                    else:
                        connector = "└── " if is_last else "├── "
                        icon = "📁"  # Icon cho Folder
                        display_text = f"{prefix}{connector}{icon} {name}\n"
                        # Cập nhật prefix cho các con của node này
                        child_prefix = prefix + ("    " if is_last else "│   ")

                    # In ra node hiện tại (Folder/Zip)
                    self.txt_preview.insert(tk.END, display_text)

                    # Lấy danh sách con (Folder và File)
                    subdirs = node.get("subdirectories") or []
                    files = node.get("files") or []
                    
                    # Gộp chung lại để xử lý vòng lặp một thể (để biết ai là phần tử cuối cùng)
                    # Tạo danh sách các item con: mỗi item là dict {type, data}
                    children = []
                    for d in subdirs:
                        children.append({"type": "dir", "data": d})
                    for f in files:
                        children.append({"type": "file", "data": f})
                    
                    count = len(children)
                    for i, child in enumerate(children):
                        is_last_child = (i == count - 1)
                        
                        if child["type"] == "dir":
                            # Gọi đệ quy nếu là Folder
                            draw_tree(child["data"], child_prefix, is_last_child, is_root=False)
                        else:
                            # In trực tiếp nếu là File
                            f_name = child["data"].get("name", "Unknown")
                            f_connector = "└── " if is_last_child else "├── "
                            
                            # Dòng hiển thị file
                            f_line = f"{child_prefix}{f_connector}📄 {f_name}\n"
                            self.txt_preview.insert(tk.END, f_line)

                # 4. Bắt đầu vẽ từ node gốc
                draw_tree(tree_data, is_root=True)

            except Exception as e:
                self.txt_preview.insert(tk.END, f"Error parsing ZIP tree: {e}")
                
        elif p_type == "video" and data:
            try:
                # Write data to temp file
                self.temp_video = tempfile.NamedTemporaryFile(
                    suffix=".mp4", delete=False
                )
                self.temp_video.write(data)
                self.temp_video.close()

                # Load and Play
                self.video_player.load(self.temp_video.name)
                self.video_player.play()

            except Exception as e:
                print(f"Video error: {e}")
                self.lbl_preview_img.config(text="Video Error")
        else:
            self.lbl_preview_img.config(image="", text="No Preview Available")

    # ---  Hàm xác định loại file ---
    def _get_kind(self, filename, is_folder=False):
        if is_folder:
            return "Folder"

        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        kind_map = {
            ".jpg": "JPEG Image",
            ".jpeg": "JPEG Image",
            ".png": "PNG Image",
            ".gif": "GIF Image",
            ".mp4": "MPEG-4 Video",
            ".mkv": "Matroska Video",
            ".avi": "AVI Video",
            ".mp3": "MP3 Audio",
            ".wav": "WAV Audio",
            ".txt": "Text Document",
            ".pdf": "PDF Document",
            ".doc": "Word Doc",
            ".docx": "Word Doc",
            ".zip": "ZIP Archive",
            ".rar": "RAR Archive",
            ".7z": "7-Zip Archive",
        }
        return kind_map.get(ext, f"{ext.upper().replace('.', '')} File")


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.5)
    except:
        pass

    app = FileClientApp(root)
    root.mainloop()
