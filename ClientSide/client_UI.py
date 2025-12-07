import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk  # <--- NEW: Required for images
import io
import threading  # <--- NEW: To keep UI responsive
import os


from dfs_client import DFSClient

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000


class FileClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UI Client")
        self.root.geometry("1000x700")  # Slightly wider for preview

        self.client = None
        self.is_connected = False

        self.colors = {
            "primary": "#2c3e50",
            "secondary": "#ecf0f1",
            "accent": "#3498db",
            "text": "#2c3e50",
            "white": "#ffffff",
        }

        # Placeholder for the current preview image to prevent garbage collection
        self.current_image = None

        self.setup_styles()
        self.create_layout()

    def setup_styles(self):
        # ... (Your existing styles code remain exactly the same) ...
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

        directory_icon = self.icons.get("folder")

        directory_node = {"text": " " + name}

        if directory_icon:
            directory_node["image"] = directory_icon

        node = self.tree.insert(parent, "end", **directory_node)

        if subdir is not []:
            for dir in subdir:
                self.populate_tree(node, dir)

        for file in files:
            file_name = file.get("name") or "Untitled"
            file_path = file.get("path")

            file_icon = self._get_icon(file_name)

            file_node = {"text": " " + file_name, "image": file_icon}
            self.tree.insert(node, tk.END, **file_node)

    def create_layout(self):
        # ... (Keep Header and Left Frame code exactly the same until 'File Response List') ...

        # --- HEADER ---
        header_frame = tk.Frame(self.root, bg=self.colors["primary"], height=80)
        header_frame.pack(side="top", fill="x")
        header_frame.pack_propagate(False)

        lbl_title = ttk.Label(header_frame, text="CLIENT UI", style="Header.TLabel")
        lbl_title.pack(side="left", padx=20, pady=20)

        toolbar_frame = tk.Frame(header_frame, bg=self.colors["primary"])
        toolbar_frame.pack(side="right", padx=20)

        self.create_toolbar_btn(toolbar_frame, "Connect", "▶", self.on_connect_click)
        self.create_toolbar_btn(toolbar_frame, "Refresh", "⟳", self.on_refresh_click)
        self.create_toolbar_btn(toolbar_frame, "Exit", "✖", self.root.quit)

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
        self.entry_host = ttk.Entry(input_card)
        self.entry_host.grid(row=1, column=1, sticky="ew", padx=10)

        ttk.Label(input_card, text="Request:", background="white").grid(
            row=2, column=0, sticky="w", pady=5
        )
        req_sub_frame = ttk.Frame(input_card, style="Card.TFrame")
        req_sub_frame.grid(row=2, column=1, sticky="ew", padx=10)

        self.entry_req = ttk.Entry(req_sub_frame)
        self.entry_req.pack(side="left", fill="x", expand=True)
        ttk.Button(
            req_sub_frame, text="Browse", width=8, command=self.browse_folder
        ).pack(side="right", padx=(5, 0))

        action_frame = ttk.Frame(input_card, style="Card.TFrame")
        action_frame.grid(row=3, column=1, sticky="w", padx=10, pady=10)
        ttk.Button(action_frame, text="SEND REQUEST", command=self.on_send_click).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(action_frame, text="DOWNLOAD", command=self.on_download_click).pack(
            side="left"
        )

        ttk.Label(
            left_frame, text="File Response List", font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 5))

        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill="both", expand=True)

        tree_scroll = ttk.Scrollbar(tree_frame)
        self.tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, height=10)
        tree_scroll.config(command=self.tree.yview)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.tree.heading("#0", text="Folder / File Name", anchor="w")

        # --- NEW: Bind Click Event to Treeview ---
        self.tree.bind("<<TreeviewSelect>>", self.on_file_select)

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
        options = ["All files", "Image files", "Video files"]
        for opt in options:
            var = tk.IntVar()
            if opt == "All files":
                var.set(1)
            chk = ttk.Checkbutton(
                right_frame, text=opt, variable=var, style="TCheckbutton"
            )
            chk.pack(fill="x", pady=8, anchor="w")
            self.check_vars[opt] = var

        style = ttk.Style()
        style.configure("TCheckbutton", background="white", font=("Segoe UI", 10))

        ttk.Separator(right_frame, orient="horizontal").pack(fill="x", pady=20)

        # --- NEW: PREVIEW SECTION ---
        ttk.Label(
            right_frame,
            text="File Preview",
            font=("Segoe UI", 12, "bold"),
            background="white",
        ).pack(anchor="w", pady=(0, 10))

        self.preview_container = tk.Frame(
            right_frame, bg="white", height=250, width=250
        )
        self.preview_container.pack(fill="x")
        self.preview_container.pack_propagate(False)  # Force size

        # Label for Image Previews
        self.lbl_preview_img = tk.Label(
            self.preview_container, bg="#ecf0f1", text="No Preview"
        )
        self.lbl_preview_img.place(relx=0.5, rely=0.5, anchor="center")

        # Text Widget for Text Previews (Initially Hidden)
        self.txt_preview = tk.Text(
            self.preview_container, height=10, width=30, font=("Consolas", 8)
        )

        # ---------------------------

    # ... (Keep create_toolbar_btn and browse_folder the same) ...
    def create_toolbar_btn(self, parent, text, icon, cmd):
        btn = tk.Button(
            parent,
            text=f"{icon}  {text}",
            command=cmd,
            bg="#34495e",
            fg="white",
            bd=0,
            padx=15,
            pady=5,
            activebackground="#2c3e50",
            activeforeground="white",
            font=("Segoe UI", 9, "bold"),
        )
        btn.pack(side="left", padx=5)

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_req.delete(0, tk.END)
            self.entry_req.insert(0, path)

    # --- NEW: Logic to handle file selection ---
    def on_file_select(self, _):
        selected_item = self.tree.selection()
        if not selected_item:
            return

        file_name = self.tree.item(selected_item[0], "text")

        # Reset Preview Panel
        self.lbl_preview_img.config(image="", text="Loading...")
        self.txt_preview.pack_forget()
        self.lbl_preview_img.pack(fill="both", expand=True)

        # In a real app, check if it's a file or folder before requesting
        # For now, we assume everything is a file and request preview
        threading.Thread(
            target=self.fetch_preview_data, args=(file_name,), daemon=True
        ).start()

    # --- NEW: Fetch logic (Connects to your socket code) ---
    def fetch_preview_data(self, filename):
        """
        This function simulates the network request.
        Replace the logic inside with your actual socket _send_control calls.
        """
        if not self.client:
            self.update_ui_preview(None, "Not Connected")
            return

        try:
            # 1. SEND REQUEST (Using logic from previous turn)
            # _send_control(self.client_socket, {"type": "preview", "payload": {"name": filename}})

            # 2. RECEIVE RESPONSE
            # resp = _recv_control(self.client_socket)

            # SIMULATED RESPONSE FOR UI TESTING:
            import time

            time.sleep(0.5)  # Simulate network lag

            # Logic to handle response:
            # if resp['type'] == 'preview_ready':
            #    data = _recv_all(self.client_socket, resp['payload']['size'])
            #    self.root.after(0, self.update_ui_preview, data, resp['payload']['type'])

            pass
        except Exception as e:
            print(f"Preview error: {e}")

    # --- NEW: Update UI from Main Thread ---
    def update_ui_preview(self, data, p_type):
        """
        Called by the thread to update the UI safely.
        """
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

        elif p_type == "text" and data:
            self.lbl_preview_img.pack_forget()
            self.txt_preview.pack(fill="both", expand=True)
            self.txt_preview.delete("1.0", tk.END)
            self.txt_preview.insert("1.0", data.decode("utf-8"))

        else:
            self.lbl_preview_img.config(image="", text="No Preview Available")

    def on_connect_click(self):
        host = self.entry_host.get()
        if not host:
            messagebox.showinfo("Info", "Using default host as 127.0.0.1")

        try:
            self.client = DFSClient(host=host or DEFAULT_HOST)
            self.client.connect()
            self.is_connected = True
            self.entry_status.config(state="normal")
            self.entry_status.delete(0, tk.END)
            self.entry_status.insert(0, "Connected")
            self.entry_status.config(state="readonly")
            self.on_refresh_click()  # Refresh file list on connect
        except Exception as e:
            messagebox.showerror("Connection Failed", str(e))
            self.is_connected = False

    def _execute_upload(self, local_path, remote_name):
        """Helper function to run the upload in a separate thread."""
        try:
            if not self.client:
                raise Exception("Client not initialized.")

            result = self.client.upload_file(local_path, remote_name)

            if result and result.get("payload", {}).get("ok"):
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success",
                        f"File '{os.path.basename(local_path)}' uploaded successfully.",
                    ),
                )
                # Refresh the file list on the main thread
                self.root.after(0, self.on_refresh_click)
            else:
                error_msg = result.get("payload", {}).get(
                    "error", "Unknown upload error."
                )
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Upload Failed",
                        f"Failed to upload '{os.path.basename(local_path)}': {error_msg}",
                    ),
                )
        except Exception as e:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Upload Error", f"An error occurred during upload: {e}"
                ),
            )

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

    def on_refresh_click(self):
        if not self.is_connected:
            messagebox.showwarning(
                "Not Connected", "Please connect to the server first."
            )
            return

        # Clear existing tree
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            # Fetch file list from server
            if not self.client:
                return
            file_list = self.client.list_files(["all"])

            # Build hierarchical tree data
            if file_list["payload"] is None:

                return
            messagebox.showinfo("DEBUG", file_list["payload"])
            self.populate_tree("", file_list["payload"])

        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def _execute_download(self, remote_path, local_path):
        """Helper function to run the download in a separate thread."""
        try:
            if not self.client:
                # This should not happen if is_connected is true, but as a safeguard
                raise Exception("Client not initialized.")

            result = self.client.download_file(remote_path, local_path)

            if result and result.get("payload", {}).get("ok"):
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success",
                        f"File '{os.path.basename(remote_path)}' downloaded successfully.",
                    ),
                )
            else:
                error_msg = result.get("payload", {}).get(
                    "error", "Unknown download error."
                )
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Download Failed",
                        f"Failed to download '{os.path.basename(remote_path)}': {error_msg}",
                    ),
                )
        except Exception as e:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Download Error", f"An error occurred during download: {e}"
                ),
            )

    def on_download_click(self):
        if not self.is_connected:
            messagebox.showwarning(
                "Not Connected", "Please connect to the server first."
            )
            return

        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning(
                "No File Selected", "Please select a file to download."
            )
            return

        # Helper to construct the full path from the tree
        def get_full_path(item_id):
            path_parts = [self.tree.item(item_id, "text")]
            parent_id = self.tree.parent(item_id)
            while parent_id:
                path_parts.insert(0, self.tree.item(parent_id, "text"))
                parent_id = self.tree.parent(parent_id)
            return "/".join(path_parts)

        remote_path = get_full_path(selected_item[0])
        file_name = self.tree.item(selected_item[0], "text")

        # Check if selected item is a folder (folders can't be downloaded)
        if self.tree.get_children(selected_item[0]):
            messagebox.showwarning("Invalid Selection", "Cannot download a folder.")
            return

        local_path = filedialog.asksaveasfilename(
            initialfile=file_name,
            title="Save File As",
            defaultextension=".*",
            filetypes=[("All Files", "*.*")],
        )

        if not local_path:
            return  # User cancelled

        # Use a thread to avoid blocking the UI
        threading.Thread(
            target=self._execute_download, args=(remote_path, local_path), daemon=True
        ).start()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.5)
    except:
        pass

    app = FileClientApp(root)
    root.mainloop()
