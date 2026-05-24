"""PSD writer utility using pytoshop."""

import io
from typing import List, Tuple, Optional
import numpy as np
from PIL import Image

from app.core.errors import PSDWriteError


class Layer:
    """Represents a single layer in a PSD file."""
    
    def __init__(
        self,
        name: str,
        image: np.ndarray,
        blend_mode: str = "normal",
        opacity: int = 255,
    ):
        """
        Initialize a layer.
        
        Args:
            name: Layer name
            image: RGBA image array (H, W, 4)
            blend_mode: Blend mode (normal, multiply, screen, etc.)
            opacity: Layer opacity (0-255)
        """
        self.name = name
        self.image = image
        self.blend_mode = blend_mode
        self.opacity = opacity
        
        # Calculate bounding box
        if image.shape[2] == 4:
            alpha = image[:, :, 3]
        else:
            alpha = np.ones((image.shape[0], image.shape[1]), dtype=np.uint8) * 255
        
        # Find non-transparent pixels
        non_transparent = np.where(alpha > 0)
        if len(non_transparent[0]) > 0:
            self.top = int(non_transparent[0].min())
            self.left = int(non_transparent[1].min())
            self.bottom = int(non_transparent[0].max()) + 1
            self.right = int(non_transparent[1].max()) + 1
        else:
            self.top = 0
            self.left = 0
            self.bottom = image.shape[0]
            self.right = image.shape[1]
    
    @property
    def bbox(self) -> dict:
        """Get bounding box as dict."""
        return {
            "top": self.top,
            "left": self.left,
            "bottom": self.bottom,
            "right": self.right,
        }
    
    @property
    def area(self) -> int:
        """Get layer area in pixels."""
        return (self.bottom - self.top) * (self.right - self.left)


def create_simple_psd(
    image: np.ndarray,
    layer_name: str = "image",
) -> bytes:
    """
    Create a simple single-layer PSD from an image.
    
    Args:
        image: RGB image array (H, W, 3)
        layer_name: Name for the layer
        
    Returns:
        PSD file bytes
        
    Raises:
        PSDWriteError: If PSD creation fails
    """
    try:
        # Try to import pytoshop
        try:
            from pytoshop.user import Writer
            from pytoshop.constants import BlendMode
        except ImportError:
            raise PSDWriteError(
                "pytoshop not installed. Install with: pip install pytoshop"
            )
        
        height, width = image.shape[:2]
        
        # Convert RGB to RGBA (add full alpha channel)
        if image.shape[2] == 3:
            rgba = np.dstack([image, np.full((height, width), 255, dtype=np.uint8)])
        else:
            rgba = image
        
        # Create PSD in memory
        output = io.BytesIO()
        
        # Write PSD with pytoshop
        writer = Writer(
            width=width,
            height=height,
            depth=8,
            color_mode=3,  # RGB
            version=1,
        )
        
        # Add the image as a single layer
        # pytoshop expects channels in RGBA order
        channels = [
            rgba[:, :, 0],  # Red
            rgba[:, :, 1],  # Green
            rgba[:, :, 2],  # Blue
            rgba[:, :, 3],  # Alpha
        ]
        
        writer.write(output, [
            {
                "name": layer_name,
                "opacity": 255,
                "blend_mode": "normal",
                "channels": channels,
            }
        ])
        
        return output.getvalue()
        
    except PSDWriteError:
        raise
    except Exception as e:
        raise PSDWriteError(f"Failed to create PSD: {str(e)}")


def create_psd_from_layers(
    layers: List[Layer],
    canvas_width: int,
    canvas_height: int,
) -> bytes:
    """
    Create a multi-layer PSD from a list of layers.
    
    Args:
        layers: List of Layer objects
        canvas_width: Canvas width
        canvas_height: Canvas height
        
    Returns:
        PSD file bytes
        
    Raises:
        PSDWriteError: If PSD creation fails
    """
    try:
        try:
            from pytoshop.user import Writer
        except ImportError:
            raise PSDWriteError(
                "pytoshop not installed. Install with: pip install pytoshop"
            )
        
        output = io.BytesIO()
        
        writer = Writer(
            width=canvas_width,
            height=canvas_height,
            depth=8,
            color_mode=3,  # RGB
            version=1,
        )
        
        # Prepare layer data for pytoshop
        psd_layers = []
        for layer in layers:
            # Ensure RGBA format
            if layer.image.shape[2] == 3:
                rgba = np.dstack([
                    layer.image,
                    np.full((layer.image.shape[0], layer.image.shape[1]), 255, dtype=np.uint8)
                ])
            else:
                rgba = layer.image
            
            channels = [
                rgba[:, :, 0],  # Red
                rgba[:, :, 1],  # Green
                rgba[:, :, 2],  # Blue
                rgba[:, :, 3],  # Alpha
            ]
            
            psd_layers.append({
                "name": layer.name,
                "opacity": layer.opacity,
                "blend_mode": layer.blend_mode,
                "channels": channels,
            })
        
        writer.write(output, psd_layers)
        
        return output.getvalue()
        
    except PSDWriteError:
        raise
    except Exception as e:
        raise PSDWriteError(f"Failed to create multi-layer PSD: {str(e)}")
