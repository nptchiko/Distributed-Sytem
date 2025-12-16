# Distributed File System

A distributed file system with load balancing, supporting multiple file types (images, videos, audio, text, compressed files) with preview capabilities.

## Architecture

- **Coordinator**: Load balancer that routes requests to specialized servers
- **File Servers**: Separate servers for different file types (image, video, text, audio, compressed)
- **Client**: GUI application with file preview and management features

## Features

- 📁 File upload/download with SHA-256 integrity checking
- 🔍 File search and filtering by type
- 👁️ Real-time preview for images, videos, audio, PDFs, and ZIP archives
- 🎨 Modern Tkinter GUI with tree view
- ⚖️ Automatic load balancing based on file type
- 🔒 Path traversal protection

## Setup

### 1. Install Dependencies

```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Servers

Edit `Coordinator/config.yaml` to set server addresses:

```yaml
coordinator:
  host: "127.0.0.1"
  port: 9000
image_server:
  host: "127.0.0.1"
  port: 9001
# ... (other servers)
```

### 3. Start Servers

Open separate terminals for each:

```bash
# Terminal 1: Image Server
cd ServerSide
python main.py 127.0.0.1 9001

# Terminal 2: Video Server
python main.py 127.0.0.1 9002

# Terminal 3: Text Server
python main.py 127.0.0.1 9003

# Terminal 4: Audio Server
python main.py 127.0.0.1 9004

# Terminal 5: Compressed Server
python main.py 127.0.0.1 9005

# Terminal 6: Coordinator
cd ../Coordinator
python coordinator.py
```

### 4. Start Client

```bash
cd ClientSide
python client_UI.py
```

## Usage

1. **Connect**: Click "Connect" button with default settings (127.0.0.1:9000)
2. **Browse**: View files in tree structure
3. **Upload**: Click "UPLOAD" and select a file
4. **Download**: Select a file and click "DOWNLOAD"
5. **Preview**: Click any file to see preview in the right panel
6. **Filter**: Use checkboxes to filter by file type

## Supported File Types

| Type | Extensions |
|------|-----------|
| Images | .jpg, .jpeg, .png, .gif, .bmp |
| Videos | .mp4, .mkv, .webm, .flv, .avi |
| Audio | .mp3, .m4a, .flac, .ogg |
| Text | .txt, .md, .pdf |
| Compressed | .zip, .rar, .7z |

## Preview Features

- **Images**: Thumbnail generation
- **Videos**: 5-second preview clip
- **Audio**: 5-second audio snippet with playback
- **PDF**: First page rendering
- **ZIP**: File tree structure

## Project Structure

```
.
├── ClientSide/
│   ├── client_UI.py          # GUI application
│   ├── dfs_client.py          # Client protocol handler
│   └── VideoPreviewPlayer.py  # Video preview component
├── Coordinator/
│   ├── coordinator.py         # Load balancer
│   └── config.yaml            # Server configuration
├── ServerSide/
│   ├── main.py                # File server implementation
│   └── storage/               # File storage directory
└── requirements.txt
```

## Protocol

Communication uses length-prefixed JSON messages (4-byte big-endian length + JSON payload):

```json
// Upload request
{"command": "upload", "payload": {"name": "file.jpg", "size": 1024, "sha256": "..."}}

// Download request
{"command": "download", "path": "storage/file.jpg"}

// List request
{"command": "list", "filters": ["image", "video"], "path": "storage/"}
```

## Requirements

- Python 3.7+
- OpenCV (for video processing)
- Pillow (for image processing)
- PyMuPDF (for PDF rendering)
- pydub (for audio processing)
- pygame (for audio playback)
- PyYAML (for configuration)

## Notes

- Default storage directory: `ServerSide/storage/`
- Each file server manages its own storage based on file type
- The coordinator automatically routes requests to appropriate servers
- File integrity is verified using SHA-256 checksums

## Screenshots

**File Listing:**
![File Listing](https://github.com/user-attachments/assets/a29c8b2a-aee7-4935-95aa-ed8d71ede4ac)

**File Download:**
![File Download](https://github.com/user-attachments/assets/e93d2839-9eb6-4699-b091-266c139e7e30)

**File Preview:**
<img width="1194" height="938" alt="image" src="https://github.com/user-attachments/assets/4875dd91-6907-4999-9811-85bd964ec14c" />
