# Layer PSD Converter — Project Plan

A Python product that converts a single image into an editable Adobe Photoshop `.psd` file with AI-segmented object layers (background, main object, table, books, shadow, etc.).

The product is shipped as three things in one repo:
1. A **FastAPI service** (the engine).
2. A **CLI tool** named `psdfy` for install / update / version / fix on Windows and macOS.
3. A **single-page Web UI** with a side menu for upload and preview of the generated PSD.

---

## 1. Project Overview

`layer-psd-converter` is a self-contained image-to-PSD product. End users install it locally with one command (`psdfy install`), open the Web UI in their browser, log in with a password (default `123456`, configurable at install time), upload an image, and download a layered `.psd`.

Under the hood:
- A FastAPI service runs locally (or remotely) and exposes `POST /convert` plus a small auth endpoint.
- Object segmentation uses pretrained models (SAM 2 + optional GroundingDINO).
- A `pytoshop`-based writer composes the multi-layer `.psd`.
- Machine-to-machine API access is authenticated with a **Client Signature** scheme described in section 28.
- Browser users access the same API through a thin Web UI behind a password gate.

The target audience for this plan is a junior developer or coding assistant. The plan is intentionally high-level on code but specific on architecture, tools, and decision points.

---

## 2. Goal

- Accept 1 image via HTTP `POST /convert`.
- Detect and separate distinct objects via AI segmentation.
- Produce 1 `.psd` file with named, editable layers (one mask-cut object per layer).
- Optionally return PNG previews of each layer.
- Optionally return a `metadata.json` describing each layer.
- Be reproducible, containerizable, and installable on Windows / macOS / Linux with a single `psdfy install`.
- Provide a minimal Web UI so non-developers can use the tool.
- Protect the API with a Client Signature scheme suitable for local and remote deployments.

Out of scope for v1:
- Multi-image batch input.
- 3D / depth-based layering.
- Font / text recognition layering.
- Real-time streaming.
- Multi-user account system (single shared password is enough).

---

## 3. Expected Input / Output

### Input

| Field   | Type           | Required | Notes                                         |
|---------|----------------|----------|-----------------------------------------------|
| `file`  | multipart file | yes      | `jpg`, `jpeg`, `png`, `webp`                  |
| `prompt`| string         | no       | Optional text prompt for GroundingDINO mode   |
| `mode`  | string         | no       | `auto` (default) or `prompt`                  |
| `return_previews` | bool | no    | Default `false`                               |
| `return_metadata` | bool | no    | Default `true`                                |

Hard limits (configurable):
- Max file size: `10 MB`
- Max resolution: `4096 x 4096`
- Allowed MIME types: `image/jpeg`, `image/png`, `image/webp`

### Output

The endpoint can respond in two formats based on `Accept` header or query flag:

1. **JSON response** (default) — includes a download URL to the PSD plus optional metadata and preview URLs.
2. **Binary response** — direct `.psd` download (`Content-Type: image/vnd.adobe.photoshop`).

---

## 4. API Endpoint Design

All non-public endpoints require two headers:

- `X-Session-Id`: the `sessionId` returned by `POST /auth/client-signature`.
- `X-Client-Signature`: the `clientSignature` returned by the same call.

Details of the formula and lifecycle live in section 28.

### Port split

The product runs as **two FastAPI apps** on two different ports so the public API surface and the browser UI can be locked down independently:

| Server      | Default port | Default host | Purpose                                                                 |
|-------------|--------------|--------------|-------------------------------------------------------------------------|
| Proxy API   | `3456`       | `localhost`  | Machine-to-machine endpoints. Signed via Client Signature (section 28). |
| GUI Web     | `3457`       | `localhost`  | Browser UI + cookie-based login. Talks to Proxy API server-side.        |

Configurable via `.env` (`APP_HOST`, `APP_API_PORT`, `APP_UI_PORT`) or `~/.psdfy/config.toml`. CLI flags on `psdfy install` / `psdfy start` override per invocation.

### Routes per server

**Proxy API server (port `3456`)**
- `POST /auth/client-signature` (public)
- `POST /convert` (signed)
- `GET  /files/{job_id}/{filename}` (signed)
- `GET  /health`, `GET /version` (public)

**GUI Web server (port `3457`)**
- `GET  /` — single-page UI shell (redirects to `/login` if cookie missing)
- `GET  /login`, `POST /ui/login`, `POST /ui/logout`
- `POST /ui/convert` — server-side proxy that calls the Proxy API with the session-bound signature; the browser never sees `clientSecret` or `clientSignature`
- `GET  /ui/job/{job_id}` — progress polling for the UI
- `GET  /health` (public)

### `POST /auth/client-signature` (public, Proxy API)

Issues a signature and a session id. See section 28 for full payload, formula, and validation rules.

### `POST /convert` (signed, Proxy API)

```
POST /convert
Content-Type: multipart/form-data
X-Session-Id: <sessionId>
X-Client-Signature: <clientSignature>
```

Form fields:

- `file` (required)
- `mode` (optional: `auto` | `prompt`)
- `prompt` (optional, string, used when `mode=prompt`)
- `return_previews` (optional, boolean)
- `return_metadata` (optional, boolean)

Status codes:

| Code | Meaning                                      |
|------|----------------------------------------------|
| 200  | Conversion successful                        |
| 400  | Invalid input (bad file type, missing field) |
| 401  | Missing or invalid signature / session       |
| 403  | Signature expired or replayed                |
| 413  | File too large                               |
| 415  | Unsupported media type                       |
| 422  | Image unreadable / corrupted                 |
| 500  | Internal model or PSD-writer error           |
| 503  | Model warming up / GPU busy                  |

### Web UI auth endpoints (GUI Web server)

- `POST /ui/login` — body: `{ "password": "..." }` → bcrypt-verifies against `ui_password_hash` and sets a short-lived signed cookie. Internally the server calls the same signing logic to produce a `sessionId`/`clientSignature` pair, stored server-side keyed by the cookie.
- `POST /ui/logout` — clears the cookie and revokes the bound session in the signature store.

### Cross-server notes

- The GUI Web server never exposes `clientSecret` or `clientSignature` to the browser. UI-originated calls go through `POST /ui/convert` which forwards to the Proxy API with headers injected server-side.
- Both servers share the same `signature store` (in-memory for MVP, Redis later) so a session minted on one is recognized by the other when needed.
- CORS on the Proxy API: by default allow only `http://<host>:<ui_port>`. Override with `CORS_ALLOWED_ORIGINS` for trusted external clients.

---

## 5. High Level Architecture

