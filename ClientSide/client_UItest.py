import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class FileClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UI Client - File Explorer")
        self.root.geometry("900x650")
        
        self.client_socket = None
        self.is_connected = False
        

        self.colors = {
            "primary": "#2c3e50",    
            "secondary": "#ecf0f1",  
            "accent": "#3498db",     
            "text": "#2c3e50",       
            "white": "#ffffff"
        }

        self.setup_styles()
        self.create_layout()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=self.colors["secondary"])
        style.configure("TLabel", background=self.colors["secondary"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=6)
        style.configure("Header.TLabel", background=self.colors["primary"], foreground=self.colors["white"], font=("Segoe UI", 20, "bold"))
        style.configure("Card.TFrame", background=self.colors["white"], relief="flat")
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=25, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#bdc3c7", foreground=self.colors["text"])
        
        style.map("TButton", background=[("active", self.colors["accent"]), ("!disabled", "#bdc3c7")])

    def create_layout(self):

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

        ttk.Label(input_card, text="Status:", background="white").grid(row=0, column=0, sticky="w", pady=5)
        self.entry_status = ttk.Entry(input_card, width=20)
        self.entry_status.insert(0, "Disconnected")
        self.entry_status.config(state="readonly")
        self.entry_status.grid(row=0, column=1, sticky="w", padx=10)

        ttk.Label(input_card, text="Host IP:", background="white").grid(row=1, column=0, sticky="w", pady=5)
        self.entry_host = ttk.Entry(input_card)
        self.entry_host.insert(0, "127.0.0.1") # Mặc định localhost
        self.entry_host.grid(row=1, column=1, sticky="ew", padx=10)

        ttk.Label(input_card, text="Request:", background="white").grid(row=2, column=0, sticky="w", pady=5)
        req_sub_frame = ttk.Frame(input_card, style="Card.TFrame")
        req_sub_frame.grid(row=2, column=1, sticky="ew", padx=10)
        
        self.entry_req = ttk.Entry(req_sub_frame)
        self.entry_req.pack(side="left", fill="x", expand=True)
        ttk.Button(req_sub_frame, text="Browse", width=8, command=self.browse_folder).pack(side="right", padx=(5, 0))


        action_frame = ttk.Frame(input_card, style="Card.TFrame")
        action_frame.grid(row=3, column=1, sticky="w", padx=10, pady=10)

        ttk.Button(action_frame, text="SEND REQUEST", command=self.on_send_click).pack(side="left", padx=(0, 5))
        ttk.Button(action_frame, text="DOWNLOAD", command=self.on_download_click).pack(side="left")


        ttk.Label(left_frame, text="File Response List", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill="both", expand=True)
        
        tree_scroll = ttk.Scrollbar(tree_frame)

        self.tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, height=10)
        tree_scroll.config(command=self.tree.yview)
        
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        
        self.tree.heading("#0", text="Folder / File Structure", anchor="w")

        right_frame = ttk.Frame(body_frame, style="Card.TFrame", padding=15)
        right_frame.pack(side="right", fill="y", anchor="n")

        ttk.Label(right_frame, text="Filter Options", font=("Segoe UI", 12, "bold"), background="white").pack(anchor="w", pady=(0, 15))
        
        self.check_vars = {}
        options = ["All files", "Image files", "Video files"]
        
        for opt in options:
            var = tk.IntVar()
            if opt == "All files": var.set(1)
            chk = ttk.Checkbutton(right_frame, text=opt, variable=var, style="TCheckbutton")
            chk_style = ttk.Style()
            chk_style.configure("TCheckbutton", background="white", font=("Segoe UI", 10))
            
            chk.pack(fill="x", pady=8, anchor="w")
            self.check_vars[opt] = var

        ttk.Separator(right_frame, orient='horizontal').pack(fill='x', pady=20)
        
        ttk.Label(right_frame, text="Custom Extensions:", background="white").pack(anchor="w", pady=(0, 5))
        self.entry_ext = ttk.Entry(right_frame)
        self.entry_ext.pack(fill="x")
        ttk.Label(right_frame, text="(e.g. .pnj; .pdf)", font=("Segoe UI", 8, "italic"), background="white", foreground="#7f8c8d").pack(anchor="w")

    def create_toolbar_btn(self, parent, text, icon, cmd):
        btn = tk.Button(parent, text=f"{icon}  {text}", command=cmd, 
                        bg="#34495e", fg="white", 
                        bd=0, padx=15, pady=5, 
                        activebackground="#2c3e50", activeforeground="white",
                        font=("Segoe UI", 9, "bold"))
        btn.pack(side="left", padx=5)

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_req.delete(0, tk.END)
            self.entry_req.insert(0, path)


    
    def create_mock_data(self):
        return [
            {"id": 1, "name": "Ổ C", "type": "drive", "parent_id": None, "size": "1097876"},
            {"id": 2, "name": "Users", "type": "folder", "parent_id": 1, "size": "12344"},
            {"id": 3, "name": "Admin", "type": "folder", "parent_id": 2, "size": "113455"},
            {"id": 4, "name": "HINHANH", "type": "img", "parent_id": 3, "size": "12344"},
            {"id": 5, "name": "Public", "type": "folder", "parent_id": 2, "size": "4000"},
            {"id": 6, "name": "video.mp4", "type": "video", "parent_id": 5, "size": "500000"},
            {"id": 7, "name": "Program Files", "type": "folder", "parent_id": 1, "size": "0"}
        ]

    def populate_tree(self, data):
        for item in self.tree.get_children():
            self.tree.delete(item)

        id_map = {}

        nodes_to_process = data.copy()
        
        while nodes_to_process:
            current_len = len(nodes_to_process)
            remaining_nodes = []
            
            for item in nodes_to_process:
                node_id = item["id"]
                parent_id = item["parent_id"]
                name = item["name"]
                size = item["size"]

                display_text = f"{name}  [{size}]" 
                

                if parent_id is None:

                    tree_id = self.tree.insert("", "end", text=display_text, open=True)
                    id_map[node_id] = tree_id
                    

                elif parent_id in id_map:
                    parent_tree_id = id_map[parent_id]

                    tree_id = self.tree.insert(parent_tree_id, "end", text=display_text, open=True)
                    id_map[node_id] = tree_id
                    

                else:
                    remaining_nodes.append(item)
            
            nodes_to_process = remaining_nodes
            
            if len(nodes_to_process) == current_len:
                print(f"Cảnh báo: Không tìm thấy cha cho các node: {nodes_to_process}")
                break


    def on_connect_click(self):
        self.entry_status.config(state="normal")
        self.entry_status.delete(0, tk.END)
        self.entry_status.insert(0, "Connected")
        self.entry_status.config(state="readonly")
        messagebox.showinfo("Connection", "Giả lập kết nối thành công!")

    def on_send_click(self):
        data = self.create_mock_data()
        self.populate_tree(data)
        messagebox.showinfo("Success", "Đã tải dữ liệu từ Server (Giả lập)")

    def on_refresh_click(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def on_download_click(self):
        selected_item = self.tree.selection()
        if selected_item:
            item_text = self.tree.item(selected_item[0])['text']
            messagebox.showinfo("Download", f"Đang tải về: {item_text}")
        else:
            messagebox.showwarning("Warning", "Vui lòng chọn một file/folder để tải!")

if __name__ == "__main__":
    root = tk.Tk()
    try: root.tk.call('tk', 'scaling', 1.25) 
    except: pass
    
    app = FileClientApp(root)
    root.mainloop()