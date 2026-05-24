"""Metadata builder service."""

import json
from datetime import datetime
from typing import List, Tuple, Dict, Any
import numpy as np

from app.schemas.mask import Mask


class MetadataBuilder:
    """Builds metadata.json for conversion results."""
    
    def build_metadata(
        self,
        job_id: str,
        image_filename: str,
        image_width: int,
        image_height: int,
        image_format: str,
        layers: List[Tuple[np.ndarray, str, dict]],
        timings: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Build metadata dictionary.
        
        Args:
            job_id: Job ID
            image_filename: Original image filename
            image_width: Image width
            image_height: Image height
            image_format: Image format (JPEG, PNG, etc.)
            layers: List of (rgba_array, layer_name, bbox) tuples
            timings: Pipeline timings
            
        Returns:
            Metadata dictionary
        """
        # Build layer info
        layer_info = []
        for rgba, layer_name, bbox in layers:
            # Calculate area
            if rgba.shape[2] == 4:
                alpha = rgba[:, :, 3]
            else:
                alpha = np.ones((rgba.shape[0], rgba.shape[1]), dtype=np.uint8) * 255
            
            area = int((alpha > 0).sum())
            
            layer_info.append({
                "name": layer_name,
                "bbox": bbox,
                "area": area,
                "blend_mode": "normal",
            })
        
        # Build metadata
        metadata = {
            "job_id": job_id,
            "source": {
                "filename": image_filename,
                "width": image_width,
                "height": image_height,
                "format": image_format,
            },
            "model": {
                "segmenter": "SAM 2",
                "version": "1.0.0",
            },
            "layers": layer_info,
            "timing": timings,
            "generated_at": datetime.now().isoformat(),
        }
        
        return metadata


def get_metadata_builder() -> MetadataBuilder:
    """Get metadata builder instance."""
    return MetadataBuilder()