```
                              +-----------------------+
                              |  Browser (Web UI)     |
                              +-----------+-----------+
                                          | cookie auth
                                          v
+-----------------+         +----------------------------+
|  HTTP client    |         |  GUI Web server (3457)     |
|  (curl, SDK)    |         |  - /login, /, /ui/*        |
+--------+--------+         |  - server-side proxy       |
         |                  +-------------+--------------+
         |                                |  X-Session-Id
         |                                |  X-Client-Signature
         |  X-Session-Id                  v
         |  X-Client-Signature   +----------------------------+
         +---------------------> |  Proxy API server (3456)   |
                                 |  - /auth/client-signature  |
                                 |  - /convert, /files/*      |
                                 +-------------+--------------+
                                               |
                                               v
                                  +------------------------+
                                  | Client-Signature mw    |
                                  +-----------+------------+
                                              |
                                              v
                                  +------------------------+
                                  | Conversion service     |
                                  +-----------+------------+
                                              |
   +--------+---------+-------+----------+----+----+----------+----------+
   |        |         |                  |         |          |          |
   v        v         v                  v         v          v          v
ImageLoader Segmenter MaskRefiner BackgroundBuilder ShadowBuilder LayerBuilder PSDWriter
                                                                                   |
                                                                                   v
                                                                         Storage (local/S3)
```

Synchronous flow is fine for MVP. For production, wrap the heavy step in a job queue (Celery / RQ / Arq) with Redis, and return a `job_id` for polling.

The CLI (`psdfy`) is a separate process that talks to the local OS to install, configure, start, and stop both FastAPI servers. It does not embed model code.

---

## 6. Recommended Tech Stack

- **Language:** Python 3.11+
- **API framework:** FastAPI + Uvicorn
- **Validation:** Pydantic v2
- **Image processing:** Pillow, OpenCV (`opencv-python-headless`), NumPy
- **Segmentation models:**
  - Primary: **SAM 2** (Meta) for class-agnostic masks
  - Optional: **GroundingDINO** for text-prompted detection → feed boxes into SAM 2
  - Fallback (CPU/light): **MobileSAM** or **rembg** (`u2net`)
- **PSD writer:** `pytoshop` (preferred) or `psd-tools` write APIs
- **CLI framework:** `Typer` (built on Click) for the `psdfy` command.
- **Web UI:** Vanilla HTML + Tailwind (CDN) + a tiny bit of vanilla JS, served via Jinja2 templates from FastAPI. Keeps install footprint small. (Optional upgrade later: HTMX or a small React build.)
- **Auth:** Custom HMAC-SHA256 Client Signature middleware (section 28); cookie-backed session for the Web UI.
- **Process supervision:** Foreground via `uvicorn` for MVP. For background install: NSSM (Windows), `launchd` (macOS), `systemd` (Linux).
- **Packaging:** `pyproject.toml` with a `[project.scripts]` entry exposing `psdfy`. Distributed via `pipx` (primary), with optional Homebrew formula and Scoop manifest.
- **Async/queues (later):** Redis + Arq or Celery
- **Storage:** Local filesystem for MVP, S3-compatible for production
- **Container:** Docker (CUDA base image for GPU)
- **Logging:** `structlog` or stdlib `logging` + JSON formatter
- **Testing:** Pytest, httpx for API tests, Playwright (optional) for the Web UI
- **Config:** `pydantic-settings` + `.env` + a per-user TOML at `~/.psdfy/config.toml`

---

## 7. AI Model vs Custom Machine Learning Training

Short answer: **You do NOT need to train your own model.** Use pretrained models.

### Why pretrained is enough

- **SAM 2** (Segment Anything Model 2) is a general-purpose, class-agnostic segmenter. Given a point, box, or "everything" prompt, it returns precise masks for arbitrary objects without any class labels.
- **GroundingDINO** is an open-vocabulary detector. Given a text phrase like `"books . table . cup"`, it returns bounding boxes you can feed into SAM 2 to get named masks.
- Together they cover the user's example layers (background, main object, table, books, shadow, other objects) without dataset preparation or training.

### When you would train a custom model

Only if all of the following are true:
- You have a narrow, repeatable domain (e.g., specific product catalog, medical scans).
- Pretrained models miss objects consistently.
- You have labeled data (~thousands of masks).

For this project, custom training is **not recommended**. It is months of work for marginal gain.

### Recommended practical approach

1. **MVP:** SAM 2 in "automatic mask generation" mode → produces N masks → name them generically (`object_1`, `object_2`, ...) plus `background`.
2. **v1.1:** Add GroundingDINO. Accept an optional text prompt OR use a default vocabulary list (`"person . table . book . cup . chair . shadow"`) → boxes → SAM 2 → named layers.
3. **v1.2:** Add a shadow detector (luminance + ground-plane heuristic) and a background completion step (inpainting, e.g., LaMa) so the background layer is a clean plate.

---

## 8. MVP Approach

Keep it ruthlessly simple:

1. FastAPI app, single `POST /convert` endpoint, synchronous, behind Client Signature auth.
2. Run **SAM 2 automatic mask generator** on the input.
3. Filter masks by area (drop masks < 1% or > 95% of image).
4. Sort masks by area (largest → smallest).
5. Treat the largest non-full mask as `main_object`, others as `object_N`.
6. Background = full image minus union of all masks.
7. No shadow layer yet.
8. Build layers in PIL (RGBA), feed to `pytoshop`, return `.psd` bytes.
9. Ship the `psdfy` CLI with `install`, `update`, `version`, `fix`.
10. Ship a single-page Web UI with password gate.

Goal: working end-to-end conversion in ~2 weeks of dev time.

---

## 9. Advanced Approach

After MVP is stable:

1. **GroundingDINO + SAM 2** for named layers via text prompt.
2. **Shadow extraction** as its own layer (see section 15).
3. **Background inpainting** with LaMa so the background layer is a complete plate.
4. **Mask refinement** with guided filter or alpha matting (`pymatting`) for clean edges, especially hair/fur.
5. **Layer ordering heuristic** based on object size + vertical position (closer-to-camera objects on top).
6. **Async job queue** with progress polling.
7. **Caching** of model weights and a warm-start endpoint.
8. **Multi-user auth**, API keys, rate limiting.
9. **Auto-update** in `psdfy update` (PyPI release channel).

---

## 10. Processing Pipeline

```
1. Receive request (auth middleware validates X-Session-Id + X-Client-Signature)
2. Validate file (type, size, dimensions)
3. Load + decode image -> RGB NumPy array
4. Optional resize if larger than MAX_INFER_SIZE (keep aspect ratio)
5. Run segmentation:
     a. mode=auto    -> SAM 2 automatic mask generator
     b. mode=prompt  -> GroundingDINO(prompt) -> boxes -> SAM 2
6. Post-process masks:
     - remove tiny/duplicate masks (NMS by IoU)
     - feather edges / alpha matting
     - resize masks back to original resolution
7. Build background layer (image minus union of foreground masks; optional inpaint)
8. Build optional shadow layer (luminance heuristic on background-subtracted area)
9. Build per-object RGBA layers
10. Order layers (background -> shadow -> objects bottom->top)
11. Compose PSD (pytoshop) with layer names + bounding boxes
12. Save to disk / return bytes
13. Optionally save preview PNGs + metadata.json
14. Respond
```

---

## 11. Folder Structure

