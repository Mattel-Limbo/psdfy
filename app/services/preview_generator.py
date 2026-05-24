"""Preview PNG generator service."""

import io
from typing import List, Tuple
import numpy as np
from PIL import Image

from app.schemas.mask import Mask


class PreviewGenerator:
    """Generates preview PNGs for layers."""
    
    def generate_layer_preview(
        self,
        rgba: np.ndarray,
        layer_name: str,
    ) -> bytes:
        """
        Generate preview PNG for a layer.
        
        Args:
            rgba: RGBA image array (H, W, 4)
            layer_name: Layer name
            
        Returns:
            PNG file bytes
        """
        # Convert to PIL Image
        img = Image.fromarray(rgba, mode="RGBA")
        
        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def generate_all_previews(
        self,
        layers: List[Tuple[np.ndarray, str, dict]],
    ) -> List[Tuple[str, bytes]]:
        """
        Generate preview PNGs for all layers.
        
        Args:
            layers: List of (rgba_array, layer_name, bbox) tuples
            
        Returns:
            List of (layer_name, png_bytes) tuples
        """
        previews = []
        
        for rgba, layer_name, _ in layers:
            png_bytes = self.generate_layer_preview(rgba, layer_name)
            previews.append((layer_name, png_bytes))
        
        return previews


def get_preview_generator() -> PreviewGenerator:
    """Get preview generator instance."""
    return PreviewGenerator()
