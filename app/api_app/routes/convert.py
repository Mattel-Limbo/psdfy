"""Convert routes for the API app."""

import uuid
import time
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, Request
from typing import Optional, List
import numpy as np

from app.core.config import settings
from app.core.errors import (
    InvalidImageError,
    FileTooLargeError,
    UnsupportedMediaTypeError,
    UnauthorizedError,
)
from app.core.progress_tracker import AsyncProgressTracker
from app.utils.io import load_image
from app.services.segmenter import get_segmenter
from app.services.mask_postprocess import get_postprocessor
from app.services.layer_builder import get_layer_builder
from app.services.psd_writer import get_psd_writer
from app.services.preview_generator import get_preview_generator
from app.services.metadata_builder import get_metadata_builder
from app.storage.local_storage import get_local_storage
from app.schemas.convert import ConvertResponse

router = APIRouter(tags=["convert"])


@router.post("/convert", response_model=ConvertResponse)
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
        
    Raises:
        UnauthorizedError: If signature/session is invalid
        InvalidImageError: If image is corrupted or unsupported
        FileTooLargeError: If file exceeds size limit
        UnsupportedMediaTypeError: If file type is not supported
    """
    # Verify session is attached by middleware
    if not hasattr(request.state, "session"):
        raise UnauthorizedError("Missing or invalid signature")
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    request_id = getattr(request.state, "request_id", job_id)
    
    # Initialize progress tracker
    tracker = AsyncProgressTracker()
    
    # Start timing
    start_time = time.time()
    timings = {}
    
    storage = get_local_storage()
    
    try:
        # Validate mode
        if mode not in ("auto", "prompt"):
            raise InvalidImageError(f"Invalid mode '{mode}'. Must be 'auto' or 'prompt'")
        
        if mode == "prompt" and not prompt:
            raise InvalidImageError("prompt field is required when mode='prompt'")
        
        # Load and validate image
        tracker.start_stage("load", "📁 Loading image...")
        load_start = time.time()
        file_bytes = await file.read()
        image_array, (orig_width, orig_height), image_format = load_image(file_bytes)
        timings["load"] = time.time() - load_start
        tracker.complete_stage("load", f"✅ Image loaded ({orig_width}x{orig_height})")
        
        # Segmentation
        tracker.start_stage("segmentation", "🔍 Segmenting image...")
        seg_start = time.time()
        segmenter = get_segmenter()
        
        if mode == "auto":
            masks = segmenter.segment_auto(image_array)
        else:
            masks = segmenter.segment_with_prompt(image_array, prompt)
        
        timings["segmentation"] = time.time() - seg_start
        tracker.complete_stage("segmentation", f"✅ Segmentation complete ({len(masks)} masks)")
        
        # Post-process masks
        tracker.start_stage("postprocess", "🎨 Post-processing masks...")
        postproc_start = time.time()
        postprocessor = get_postprocessor()
        masks = postprocessor.process(masks, image_array.shape)
        timings["postprocess"] = time.time() - postproc_start
        tracker.complete_stage("postprocess", "✅ Post-processing complete")
        
        # Build layers
        tracker.start_stage("layer_build", "🏗️ Building layers...")
        layer_builder = get_layer_builder()
        
        # Background layer
        bg_rgba, bg_name, bg_bbox = layer_builder.build_background(image_array, masks)
        layers = [(bg_rgba, bg_name, bg_bbox)]
        
        # Object layers
        for rgba, layer_name, bbox in layer_builder.build_layers(image_array, masks):
            layers.append((rgba, layer_name, bbox))
        
        tracker.complete_stage("layer_build", f"✅ Built {len(layers)} layers")
        
        # Write PSD
        tracker.start_stage("psd_write", "💾 Writing PSD file...")
        psd_start = time.time()
        psd_writer = get_psd_writer()
        psd_bytes = psd_writer.write_psd(
            layers,
            orig_width,
            orig_height,
        )
        timings["psd_write"] = time.time() - psd_start
        tracker.complete_stage("psd_write", f"✅ PSD written ({len(psd_bytes) / 1024 / 1024:.1f}MB)")
        
        # Save PSD to storage
        psd_path = storage.save_psd(job_id, psd_bytes)
        psd_url = storage.get_file_url(psd_path)
        
        # Generate previews if requested
        preview_urls = None
        if return_previews:
            tracker.start_stage("previews", "🖼️ Generating previews...")
            preview_gen = get_preview_generator()
            previews = preview_gen.generate_all_previews(layers)
            
            preview_urls = []
            for idx, (layer_name, png_bytes) in enumerate(previews):
                preview_path = storage.save_preview(job_id, layer_name, png_bytes)
                preview_url = storage.get_file_url(preview_path)
                preview_urls.append({
                    "layer": layer_name,
                    "url": preview_url,
                })
                progress = ((idx + 1) / len(previews)) * 100
                tracker.update_stage("previews", progress, f"Generated {idx + 1}/{len(previews)} previews")
            
            tracker.complete_stage("previews", f"✅ Generated {len(preview_urls)} previews")
        
        # Generate metadata if requested
        metadata_dict = None
        if return_metadata:
            tracker.start_stage("metadata", "📋 Generating metadata...")
            metadata_builder = get_metadata_builder()
            metadata_dict = metadata_builder.build_metadata(
                job_id=job_id,
                image_filename=file.filename or "image",
                image_width=orig_width,
                image_height=orig_height,
                image_format=image_format,
                layers=layers,
                timings=timings,
            )
            
            # Save metadata to storage
            metadata_path = storage.save_metadata(job_id, metadata_dict)
            metadata_url = storage.get_file_url(metadata_path)
            metadata_dict["url"] = metadata_url
            tracker.complete_stage("metadata", "✅ Metadata generated")
        
        # Build response
        response = ConvertResponse(
            job_id=job_id,
            status="succeeded",
            psd={
                "url": psd_url,
                "size_bytes": len(psd_bytes),
                "layer_count": len(layers),
            },
            timing=timings,
            previews=preview_urls,
            metadata=metadata_dict,
            request_id=request_id,
        )
        
        timings["total"] = time.time() - start_time
        response.timing = timings
        
        return response
        
    except (InvalidImageError, FileTooLargeError, UnsupportedMediaTypeError) as e:
        # Clean up on error
        storage.cleanup_job(job_id)
        tracker.fail_stage("convert", str(e))
        raise
    except Exception as e:
        # Clean up on error
        storage.cleanup_job(job_id)
        tracker.fail_stage("convert", str(e))
        raise InvalidImageError(f"Conversion failed: {str(e)}")