```
layer-psd-converter/
├── app/
│   ├── __init__.py
│   ├── main.py                  # exposes `api_app` and `ui_app` FastAPI instances
│   ├── api_app/                 # Proxy API server (port 3456)
│   │   ├── __init__.py
│   │   ├── factory.py           # build_api_app() -> FastAPI
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── convert.py       # POST /convert
│   │       ├── auth.py          # POST /auth/client-signature
│   │       ├── files.py         # GET  /files/{job_id}/{filename}
│   │       └── health.py        # GET  /health, /version
│   ├── ui_app/                  # GUI Web server (port 3457)
│   │   ├── __init__.py
│   │   ├── factory.py           # build_ui_app() -> FastAPI
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── pages.py         # GET  /, /login
│   │       ├── auth.py          # POST /ui/login, /ui/logout
│   │       ├── proxy.py         # POST /ui/convert, GET /ui/job/{id}
│   │       └── health.py        # GET  /health
│   ├── core/
│   │   ├── config.py            # pydantic-settings + ~/.psdfy/config.toml loader
│   │   ├── logging.py
│   │   ├── errors.py            # custom exception classes
│   │   └── security.py          # signature builder/validator + session store
│   ├── middleware/
│   │   ├── client_signature.py  # validates X-Session-Id / X-Client-Signature (api_app)
│   │   └── ui_session.py        # validates signed cookie (ui_app)
│   ├── schemas/
│   │   ├── convert.py           # request/response models
│   │   ├── auth.py              # client-signature payloads
│   │   └── metadata.py
│   ├── services/
│   │   ├── conversion_service.py
│   │   ├── image_loader.py
│   │   ├── segmenter.py
│   │   ├── mask_postprocess.py
│   │   ├── background_builder.py
│   │   ├── shadow_builder.py
│   │   ├── layer_builder.py
│   │   └── psd_writer.py
│   ├── models/
│   │   ├── sam2_loader.py
│   │   └── dino_loader.py
│   ├── utils/
│   │   ├── io.py
│   │   ├── geometry.py
│   │   ├── naming.py
│   │   └── http_client.py       # used by ui_app/proxy.py to call api_app
│   └── storage/
│       ├── local_storage.py
│       └── s3_storage.py
├── web/
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   └── app.html             # the single-page UI (side menu + upload + preview)
│   └── static/
│       ├── css/app.css
│       ├── js/app.js
│       └── img/logo.svg
├── psdfy/                       # the CLI package
│   ├── __init__.py
│   ├── __main__.py              # `python -m psdfy`
│   ├── cli.py                   # Typer app, registers commands
│   ├── commands/
│   │   ├── install.py
│   │   ├── start.py
│   │   ├── stop.py
│   │   ├── update.py
│   │   ├── version.py
│   │   └── fix.py
│   ├── installers/
│   │   ├── windows.py           # NSSM / Task Scheduler helpers
│   │   ├── macos.py             # launchd plist helpers
│   │   └── linux.py             # systemd unit helpers (optional)
│   ├── config.py                # read/write ~/.psdfy/config.toml
│   ├── doctor.py                # health checks used by `psdfy fix`
│   └── weights.py               # download + verify model weights
├── tests/
│   ├── conftest.py
│   ├── test_api_convert.py
│   ├── test_auth_signature.py
│   ├── test_segmenter.py
│   ├── test_mask_postprocess.py
│   ├── test_psd_writer.py
│   ├── test_cli_install.py
│   └── fixtures/
│       └── sample_images/
├── scripts/
│   ├── download_weights.py
│   └── benchmark.py
├── weights/                     # downloaded model weights (gitignored)
├── outputs/                     # generated PSDs (gitignored)
├── docker/
│   ├── Dockerfile
│   └── Dockerfile.gpu
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── README.md
└── plan.md
```

---

## 12. Layer Generation Strategy

Each layer = an RGBA image the same size as the original canvas, with transparent pixels everywhere except inside the mask.

Rules:

- **Naming:** Prefer human-readable labels from GroundingDINO. Fall back to `object_1`, `object_2`, ...
- **Deduplication:** If two masks have IoU > 0.85, keep the one with higher confidence/area.
- **Size filter:** Drop masks with area < `MIN_MASK_AREA_RATIO` (e.g., 0.005) or > 0.95 of image.
- **Layer order (bottom → top):**
  1. `background`
  2. `shadow` (if present)
  3. Static scene objects (table, floor) sorted by area desc
  4. Foreground objects sorted by vertical position (lower y = closer to camera = higher in stack)
  5. `main_object` (largest salient object) on top
- **Layer bounds:** Crop each layer's stored data to the mask's bounding box for smaller PSD size; PSD layer position records the offset.

---

## 13. Mask Post-Processing Strategy

Raw SAM 2 masks are good but not perfect. Apply:

1. **Binary cleanup:** morphological open/close to remove specks and pinholes.
2. **Hole filling:** `cv2.findContours` + fill internal holes.
3. **Edge feathering:** Gaussian blur the alpha channel by 1–2 px to avoid jaggy borders.
4. **Alpha matting (optional, advanced):** `pymatting` with a trimap derived from the mask, especially for hair, fur, glass.
5. **Mask NMS:** suppress overlapping masks (IoU threshold ~0.85).
6. **Resize:** if inference was on a downscaled image, upscale masks with `cv2.INTER_NEAREST` then re-feather.
7. **Sanity checks:** non-empty mask, area within range, no NaNs.

---

## 14. Background Layer Strategy

Two strategies, pick one based on use case:

**A. Simple (MVP):**
- `background = original_image` with foreground masks set to transparent.
- Pro: trivial. Con: holes where objects were removed, so background is not "clean."

**B. Inpainted (advanced):**
- Compute union of foreground masks → dilate slightly.
- Run inpainting (`cv2.inpaint` for fast, **LaMa** for high quality) to fill the holes.
- Result: a complete, editable background plate.

Always store the background as a fully opaque RGB layer at the bottom of the stack.

---

## 15. Shadow Layer Strategy

Shadow extraction is heuristic — there is no universal pretrained "shadow segmenter" that ships nicely. Recommended approach:

1. Convert image to LAB color space.
2. Build a candidate mask = pixels that are (a) outside foreground masks, (b) significantly darker than the local background mean, (c) low chroma.
3. Morphologically clean and connect to nearest foreground object's base.
4. Store as a layer with **multiply** blend mode in the PSD so it composites naturally over the background.

If reliability is critical, document this as a "best-effort" feature and let the user disable it (`detect_shadow=false`).

---

## 16. PSD Export Strategy

Use **`pytoshop`** as the primary writer. It supports:

- Multiple layers
- Layer names
- Per-layer position/offset
- RGBA channels
- Blend modes (needed for shadow `multiply`)

Steps:

1. Create a `PsdFile` with the canvas size + RGB color mode + 8-bit depth.
2. For each layer (bottom → top):
   - Convert RGBA NumPy array to channel arrays (R, G, B, A).
   - Create a `Layer` with `name`, `top`, `left`, `bottom`, `right`.
   - Set `blend_mode` (`normal` for objects, `multiply` for shadow).
   - Append to `psd.layers`.
3. Optionally bake a flattened composite into the PSD's "merged image" so Photoshop shows a preview without loading layers.
4. Write to bytes / file.

Avoid `photoshop-python-api` — it requires a real Photoshop install (Windows/macOS), not viable for server deployments.

Validation: open every generated PSD in Photoshop manually during development to confirm layers, names, and blend modes survive the round-trip.

---

## 17. Example API Response

JSON response (with `return_previews=true&return_metadata=true`):

