"""Schemas for convert endpoint request/response."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ConvertRequest(BaseModel):
    """Convert endpoint request model."""
    
    mode: str = Field(
        default="auto",
        description="Segmentation mode: 'auto' (SAM 2) or 'prompt' (GroundingDINO). "
                    "Available modes depend on installed models. Call GET /capabilities to check availability."
    )
    prompt: Optional[str] = Field(default=None, description="Text prompt for GroundingDINO mode (required when mode='prompt')")
    return_previews: bool = Field(default=False, description="Whether to return preview PNGs")
    return_metadata: bool = Field(default=True, description="Whether to return metadata.json")


class LayerInfo(BaseModel):
    """Information about a single layer in the PSD."""
    
    name: str
    bbox: dict = Field(description="Bounding box: {top, left, bottom, right}")
    area: int = Field(description="Area in pixels")
    blend_mode: str = Field(default="normal")


class ConvertResponse(BaseModel):
    """Convert endpoint response model."""
    
    job_id: str = Field(description="Unique job identifier")
    status: str = Field(description="Job status: 'succeeded', 'failed', 'queued'")
    psd: dict = Field(description="PSD file info: {url, size_bytes, layer_count}")
    timing: dict = Field(
        description="Pipeline stage timings in seconds: {load, segmentation, postprocess, psd_write, total}"
    )
    previews: Optional[List[dict]] = Field(
        default=None,
        description="List of preview URLs if return_previews=true"
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Metadata dict if return_metadata=true"
    )
    request_id: str = Field(description="Request ID for tracing")


class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: dict = Field(description="Error details: {code, message, request_id}")


class MetadataResponse(BaseModel):
    """Metadata.json response model."""
    
    job_id: str
    source: dict = Field(description="Source image info: {filename, width, height, format}")
    model: dict = Field(description="Model info: {segmenter, version}")
    layers: List[LayerInfo]
    generated_at: datetime
