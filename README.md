# 🎨 psdfy

**Convert any image into an editable Adobe Photoshop file with AI-powered layer segmentation.**

Upload a photo, and psdfy automatically detects objects, creates separate layers for each one, and exports a ready-to-edit `.psd` file. Perfect for designers, photographers, and anyone who needs to work with layered images.

---

## ✨ Features

- **🤖 AI-Powered Segmentation** - Uses SAM 2 to automatically detect and separate objects
- **📦 Multi-Layer PSD Export** - Each detected object becomes an editable layer
- **🎯 Text-Prompted Detection** - Optional GroundingDINO integration for specific object detection
- **🌐 Web UI** - Simple browser interface for uploading and downloading
- **💻 CLI Tool** - Command-line interface for automation and scripting
- **☁️ Cloud Ready** - S3 storage backend support for cloud deployments
- **🐳 Docker Support** - CPU and GPU Docker images included
- **⚡ Fast Processing** - Optimized for 1080p images (< 5 seconds on GPU)

---

## 🚀 Quick Start

### Option 1: Web UI (Easiest)

```bash
# Install psdfy
pip install psdfy

# Run installation wizard
psdfy install

# Start the service
psdfy start

# Open browser and go to http://localhost:3457
```

Then:
1. Login with password (default: `123456`)
2. Upload an image
3. Click "Convert to PSD"
4. Download your layered PSD file

### Option 2: Docker (Recommended)

```bash
# CPU version
docker build -f docker/Dockerfile -t psdfy:latest .
docker run -p 3456:3456 -p 3457:3457 psdfy:latest

# GPU version (CUDA 12.1)
docker build -f docker/Dockerfile.gpu -t psdfy:gpu .
docker run --gpus all -p 3456:3456 -p 3457:3457 psdfy:gpu
```

### Option 3: Python API

```python
from app.utils.io import load_image
from app.services.segmenter import get_segmenter
from app.services.psd_writer import get_psd_writer

# Load image
image_array, (width, height), fmt = load_image(image_bytes)

# Segment objects
segmenter = get_segmenter()
masks = segmenter.segment_auto(image_array)

# Write PSD
psd_writer = get_psd_writer()
psd_bytes = psd_writer.write_psd(layers, width, height)
```

---

## 📖 Usage

### Web UI

1. **Login** - Enter password (default: `123456`)
2. **Upload** - Drag & drop or click to select image
3. **Configure** - Choose segmentation mode:
   - `Automatic` - Detects all objects
   - `Text Prompt` - Specify objects (e.g., "person . table . book")
4. **Convert** - Click "Convert to PSD"
5. **Download** - Get your layered PSD file

### CLI Commands

```bash
# Show version and system info
psdfy version

# Install/configure psdfy
psdfy install --password mypassword

# Start API and UI servers
psdfy start

# Stop servers
psdfy stop

# Diagnose and repair installation
psdfy fix --dry-run

# Update to latest version
psdfy update

# Check for issues
psdfy fix --redownload-weights
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Web UI)                      │
└────────────────────────┬────────────────────────────────┘
                         │ (Cookie Auth)
                         ▼
┌─────────────────────────────────────────────────────────┐
│         GUI Web Server (Port 3457)                       │
│  - Login page                                            │
│  - Upload interface                                      │
│  - Server-side proxy to API                             │
└────────────────────────┬────────────────────────────────┘
                         │ (X-Session-Id, X-Client-Signature)
                         ▼
┌─────────────────────────────────────────────────────────┐
│         Proxy API Server (Port 3456)                     │
│  - /convert - Image to PSD conversion                   │
│  - /files - Download results                            │
│  - /auth - Session management                           │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
    ┌────────┐      ┌────────┐      ┌────────┐
    │ SAM 2  │      │ Mask   │      │ PSD    │
    │ Loader │      │ Post-  │      │ Writer │
    │        │      │ process│      │        │
    └────────┘      └────────┘      └────────┘
```

---

## 🛠️ Development

### Setup