```json
{
  "job_id": "8f3c2a1e-2b4c-4f3a-9b1d-7c2e9f1a0b21",
  "status": "succeeded",
  "psd": {
    "url": "/files/8f3c2a1e/output.psd",
    "size_bytes": 2348112,
    "layer_count": 6
  },
  "previews": [
    { "name": "background",   "url": "/files/8f3c2a1e/preview_background.png" },
    { "name": "shadow",       "url": "/files/8f3c2a1e/preview_shadow.png" },
    { "name": "table",        "url": "/files/8f3c2a1e/preview_table.png" },
    { "name": "books",        "url": "/files/8f3c2a1e/preview_books.png" },
    { "name": "main_object",  "url": "/files/8f3c2a1e/preview_main_object.png" }
  ],
  "metadata_url": "/files/8f3c2a1e/metadata.json",
  "timing_ms": {
    "load": 35,
    "segmentation": 1820,
    "postprocess": 240,
    "psd_write": 410,
    "total": 2540
  }
}
```

Error response:

```json
{
  "error": {
    "code": "UNSUPPORTED_MEDIA_TYPE",
    "message": "Only jpg, jpeg, png, webp are supported.",
    "request_id": "req_01HXYZ..."
  }
}
```

---

## 18. Example metadata.json

```json
{
  "job_id": "8f3c2a1e-2b4c-4f3a-9b1d-7c2e9f1a0b21",
  "source": {
    "filename": "scene.jpg",
    "width": 1920,
    "height": 1280,
    "format": "jpeg"
  },
  "model": {
    "segmenter": "sam2_hiera_large",
    "detector": "groundingdino_swint_ogc",
    "version": "1.0.0"
  },
  "layers": [
    {
      "index": 0,
      "name": "background",
      "blend_mode": "normal",
      "bbox": [0, 0, 1920, 1280],
      "area_ratio": 1.0,
      "inpainted": true
    },
    {
      "index": 1,
      "name": "shadow",
      "blend_mode": "multiply",
      "bbox": [420, 880, 1380, 1180],
      "area_ratio": 0.062,
      "method": "luminance_heuristic"
    },
    {
      "index": 2,
      "name": "table",
      "blend_mode": "normal",
      "bbox": [200, 700, 1700, 1280],
      "area_ratio": 0.31,
      "confidence": 0.81
    },
    {
      "index": 3,
      "name": "books",
      "blend_mode": "normal",
      "bbox": [610, 540, 1010, 820],
      "area_ratio": 0.07,
      "confidence": 0.74
    },
    {
      "index": 4,
      "name": "main_object",
      "blend_mode": "normal",
      "bbox": [800, 300, 1300, 900],
      "area_ratio": 0.18,
      "confidence": 0.92
    }
  ],
  "generated_at": "2026-05-22T10:14:05Z"
}
```

---

## 19. Environment Variables

```env
# --- App ---
APP_ENV=development           # development | staging | production
APP_HOST=localhost            # bind host for both servers (use 0.0.0.0 to expose on LAN)
APP_API_PORT=3456             # proxy API port (POST /convert, /auth/client-signature, ...)
APP_UI_PORT=3457              # GUI web port (login + single-page UI)
APP_LOG_LEVEL=INFO
APP_REQUEST_TIMEOUT=120

# --- Limits ---
MAX_UPLOAD_MB=10
MAX_IMAGE_DIM=4096
MAX_INFER_SIZE=1536
MIN_MASK_AREA_RATIO=0.005

# --- Models ---
SAM2_WEIGHTS_PATH=./weights/sam2_hiera_large.pt
SAM2_CONFIG_PATH=./weights/sam2_hiera_l.yaml
DINO_WEIGHTS_PATH=./weights/groundingdino_swint_ogc.pth
DINO_CONFIG_PATH=./weights/GroundingDINO_SwinT_OGC.py
DEVICE=cuda                   # cuda | cpu | mps
ENABLE_GROUNDING_DINO=true
DEFAULT_PROMPT=person . table . book . cup . chair . laptop . bottle

# --- Features ---
ENABLE_SHADOW_LAYER=true
ENABLE_BACKGROUND_INPAINT=true

# --- Storage ---
STORAGE_BACKEND=local         # local | s3
STORAGE_LOCAL_DIR=./outputs
S3_BUCKET=
S3_REGION=
S3_ACCESS_KEY=
S3_SECRET_KEY=
PUBLIC_BASE_URL=http://localhost:3456

# --- Auth: Web UI password ---
UI_PASSWORD=123456            # default; overridden by `psdfy install --password`
UI_SESSION_TTL_SECONDS=86400
UI_COOKIE_NAME=psdfy_ui

# --- Auth: Client Signature ---
SIGNATURE_SECRET_PEPPER=      # extra server-side pepper mixed into HMAC key (optional)
SIGNATURE_SALT_LENGTH=10
SIGNATURE_TTL_SECONDS=86400   # how long a session/signature is valid
SIGNATURE_TIMESTAMP_SKEW=300  # max abs(now - clientUnixTimestamps) on issuance, seconds
SIGNATURE_STORE=memory        # memory | sqlite | redis

# --- CORS ---
CORS_ALLOWED_ORIGINS=*
```

Provide a checked-in `.env.example`. Never commit the real `.env`.

`UI_PASSWORD` is also persisted (hashed) to `~/.psdfy/config.toml` by `psdfy install` so the same password survives reinstalls.

---

## 20. Requirements.txt Suggestion

```
# Web
fastapi>=0.115
uvicorn[standard]>=0.30
python-multipart>=0.0.9
pydantic>=2.7
pydantic-settings>=2.3
jinja2>=3.1
itsdangerous>=2.2          # signed cookies for the UI session

# Auth
passlib[bcrypt]>=1.7        # hash UI password at rest

# CLI
typer[all]>=0.12
rich>=13.7
tomli-w>=1.0                # write TOML config
packaging>=24.0             # version comparisons in `psdfy update`
requests>=2.32              # fetch latest version + weights

# Imaging
pillow>=10.3
opencv-python-headless>=4.10
numpy>=1.26
scikit-image>=0.24
pymatting>=1.1

# ML / segmentation
torch>=2.3
torchvision>=0.18
# Install SAM 2 from source (Meta's repo) — pinned commit recommended
# git+https://github.com/facebookresearch/sam2.git@<commit-sha>
# GroundingDINO from source
# git+https://github.com/IDEA-Research/GroundingDINO.git@<commit-sha>
transformers>=4.42
huggingface-hub>=0.24

# PSD
pytoshop>=1.2

# Logging / utils
structlog>=24.1
python-dotenv>=1.0

# Testing
pytest>=8.2
pytest-asyncio>=0.23
httpx>=0.27
```

Pin transitively-fragile libs (`torch`, `pytoshop`, SAM 2 commit) once a working combination is found. Use a `requirements.lock` for production.

---

## 21. Development Phases

**Phase 0 — Scaffolding (1–2 days)**
- Repo init, folder structure, FastAPI hello-world, config, logging, Dockerfile.
- `pyproject.toml` with `psdfy` console script entrypoint.

