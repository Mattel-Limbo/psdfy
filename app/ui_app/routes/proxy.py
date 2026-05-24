"""UI proxy routes for server-side API calls."""

from fastapi import APIRouter, UploadFile, File, Form, Request
from typing import Optional
import httpx
import json

from app.core.config import settings
from app.core.errors import AppError

router = APIRouter(tags=["ui-proxy"])


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
    """
    try:
        # Get session from request state
        if not hasattr(request.state, "session"):
            return {"error": {"code": "UNAUTHORIZED", "message": "Not logged in"}}
        
        # Get signature manager
        signature_manager = request.app.state.signature_manager
        
        # Issue a new signature for this request
        session_id, client_signature = signature_manager.issue_signature(
            client_secret=settings.SIGNATURE_SECRET_PEPPER or "default-secret"
        )
        
        # Read file bytes
        file_bytes = await file.read()
        
        # Forward to Proxy API
        api_url = f"http://{settings.APP_HOST}:{settings.APP_API_PORT}/convert"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                files={"file": ("image", file_bytes)},
                data={
                    "mode": mode,
                    "prompt": prompt,
                    "return_previews": return_previews,
                    "return_metadata": return_metadata,
                },
                headers={
                    "X-Session-Id": session_id,
                    "X-Client-Signature": client_signature,
                },
                timeout=settings.APP_REQUEST_TIMEOUT,
            )
        
        return response.json()
        
    except Exception as e:
        return {
            "error": {
                "code": "PROXY_ERROR",
                "message": str(e),
            }
        }


@router.get("/ui/job/{job_id}")
async def get_job_status(
    request: Request,
    job_id: str,
):
    """
    Get job status and progress.
    
    For MVP, returns immediate result.
    TODO: Implement async job queue in Issue #28.
    """
    try:
        # Get session from request state
        if not hasattr(request.state, "session"):
            return {"error": {"code": "UNAUTHORIZED", "message": "Not logged in"}}
        
        # For now, return placeholder
        return {
            "job_id": job_id,
            "status": "completed",
            "progress": 100,
            "stages": {
                "load": {"status": "completed", "progress": 100},
                "segmentation": {"status": "completed", "progress": 100},
                "postprocess": {"status": "completed", "progress": 100},
                "psd_write": {"status": "completed", "progress": 100},
            },
        }
        
    except Exception as e:
        return {
            "error": {
                "code": "JOB_ERROR",
                "message": str(e),
            }
        }
