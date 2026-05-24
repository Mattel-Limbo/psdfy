"""PSD writer service using pytoshop."""

import io
from typing import List, Tuple, Optional
import numpy as np

from app.core.errors import PSDWriteError


class PSDWriter:
    """Writes multi-layer PSD files."""
    
    def write_psd(
        self,
        layers: List[Tuple[np.ndarray, str, dict]],
        canvas_width: int,
        canvas_height: int,
    ) -> bytes:
        """
        Write a multi-layer PSD file.
        
        Args:
            layers: List of (rgba_array, layer_name, bbox) tuples
            canvas_width: Canvas width
            canvas_height: Canvas height
            
        Returns:
            PSD file bytes
            
        Raises:
            PSDWriteError: If PSD writing fails
        """
        try:
            try:
                from pytoshop.user import Writer
            except ImportError:
                raise PSDWriteError(
                    "pytoshop not installed. Install with: pip install pytoshop"
                )
            
            output = io.BytesIO()
            
            # Create writer
            writer = Writer(
                width=canvas_width,
                height=canvas_height,
                depth=8,
                color_mode=3,  # RGB
                version=1,
            )
            
            # Prepare layer data
            psd_layers = []
            for rgba, layer_name, bbox in layers:
                # Ensure RGBA format
                if rgba.shape[2] == 3:
                    rgba = np.dstack([
                        rgba,
                        np.full((rgba.shape[0], rgba.shape[1]), 255, dtype=np.uint8)
                    ])
                
                # Extract channels
                channels = [
                    rgba[:, :, 0],  # Red
                    rgba[:, :, 1],  # Green
                    rgba[:, :, 2],  # Blue
                    rgba[:, :, 3],  # Alpha
                ]
                
                psd_layers.append({
                    "name": layer_name,
                    "opacity": 255,
                    "blend_mode": "normal",
                    "channels": channels,
                })
            
            # Write PSD
            writer.write(output, psd_layers)
            
            return output.getvalue()
            
        except PSDWriteError:
            raise
        except Exception as e:
            raise PSDWriteError(f"Failed to write PSD: {str(e)}")
    
    def write_simple_psd(
        self,
        image: np.ndarray,
        layer_name: str = "image",
    ) -> bytes:
        """
        Write a simple single-layer PSD.
        
        Args:
            image: RGB image array (H, W, 3)
            layer_name: Name for the layer
            
        Returns:
            PSD file bytes
            
        Raises:
            PSDWriteError: If PSD writing fails
        """
        height, width = image.shape[:2]
        
        # Convert to RGBA
        if image.shape[2] == 3:
            rgba = np.dstack([image, np.full((height, width), 255, dtype=np.uint8)])
        else:
            rgba = image
        
        # Create single layer
        layers = [(rgba, layer_name, {
            "top": 0,
            "left": 0,
            "bottom": height,
            "right": width,
        })]
        
        return self.write_psd(layers, width, height)


def get_psd_writer() -> PSDWriter:
    """Get PSD writer instance."""
    return PSDWriter()