**Phase 1 — Auth + skeleton (2–3 days)**
- `POST /auth/client-signature` endpoint and middleware (section 28).
- In-memory session store.
- `/health`, `/version`.

**Phase 2 — MVP pipeline (3–5 days)**
- Image upload + validation.
- SAM 2 auto-mask integration.
- Naive background subtraction.
- `pytoshop` writer producing a multi-layer PSD.
- Local file storage + JSON response.

**Phase 3 — Web UI (2–3 days)**
- Login page with password gate.
- Single-page app with side menu, upload, progress, preview, download PSD.

**Phase 4 — CLI `psdfy` (3–4 days)**
- `install`, `start`, `stop`, `version`, `fix` working on Windows + macOS.
- PID file management in `~/.psdfy/run/` for `start`/`stop`.
- `update` checks PyPI, swaps weights/config safely.

**Phase 5 — Quality pass (3–5 days)**
- Mask post-processing (morphology, feathering).
- Layer ordering heuristic.
- Preview PNG generation + metadata.json.
- Pytest coverage of core services + auth + CLI.

**Phase 6 — Named layers (3–5 days)**
- GroundingDINO integration with default vocabulary.
- `mode=prompt` support.
- Better naming / dedup.

**Phase 7 — Advanced features (1–2 weeks)**
- Background inpainting (LaMa).
- Shadow layer.
- Alpha matting for tricky edges.
- Async job queue + polling.
- S3 storage, API keys, rate limit.

**Phase 8 — Hardening (ongoing)**
- Benchmarks, monitoring, CI/CD, GPU autoscaling, model versioning.

---

## 22. Best Practices