```bash
# Clone repository
git clone https://github.com/Mattel-Limbo/psdfy.git
cd psdfy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Code Quality

```bash
# Run linter
ruff check app psdfy tests

# Format code
black app psdfy tests

# Type checking
mypy --strict app psdfy

# Run tests
pytest tests/ -v
```

### Project Structure

```
psdfy/
├── app/                    # FastAPI application
│   ├── api_app/           # Proxy API server (port 3456)
│   ├── ui_app/            # Web UI server (port 3457)
│   ├── services/          # Business logic (segmentation, PSD writing, etc.)
│   ├── models/            # AI model loaders (SAM 2, GroundingDINO)
│   ├── storage/           # Storage backends (local, S3)
│   └── utils/             # Helper utilities
├── psdfy/                 # CLI tool
│   ├── commands/          # CLI commands (install, start, stop, etc.)
│   ├── config.py          # Configuration management
│   └── weights.py         # Model weights downloader
├── web/                   # Web UI assets
│   └── templates/         # HTML templates
├── tests/                 # Test suite
├── docker/                # Docker configurations
└── scripts/               # Utility scripts (benchmarking, etc.)
```

---

## 📋 Requirements

- **Python**: 3.11 or higher
- **RAM**: 8GB minimum (16GB recommended)
- **GPU** (optional): NVIDIA GPU with CUDA 12.1+ for faster processing
- **Disk**: 5GB for model weights

---

## 🔧 Configuration

Configuration is stored in `~/.psdfy/config.toml`:

```toml
[app]
host = "localhost"
api_port = 3456
ui_port = 3457
device = "cpu"  # or "cuda", "mps"

[auth]
ui_password_hash = "..."
client_secret = "..."

[models]
sam2_weights_path = "~/.psdfy/weights/sam2_hiera_large.pt"
enable_grounding_dino = false
```

---

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Change ports
psdfy start --api-port 3500 --ui-port 3501
```

### Model Weights Not Found

```bash
# Re-download weights
psdfy fix --redownload-weights
```

### Reset Password

```bash
# Reset to default (123456)
psdfy fix --reset-password
```

### Check System Health

```bash
# Run diagnostics
psdfy fix --dry-run
```

---

## 📊 Performance

| Resolution | GPU (RTX 3080) | CPU (i7-12700) |
|-----------|----------------|----------------|
| 512x512   | ~0.5s          | ~3s            |
| 1080x1080 | ~1.5s          | ~8s            |
| 2160x2160 | ~4s            | ~20s           |

---

## 📝 API Examples

### Convert Image (cURL)

```bash
# Get session
SESSION=$(curl -X POST http://localhost:3456/auth/client-signature \
  -H "Content-Type: application/json" \
  -d '{"clientSecret":"your-secret"}' | jq -r '.sessionId')

# Convert image
curl -X POST http://localhost:3456/convert \
  -H "X-Session-Id: $SESSION" \
  -H "X-Client-Signature: your-signature" \
  -F "file=@image.jpg" \
  -F "mode=auto" \
  -o output.psd
```

### Convert Image (Python)

```python
import requests

# Get session
response = requests.post(
    "http://localhost:3456/auth/client-signature",
    json={"clientSecret": "your-secret"}
)
session_id = response.json()["sessionId"]

# Convert image
with open("image.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:3456/convert",
        headers={
            "X-Session-Id": session_id,
            "X-Client-Signature": "your-signature"
        },
        files={"file": f},
        data={"mode": "auto"}
    )

# Save PSD
with open("output.psd", "wb") as f:
    f.write(response.content)
```

---

## 📄 License

MIT License - see LICENSE file for details

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Mattel-Limbo/psdfy/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Mattel-Limbo/psdfy/discussions)
- **Documentation**: See `plan.md` for detailed technical documentation

---

## 🎯 Roadmap

- [ ] Batch processing support
- [ ] Advanced layer ordering heuristics
- [ ] Real-time preview in browser
- [ ] Multi-user support with API keys
- [ ] Webhook notifications
- [ ] Custom model fine-tuning

---

**Made with ❤️ for designers and developers**
