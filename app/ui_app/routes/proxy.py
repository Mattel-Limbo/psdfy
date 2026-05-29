"""UI proxy routes for server-side API calls."""

from fastapi import APIRouter, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import Optional
import httpx
import time

from app.core.config import settings
from app.core.errors import AppError

router = APIRouter(tags=["ui-proxy"])


def _rewrite_file_url(url: str) -> str:
    """
    Rewrite an API-app file URL to the UI-app download proxy path.

    The API returns absolute URLs like http://localhost:3456/files/<job>/<file>.
    The browser cannot attach auth headers to a plain <a href>, so we rewrite
    every such URL to /ui/files/<job>/<file> which is served by this app.
    """
    if not url:
        return url
    # Match against the configured public base URL
    prefix = settings.PUBLIC_BASE_URL.rstrip("/") + "/files/"
    if url.startswith(prefix):
        return "/ui/files/" + url[len(prefix):]
    # Fallback: match the internal API address directly
    internal = f"http://{settings.APP_HOST}:{settings.APP_API_PORT}/files/"
    if url.startswith(internal):
        return "/ui/files/" + url[len(internal):]
    return url


async def _get_api_session(client: httpx.AsyncClient) -> tuple[str, str]:
    """
    Obtain a session_id + client_signature from the API app.

    Returns:
        (session_id, client_signature)
    """
    client_secret = settings.CLIENT_SECRET
    if not client_secret:
        raise RuntimeError(
            "client_secret not configured. Re-run 'psdfy install' to regenerate config."
        )

    ts = str(int(time.time()))
    auth_url = f"http://{settings.APP_HOST}:{settings.APP_API_PORT}/auth/client-signature"

    resp = await client.post(
        auth_url,
        json={"clientSecret": client_secret, "clientUnixTimestamps": ts},
        timeout=10,
    )

    if not resp.is_success:
        raise RuntimeError(f"Auth failed: {resp.status_code} {resp.text}")

    data = resp.json()
    return data["sessionId"], data["clientSignature"]


@router.get("/api/capabilities")
async def capabilities_proxy(request: Request):
    """
    Proxy GET /capabilities from the API app.

    The UI fetches this to know which segmentation modes are available.
    This endpoint is public (no signature required).
    """
    try:
        api_url = f"http://{settings.APP_HOST}:{settings.APP_API_PORT}/capabilities"
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, timeout=10)
        return response.json()
    except Exception:
        # Fallback: return both modes if API is unreachable
        return {
            "modes": ["auto", "prompt"],
            "default_mode": "auto",
            "sam2_available": True,
            "dino_available": True,
        }


@router.get("/ui/files/{job_id}/{filename}")
async def download_file(request: Request, job_id: str, filename: str):
    """
    Serve output files (PSD, previews, metadata) directly from local storage.

    Browser download links cannot send custom auth headers, so all file
    downloads are routed through this UI-app endpoint instead of hitting
    the API app directly.  Access is gated by the UI session cookie which
    UISessionMiddleware already validates before this handler runs.
    """
    # Sanitise path components — prevent directory traversal
    safe_job_id = Path(job_id).name
    safe_filename = Path(filename).name

    file_path = Path(settings.STORAGE_LOCAL_DIR) / safe_job_id / safe_filename

    if not file_path.exists() or not file_path.is_file():
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "File not found"}},
        )

    return FileResponse(
        path=str(file_path),
        filename=safe_filename,
        media_type="application/octet-stream",
    )


@router.post("/ui/convert")
async def convert_proxy(
    request: Request,
    file: UploadFile = File(...),
    mode: Optional[str] = Form("auto"),
    prompt: Optional[str] = Form(None),
    return_previews: Optional[bool] = Form(False),
    return_metadata: Optional[bool] = Form(True),
):
    """
    Server-side proxy for /convert endpoint.

    Forwards request to Proxy API with session-bound signature.
    Browser never sees clientSecret or clientSignature.
    File download URLs are rewritten to /ui/files/... so the browser
    can download them without needing auth headers.
    """
    try:
        # Get session from request state (set by UISessionMiddleware as session_id)
        if not hasattr(request.state, "session_id"):
            return {"error": {"code": "UNAUTHORIZED", "message": "Not logged in"}}

        # Read file bytes
        file_bytes = await file.read()

        api_url = f"http://{settings.APP_HOST}:{settings.APP_API_PORT}/convert"

        async with httpx.AsyncClient() as client:
            # Get a fresh API session
            session_id, client_signature = await _get_api_session(client)

            # Forward to API
            response = await client.post(
                api_url,
                files={"file": (file.filename or "image", file_bytes)},
                data={
                    "mode": mode,
                    "prompt": prompt or "",
                    "return_previews": str(return_previews).lower(),
                    "return_metadata": str(return_metadata).lower(),
                },
                headers={
                    "X-Session-Id": session_id,
                    "X-Client-Signature": client_signature,
                },
                timeout=settings.CONVERT_TIMEOUT,
            )

        data = response.json()

        # Surface API errors clearly
        if not response.is_success:
            error_msg = data.get("error", {}).get("message", f"API error {response.status_code}")
            return {"error": {"code": "API_ERROR", "message": error_msg}}

        # Rewrite all file URLs to go through the UI download proxy so the
        # browser never needs to send auth headers directly to the API app.
        if isinstance(data.get("psd"), dict) and data["psd"].get("url"):
            data["psd"]["url"] = _rewrite_file_url(data["psd"]["url"])

        if isinstance(data.get("previews"), list):
            for preview in data["previews"]:
                if isinstance(preview, dict) and preview.get("url"):
                    preview["url"] = _rewrite_file_url(preview["url"])

        if isinstance(data.get("metadata"), dict) and data["metadata"].get("url"):
            data["metadata"]["url"] = _rewrite_file_url(data["metadata"]["url"])

        return data

    except httpx.TimeoutException:
        return {
            "error": {
                "code": "TIMEOUT",
                "message": "Konversi timeout. Coba lagi dengan gambar yang lebih kecil.",
            }
        }
    except Exception as e:
        return {
            "error": {
                "code": "PROXY_ERROR",
                "message": str(e),
            }
        }


@router.get("/ui/job/{job_id}")
async def get_job_status(request: Request, job_id: str):
    """Get job status (MVP: placeholder)."""
    if not hasattr(request.state, "session_id"):
        return {"error": {"code": "UNAUTHORIZED", "message": "Not logged in"}}

    return {
        "job_id": job_id,
        "status": "completed",
        "progress": 100,
    }