- **Type hints everywhere.** Run `mypy --strict` on `app/` and `psdfy/`.
- **Lint/format:** Ruff + Black, pre-commit hooks.
- **Pure functions in services.** Pass arrays in/out; keep I/O at the edges.
- **Single conversion service** orchestrates the pipeline; routes stay thin.
- **Lazy load models once** at app startup, not per request.
- **Don't load weights into git.** Use `psdfy install` / `scripts/download_weights.py`.
- **Idempotent endpoints.** Same input → reproducible output (seed where applicable).
- **Stream large files** (don't `read()` whole upload into memory if avoidable).
- **Bound everything:** request timeout, max file size, max masks per image.
- **Log structured JSON** with a `request_id` correlation field.
- **Don't trust filenames.** Re-detect MIME via magic bytes.
- **Sanitize layer names** before writing to PSD (length, control chars).
- **Document every env var** in `.env.example` and README.
- **Never log secrets.** Redact `clientSecret`, `clientSignature`, password.
- **Use constant-time comparison** (`hmac.compare_digest`) when validating signatures.

---

## 23. Error Handling Strategy

Define a small set of typed exceptions in `app/core/errors.py`:

- `InvalidImageError` → 400/415/422
- `FileTooLargeError` → 413
- `UnauthorizedError` → 401
- `SignatureExpiredError` → 403
- `SegmentationError` → 500
- `PSDWriteError` → 500
- `ModelNotReadyError` → 503

Map them to JSON via a global FastAPI exception handler that returns:

```json
{ "error": { "code": "...", "message": "...", "request_id": "..." } }
```

Rules:

- Never leak stack traces to the client; log them server-side with the `request_id`.
- Validate inputs at the edge (FastAPI + Pydantic). Internal services assume valid data.
- Wrap GPU/torch calls in try/except to detect OOM and return 503 with a retry hint.
- Always clean up temp files in a `finally` block.
- Auth errors must NOT reveal which part failed (missing header vs bad signature vs expired). Return a generic 401/403.

---

## 24. Testing Strategy

- **Unit tests** for pure helpers: mask post-processing, naming, geometry, signature builder/validator.
- **Service tests** with small fixture images (tiny 64×64 PNGs) and a mocked segmenter that returns deterministic masks.
- **API tests** with `httpx.AsyncClient`, covering happy paths, every documented error code, and signature flow.
- **PSD round-trip test:** write a PSD, read it back with `psd-tools`, assert layer count, names, sizes, blend modes.
- **CLI tests:** invoke `psdfy install --dry-run`, `psdfy version`, `psdfy fix --dry-run` with `Typer`'s `CliRunner`, asserting exit codes and config file contents.
- **Web UI smoke test (optional):** Playwright launches the server, logs in with the default password, uploads a fixture image, asserts the PSD download link appears.
- **Integration test (manual or nightly):** real model + real sample images, asserts file is non-empty, valid, and openable in Photoshop.
- **Benchmarks:** `scripts/benchmark.py` reports total ms per stage on a fixed image set.

CI matrix: lint, type-check, unit + service + API + CLI tests on CPU. Heavy model tests gated behind a `MODELS=1` flag.

---

## 25. Known Limitations

- Quality of layers depends on segmentation quality; cluttered scenes will produce noisy masks.
- SAM 2 has no semantic labels by itself — names come from GroundingDINO or are generic.
- Shadow detection is heuristic and will fail on textured or low-contrast surfaces.
- Background inpainting is approximate; large occluded regions will show artifacts.
- PSD writer support for advanced features (smart objects, text layers, layer effects) is limited; output is raster layers only.
- GPU is strongly recommended; CPU inference can take 30s–2min per image for SAM 2 large.
- Very high resolutions (>4K) require downscaling for inference, then upscaling masks, which can soften edges.
- Hair, fur, glass, motion blur remain hard cases even with alpha matting.
- The Client Signature scheme is symmetric: anyone with `clientSecret` can mint signatures. Treat `clientSecret` like a password and rotate it.
- The Web UI uses a single shared password (no multi-user). Suitable for personal/internal use, not public SaaS.

---

## 26. Acceptance Criteria

The MVP is "done" when all of the following are true:

1. `psdfy install` completes successfully on a clean Windows 11 and macOS machine, downloads weights, writes `~/.psdfy/config.toml`, and prints the final UI/API URLs.
2. `psdfy start` brings up both servers (Proxy API on `3456`, GUI Web on `3457`) and `psdfy stop` shuts them down cleanly.
3. `psdfy version` prints the CLI, service, model, and per-server URLs.
4. `psdfy fix` detects and repairs at least: missing weights, broken config, wrong Python version, port already in use (reports clear remediation).
5. Visiting `http://localhost:3457/` shows a login page; entering the configured password (default `123456`) opens the single-page UI.
6. Uploading a JPG/PNG/WEBP through the UI returns a downloadable `.psd` and shows a preview of the generated layers.
7. `POST http://localhost:3456/auth/client-signature` returns a `clientSignature` and `sessionId` for valid input and rejects invalid input.
8. `POST http://localhost:3456/convert` rejects unsigned requests with 401, signed-but-expired with 403, and accepts valid signed requests.
9. The generated `.psd` opens cleanly in Adobe Photoshop with **at least 3 named, non-empty layers** (background + 2+ objects) on representative test images.
10. Each layer is independently editable inside Photoshop.
11. Invalid inputs return the documented 4xx error codes with structured JSON errors.
12. Average end-to-end latency on GPU is **≤ 5 seconds** for a 1080p image.
13. Test suite passes in CI (lint + type-check + unit + API + CLI tests).
14. README documents `psdfy install` / `start` / `stop` (with `--password`, `--api-port`, `--ui-port`, `--host` flags), curl examples against port `3456`, and the signature flow.

For "v1 complete", add:

15. Optional `metadata.json` and preview PNGs returned correctly.
16. Shadow layer present (and toggleable) on images with clear ground shadows.
17. Background layer is inpainted when `ENABLE_BACKGROUND_INPAINT=true`.
18. `psdfy update` upgrades the package in place from PyPI and migrates config if needed.

---

## 27. Final Recommended Implementation Roadmap

A practical, junior-friendly order of operations:

1. **Day 1:** Scaffold repo, two FastAPI factories (`api_app`, `ui_app`), `.env`, Dockerfile, `/health` on both, `pyproject.toml` with `psdfy` entrypoint stub.
2. **Day 2:** Implement `POST /auth/client-signature` + middleware (section 28) on `api_app`. Write unit tests for the signature math.
3. **Day 3:** Implement `POST /convert` on `api_app` with file validation; return a placeholder PSD (single flat layer) generated by `pytoshop`. Verify it opens in Photoshop.
4. **Day 4:** Add SAM 2 loader and `segmenter.py` with auto-mask mode.
5. **Day 5:** Add `mask_postprocess.py` (NMS, area filter, morphology, feathering).
6. **Day 6:** Add `layer_builder.py` and update `psd_writer.py` to emit one layer per mask + a naive background.
7. **Day 7:** Build `ui_app` shell (login + single-page app) and `/ui/convert` server-side proxy that injects signature headers when calling `api_app`.
8. **Day 8:** Build `psdfy install` (writes `~/.psdfy/config.toml` with `api_port=3456`, `ui_port=3457`, password hash, client secret) for Windows and macOS.
9. **Day 9:** Build `psdfy start` / `psdfy stop` with PID files in `~/.psdfy/run/`. Add `psdfy version` and basic `psdfy fix`. Test on clean VMs.
10. **Day 10:** Add preview PNGs + `metadata.json`. Add structured logging and `request_id` across both servers.
11. **Day 11:** Write unit + API + CLI tests. Set up CI.
12. **Week 3:** Add GroundingDINO + `mode=prompt`. Improve layer naming and ordering.
13. **Week 4:** Background inpainting (LaMa) + shadow layer + alpha matting.
14. **Week 5+:** `psdfy update`, async job queue, S3 storage, API keys, rate limiting, benchmarks.
15. **Ongoing:** Hardening, monitoring, model upgrades, GPU autoscaling.

Stop after step 11 to ship an MVP. Steps 12+ are quality and production work that can be prioritized based on real usage feedback.

---

## 28. Authentication — Client Signature

The API is protected by a stateless-feeling but server-validated HMAC signature scheme. There is one issuer endpoint and one middleware. The Web UI never exposes this to the user; it logs in with the password and the server mints a signature internally.

### 28.1 Issuance — `POST /auth/client-signature`

Request body:

```json
{
  "clientSecret": "28bf6f2e-fd48-4778-bcd1-edc20726ea0e",
  "clientUnixTimestamps": "1779424129"
}
```

Response body:

```json
{
  "clientSignature": "<base64 string>",
  "sessionId": "c9c3f9f6-6512-4a10-9380-c7f0af8eebc6"
}
```

Validation on issuance:

- `clientSecret` must be a valid UUIDv4. Reject with 400 otherwise.
- `clientUnixTimestamps` must parse as an integer and be within `SIGNATURE_TIMESTAMP_SKEW` of server time (default ±300s). Reject with 400 otherwise.
- Generate a fresh `sessionId` (random UUIDv4) and a fresh `salt` (10 random alphanumeric chars, see `SIGNATURE_SALT_LENGTH`).
- Compute `clientSignature` per section 28.3.
- Persist the session record in `SIGNATURE_STORE`:
  ```
  { sessionId, clientSecretHash, salt, signature, timestamp, expiresAt, revoked=false }
  ```
  Store a hash of `clientSecret` (not the raw value) for forensics.
- Return only `clientSignature` and `sessionId`.

### 28.2 Verification — `X-Client-Signature` middleware

Every protected route requires:

- `X-Session-Id: <sessionId>`
- `X-Client-Signature: <clientSignature>`

The middleware:

1. Loads the session record by `sessionId`. Missing → 401.
2. Checks `expiresAt > now` and `revoked == false`. Failed → 403.
3. Constant-time compares header `X-Client-Signature` to the stored signature. Mismatch → 401.
4. On success, attaches the session info to `request.state` and proceeds.

This design intentionally does **not** require the client to send the timestamp/salt on every request: the server already has them keyed by `sessionId`. That keeps the protected-route headers minimal and avoids client clock-drift problems after issuance.

### 28.3 Signature Formula

User-provided formula:

> `base64(hmac-sha256(clientSecret) + epoch timestamps + salt string 10char)`

Canonical interpretation (recommended, what the implementation will do):

```
key       = utf8(clientSecret) [optionally peppered: utf8(clientSecret) + SIGNATURE_SECRET_PEPPER]
message   = utf8(clientUnixTimestamps) + utf8(salt10)
mac       = HMAC_SHA256(key, message)            # 32 raw bytes
signature = base64_standard(mac)                 # ASCII string
```

Notes:

- `salt10` is the 10-char alphanumeric salt the server generated at issuance and stored alongside the session.
- `clientUnixTimestamps` is the value the client sent on issuance, treated as a string.
- Use HMAC-SHA256, not plain SHA-256: the `clientSecret` is the HMAC key.
- Optional pepper (`SIGNATURE_SECRET_PEPPER`) is a server-side secret appended to the key. It does not change the wire format and gives partial protection if `clientSecret` leaks but the server config does not.

If the project later prefers the literal reading of the formula (concatenate three pieces then base64), document the alternative as:

```
signature = base64( SHA256(utf8(clientSecret)) || utf8(clientUnixTimestamps) || utf8(salt10) )
```

The recommended HMAC interpretation is more standard and is what tests and clients should target.

### 28.4 Reference Pseudocode

```python
import base64, hmac, hashlib, secrets, string, time, uuid

def make_salt(n: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))

def build_signature(client_secret: str, ts: str, salt: str, pepper: str = "") -> str:
    key = (client_secret + pepper).encode("utf-8")
    msg = (ts + salt).encode("utf-8")
    mac = hmac.new(key, msg, hashlib.sha256).digest()
    return base64.b64encode(mac).decode("ascii")

def issue(client_secret: str, client_ts: str, store, ttl: int, skew: int) -> dict:
    if not is_uuid_v4(client_secret):
        raise InvalidInput("clientSecret must be UUIDv4")
    ts_int = int(client_ts)
    if abs(time.time() - ts_int) > skew:
        raise InvalidInput("clientUnixTimestamps too far from server time")
    session_id = str(uuid.uuid4())
    salt = make_salt()
    signature = build_signature(client_secret, client_ts, salt)
    store.put(session_id, {
        "client_secret_hash": sha256_hex(client_secret),
        "salt": salt,
        "signature": signature,
        "timestamp": ts_int,
        "expires_at": int(time.time()) + ttl,
        "revoked": False,
    })
    return {"clientSignature": signature, "sessionId": session_id}

def verify(headers, store) -> dict:
    sid = headers.get("X-Session-Id")
    sig = headers.get("X-Client-Signature")
    if not sid or not sig:
        raise Unauthorized()
    rec = store.get(sid)
    if not rec or rec["revoked"]:
        raise Unauthorized()
    if rec["expires_at"] < int(time.time()):
        raise Forbidden("expired")
    if not hmac.compare_digest(sig, rec["signature"]):
        raise Unauthorized()
    return rec
```

### 28.5 Curl Example

```bash
# 1) issue
curl -sS -X POST http://localhost:3456/auth/client-signature \
  -H 'Content-Type: application/json' \
  -d '{"clientSecret":"28bf6f2e-fd48-4778-bcd1-edc20726ea0e","clientUnixTimestamps":"1779424129"}'
# -> { "clientSignature":"...", "sessionId":"..." }

# 2) call /convert
curl -sS -X POST http://localhost:3456/convert \
  -H "X-Session-Id: <sessionId>" \
  -H "X-Client-Signature: <clientSignature>" \
  -F "file=@scene.jpg" \
  -F "mode=auto"
```

### 28.6 Security Notes

- Always serve over HTTPS in production. The signature does not encrypt the payload.
- Treat `clientSecret` as a long-lived credential. Provide a way to rotate it (e.g., regenerate via `psdfy fix --reset-client-secret`).
- Rate-limit `POST /auth/client-signature` (e.g., 30/min per IP) to deter brute force.
- Use `SIGNATURE_STORE=redis` in production for multi-process deployments.
- Log only the `sessionId`, never the `clientSecret` or `clientSignature`.

---

## 29. CLI Tool — `psdfy`

`psdfy` is the user-facing command. Built with **Typer** so help, autocompletion, and exit codes are free.

### 29.1 Commands

```
psdfy install [--password TEXT] [--api-port INT] [--ui-port INT] [--host TEXT]
              [--device cuda|cpu|mps] [--no-weights] [--service] [--yes]
psdfy start   [--api-port INT] [--ui-port INT] [--host TEXT] [--foreground]
psdfy stop    [--force]
psdfy update  [--channel stable|beta] [--yes]
psdfy version
psdfy fix     [--reset-config] [--reset-password] [--redownload-weights]
              [--reset-client-secret] [--dry-run]
```

Default ports (overridable via flags or `.env`):

| Service                   | Default port | Env var         |
|---------------------------|--------------|-----------------|
| Proxy API (`/convert`, …) | `3456`       | `APP_API_PORT`  |
| GUI Web (login + UI)      | `3457`       | `APP_UI_PORT`   |
| Bind host                 | `localhost`  | `APP_HOST`      |

Both servers bind to `localhost` by default. Set `APP_HOST=0.0.0.0` (or pass `--host 0.0.0.0`) to expose on the LAN.

### 29.2 `psdfy install`

Behavior:

1. Detect OS (`win32`, `darwin`, `linux`) and Python version (require >= 3.11).
2. Create a per-user directory: `~/.psdfy/` (Windows: `%USERPROFILE%\.psdfy\`).
3. Resolve install location:
   - If installed via `pipx`, use the pipx venv (no extra venv needed).
   - Otherwise create `~/.psdfy/venv/` and install dependencies into it.
4. Prompt (or read from `--password`) for the UI password. Default if blank: `123456`.
   - Hash with bcrypt and store in `~/.psdfy/config.toml`.
5. Generate and store an initial `clientSecret` (UUIDv4) for machine-to-machine use.
6. Download model weights into `~/.psdfy/weights/` unless `--no-weights`.
7. Write `~/.psdfy/config.toml`:
   ```toml
   [app]
   host = "localhost"
   api_port = 3456            # proxy API
   ui_port  = 3457            # GUI web
   device   = "cuda"
   storage_dir = "~/.psdfy/outputs"

   [auth]
   ui_password_hash = "$2b$12$..."
   client_secret = "28bf6f2e-fd48-4778-bcd1-edc20726ea0e"
   signature_pepper = "<random 32 bytes hex>"

   [models]
   sam2_path = "~/.psdfy/weights/sam2_hiera_large.pt"
   dino_path = "~/.psdfy/weights/groundingdino_swint_ogc.pth"

   [meta]
   installed_version = "0.1.0"
   installed_at = "2026-05-22T10:14:05Z"
   ```
8. If `--service` is passed, register a background service:
   - Windows: NSSM (`nssm install psdfy`) or a Scheduled Task at logon.
   - macOS: write a `~/Library/LaunchAgents/ai.psdfy.plist` and `launchctl load` it.
   - Linux: write a `~/.config/systemd/user/psdfy.service` and `systemctl --user enable --now psdfy`.
9. Print final URLs (UI at `http://<host>:<ui_port>/`, API at `http://<host>:<api_port>/`) and the password hint.

Idempotent: re-running `psdfy install` updates the password / ports / host without redownloading weights unless asked.

### 29.3 `psdfy start`

Starts both servers in the background and writes their PIDs to `~/.psdfy/run/`:

```
~/.psdfy/run/api.pid
~/.psdfy/run/ui.pid
~/.psdfy/run/api.log
~/.psdfy/run/ui.log
```

Behavior:

1. Read `~/.psdfy/config.toml` for `host`, `api_port`, `ui_port`. CLI flags (`--host`, `--api-port`, `--ui-port`) override per invocation but do **not** persist.
2. Pre-flight checks:
   - Both ports must be free; if not, exit 1 with a clear message and suggest `psdfy fix`.
   - Required weights present.
3. Spawn the API server (uvicorn binding `app.main:api_app`) on `api_port`.
4. Spawn the UI server (uvicorn binding `app.main:ui_app`) on `ui_port`.
5. Wait until both `/health` endpoints respond OK (timeout 30s).
6. Print:
   ```
   psdfy is running
     UI:  http://localhost:3457
     API: http://localhost:3456
   ```
7. With `--foreground`, run both servers in the current terminal (logs streamed to stdout). Otherwise detach.

If `psdfy start` is invoked while servers are already running (PID files exist and processes alive), it prints status and exits 0 without restarting.

### 29.4 `psdfy stop`

Stops both servers gracefully:

1. Read PIDs from `~/.psdfy/run/api.pid` and `~/.psdfy/run/ui.pid`.
2. Send SIGTERM (Windows: `taskkill /PID <pid>`); wait up to 10 s for clean exit.
3. With `--force`, send SIGKILL (Windows: `taskkill /F /PID <pid>`) if a process refuses to exit.
4. Remove the PID files. Leave the log files for inspection.
5. Print final status. Exit 0 if both stopped (or were already stopped), 1 otherwise.

When the service was installed via `--service` (NSSM / launchd / systemd), `psdfy start` and `psdfy stop` delegate to the platform service manager instead of spawning processes directly, so behavior stays consistent.

### 29.5 `psdfy update`

1. Query PyPI for the latest `psdfy` version on the chosen channel.
2. Compare with `installed_version` in `config.toml`.
3. If newer:
   - `pipx upgrade psdfy` (or `pip install --upgrade` inside the managed venv).
   - Run any registered config migrations.
   - Restart the service (if previously installed with `--service`).
4. Print release notes URL.

### 29.6 `psdfy version`

Prints:

```
psdfy        0.3.1
service      0.3.1 (api: http://localhost:3456, ui: http://localhost:3457)
python       3.11.9
torch        2.3.0 (cuda)
sam2 weights sam2_hiera_large.pt (sha256 ok)
dino weights groundingdino_swint_ogc.pth (sha256 ok)
config       ~/.psdfy/config.toml
```

### 29.7 `psdfy fix`

A diagnose-and-repair command. Runs a sequence of checks and offers to fix what's broken:

- Python version >= 3.11.
- `~/.psdfy/config.toml` exists and parses.
- Weights present and SHA-256 matches manifest. Re-download if `--redownload-weights` or interactively confirmed.
- Port available; offer alternative if not.
- GPU detection: `torch.cuda.is_available()` matches configured `device`.
- Service status (if installed with `--service`).
- `--reset-password` re-prompts and rewrites the bcrypt hash (default back to `123456` if user submits blank).
- `--reset-client-secret` mints a new UUIDv4 and writes it.
- `--reset-config` overwrites the config with defaults (warns first).
- `--dry-run` only reports, does not modify.

Exit codes:
- `0` everything healthy or fixed.
- `1` issues remain.
- `2` user aborted.

### 29.8 Distribution

Primary channel: **PyPI** with `pipx` for end users.

```
pipx install psdfy
psdfy install --password mySecret123
```

Optional channels (post-MVP):

- **Homebrew** (macOS): a tap repo `anomalyco/homebrew-psdfy` with a formula that runs `pipx install psdfy` and then `psdfy install`.
- **Scoop** (Windows): a manifest in a bucket repo doing the same.
- **Standalone binary**: PyInstaller one-file build for users without Python. Larger download (~1 GB with torch), but zero prerequisites.

---

## 30. Web UI

A small, deliberately minimal single-page UI served by FastAPI itself. No build step required.

### 30.1 Pages

- `/` — if not logged in, redirect to `/login`. Otherwise render the app shell.
- `/login` — password form. POSTs to `/ui/login`.
- `/logout` — clears the cookie.

### 30.2 Layout

```
+--------------------------------------------------------+
| [logo] psdfy                                  [Logout] |
+----------------+---------------------------------------+
|  Side menu     |  Main panel                           |
|  ------------  |  ----------------------------------   |
|  > Convert     |  Drop image here / [Browse]           |
|    Settings    |  [Convert]                            |
|    About       |                                       |
|                |  Progress bar                         |
|                |                                       |
|                |  Result:                              |
|                |   - Preview thumbnails (per layer)    |
|                |   - [Download .psd]                   |
|                |   - [Download metadata.json]          |
+----------------+---------------------------------------+
```

For v1, only the **Convert** item in the side menu is functional. `Settings` and `About` are placeholders so the menu structure exists and can grow.

### 30.3 Auth flow (UI)

1. User submits the password to `POST /ui/login`.
2. Server bcrypt-verifies against `ui_password_hash` from `config.toml`.
3. On success, server:
   - Generates a `clientSecret` from config (or a per-session ephemeral one),
   - Calls the same internal logic as `POST /auth/client-signature` to mint `sessionId` + `clientSignature`,
   - Stores both in a server-side session keyed by a signed cookie (`itsdangerous`),
   - Returns 302 to `/`.
4. The UI's JavaScript calls `/convert` via a same-origin server-side proxy `/ui/convert` that injects the session's `X-Session-Id` and `X-Client-Signature` headers. The browser never sees those values.

This keeps the signature secret out of the browser while reusing the same auth pipeline as the public API.

### 30.4 UX details

- Drag-and-drop upload, with file-type and size validation client-side before upload.
- Live progress: poll a `/ui/job/{job_id}` endpoint or use SSE for stage updates (`load`, `segment`, `compose`, `done`).
- Show layer thumbnails as they become available.
- Show a "Open in Photoshop" hint after download.
- Mobile: side menu collapses into a top hamburger.

### 30.5 Accessibility & i18n

- Use semantic HTML (`<nav>`, `<main>`, `<form>`, `<button>`).
- Keyboard navigable; visible focus states.
- All strings centralized in a small `web/static/js/i18n.js` so a future translation pass is easy. Default language: English. Indonesian translation can ship in v1.1.

---

## 31. Cross-Platform Installation & Packaging

### 31.1 Prerequisites

- Python 3.11+ available on PATH.
- (Recommended) `pipx` installed: `python -m pip install --user pipx && python -m pipx ensurepath`.
- For GPU: matching CUDA driver + a CUDA-enabled `torch` wheel.
- For macOS Apple Silicon: `torch` with `mps` backend works for SAM 2 large but is slower than CUDA.

### 31.2 Install Flow

```
# Windows (PowerShell) and macOS (zsh/bash) — same commands
pipx install psdfy
psdfy install --password mySecret123
psdfy start
# UI:  http://localhost:3457
# API: http://localhost:3456
```

If `--service` was used during `psdfy install`, the servers start on boot/login automatically. Otherwise use `psdfy start` / `psdfy stop` to control them manually.

### 31.3 Update Flow

```
psdfy update
```

Internally `pipx upgrade psdfy` plus config migration plus service restart.

### 31.4 Uninstall Flow (post-MVP)

```
psdfy uninstall          # stops service, removes ~/.psdfy/
pipx uninstall psdfy
```

### 31.5 Platform-Specific Notes

**Windows**
- Use `pipx` rather than the system Python to avoid PATH conflicts.
- For `--service`: prefer NSSM (bundled into `~/.psdfy/bin/nssm.exe` by `psdfy install`); fallback is a Scheduled Task at logon.
- File paths in `config.toml` are stored using forward slashes for portability and converted at runtime.

**macOS**
- Test on both Intel and Apple Silicon; ship a universal wheel where possible.
- Code signing and notarization are only required if shipping a standalone binary. The `pipx` route avoids this.
- Default `device` is `mps` on Apple Silicon, `cpu` otherwise.

**Linux** (best-effort, not a primary target)
- Same `pipx` flow.
- `--service` writes a user systemd unit.
- Provide a `Dockerfile.gpu` for headless deployment.

### 31.6 PyPI Project Metadata

`pyproject.toml` highlights:

```toml
[project]
name = "psdfy"
version = "0.1.0"
description = "Image to layered Photoshop PSD via AI segmentation."
requires-python = ">=3.11"
dependencies = ["fastapi", "uvicorn[standard]", "typer[all]", "..."]

[project.scripts]
psdfy = "psdfy.cli:app"

[project.urls]
Homepage = "https://github.com/anomalyco/layer-psd-converter"
Issues   = "https://github.com/anomalyco/layer-psd-converter/issues"
```

### 31.7 Release Process

1. Bump version in `pyproject.toml` and CHANGELOG.
2. Tag `vX.Y.Z`.
3. CI builds wheel + sdist, publishes to PyPI via OIDC.
4. CI builds and pushes a Docker image.
5. (Optional) update Homebrew tap and Scoop bucket.
6. `psdfy update` users start receiving the new version.
