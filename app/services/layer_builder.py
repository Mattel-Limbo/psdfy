"""Layer builder service for creating RGBA layers from masks."""

from typing import List, Tuple
import numpy as np
from PIL import Image

from app.schemas.mask import Mask
from app.utils.geometry import calculate_bbox


class LayerBuilder:
    """Builds RGBA layers from masks."""
    
    def build_layers(
        self,
        image: np.ndarray,
        masks: List[Mask],
    ) -> List[Tuple[np.ndarray, str, dict]]:
        """
        Build RGBA layers from masks.
        
        Args:
            image: Original RGB image (H, W, 3)
            masks: List of Mask objects
            
        Returns:
            List of tuples: (rgba_layer, layer_name, bbox)
        """
        layers = []
        height, width = image.shape[:2]
        
        for i, mask in enumerate(masks):
            # Create RGBA layer at canvas size
            rgba = np.zeros((height, width, 4), dtype=np.uint8)
            
            # Copy RGB from image where mask is True
            rgba[mask.mask, :3] = image[mask.mask]
            
            # Set alpha channel
            rgba[mask.mask, 3] = 255
            
            # Layer name
            layer_name = mask.label or f"object_{i}"
            
            # Store layer with bbox
            layers.append((rgba, layer_name, mask.bbox))
        
        return layers
    
    def build_background(
        self,
        image: np.ndarray,
        masks: List[Mask],
    ) -> Tuple[np.ndarray, str, dict]:
        """
        Build background layer (image with foreground masks removed).
        
        Args:
            image: Original RGB image (H, W, 3)
            masks: List of Mask objects
            
        Returns:
            Tuple: (rgba_layer, layer_name, bbox)
        """
        height, width = image.shape[:2]
        
        # Create union of all foreground masks
        foreground_union = np.zeros((height, width), dtype=np.bool_)
        for mask in masks:
            foreground_union = np.logical_or(foreground_union, mask.mask)
        
        # Create background layer
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        
        # Copy RGB from image
        rgba[:, :, :3] = image
        
        # Set alpha: opaque where background, transparent where foreground
        rgba[:, :, 3] = (~foreground_union).astype(np.uint8) * 255
        
        # Calculate bbox (full canvas for now)
        bbox = {
            "top": 0,
            "left": 0,
            "bottom": height,
            "right": width,
        }
        
        return rgba, "background", bbox


def get_layer_builder() -> LayerBuilder:
    """Get layer builder instance."""
    return LayerBuilder()
