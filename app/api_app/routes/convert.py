"""Convert routes for the API app."""

from fastapi import APIRouter, UploadFile, File, Form, Request
from typing import Optional

router = APIRouter(tags=["convert"])


@router.post("/convert")
async def convert(
    request: Request,
    file: UploadFile = File(...),
    mode: Optional[str] = Form("auto"),
    prompt: Optional[str] = Form(None),
    return_previews: Optional[bool] = Form(False),
    return_metadata: Optional[bool] = Form(True),
):
    """
    Convert an image to a multi-layer PSD file.
    
    This endpoint requires valid X-Session-Id and X-Client-Signature headers.
    
    Args:
        request: FastAPI request object
        file: Image file (jpg, jpeg, png, webp)
        mode: Segmentation mode ('auto' or 'prompt')
        prompt: Optional text prompt for GroundingDINO mode
        return_previews: Whether to return preview PNGs
        return_metadata: Whether to return metadata.json
    
    Returns:
        JSON response with PSD URL and optional previews/metadata
    """
    # Verify session is attached by middleware
    if not hasattr(request.state, "session"):
        return {
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Missing or invalid signature",
                "request_id": request.state.request_id,
            }
        }
    
    # TODO: Implement actual conversion logic
    # For now, return a placeholder response
    return {
        "job_id": "placeholder-job-id",
        "status": "succeeded",
        "psd": {
            "url": "/files/placeholder/output.psd",
            "size_bytes": 0,
            "layer_count": 0,
        },
        "message": "Conversion endpoint is not yet implemented",
    }
