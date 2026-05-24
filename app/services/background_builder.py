"""Background builder service."""

from typing import Tuple
import numpy as np

from app.schemas.mask import Mask
from typing import List


class BackgroundBuilder:
    """Builds background layer with optional inpainting."""
    
    def build_simple_background(
        self,
        image: np.ndarray,
        masks: List[Mask],
    ) -> Tuple[np.ndarray, dict]:
        """
        Build simple background (image with foreground masks removed).
        
        Args:
            image: Original RGB image (H, W, 3)
            masks: List of Mask objects
            
        Returns:
            Tuple: (rgba_layer, bbox)
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
        
        # Calculate bbox
        bbox = {
            "top": 0,
            "left": 0,
            "bottom": height,
            "right": width,
        }
        
        return rgba, bbox
    
    def build_inpainted_background(
        self,
        image: np.ndarray,
        masks: List[Mask],
        use_lama: bool = False,
    ) -> Tuple[np.ndarray, dict]:
        """
        Build inpainted background (fill holes where foreground was).
        
        Args:
            image: Original RGB image (H, W, 3)
            masks: List of Mask objects
            use_lama: Use LaMa for inpainting (requires model)
            
        Returns:
            Tuple: (rgb_layer, bbox)
        """
        import cv2
        
        height, width = image.shape[:2]
        
        # Create union of all foreground masks
        foreground_union = np.zeros((height, width), dtype=np.bool_)
        for mask in masks:
            foreground_union = np.logical_or(foreground_union, mask.mask)
        
        # Dilate mask slightly to ensure coverage
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dilated_mask = cv2.dilate(
            foreground_union.astype(np.uint8),
            kernel,
            iterations=2
        ).astype(np.bool_)
        
        # Inpaint
        if use_lama:
            # TODO: Implement LaMa inpainting in Issue #25
            background = self._inpaint_cv2(image, dilated_mask)
        else:
            background = self._inpaint_cv2(image, dilated_mask)
        
        # Create RGBA layer (fully opaque)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[:, :, :3] = background
        rgba[:, :, 3] = 255
        
        # Calculate bbox
        bbox = {
            "top": 0,
            "left": 0,
            "bottom": height,
            "right": width,
        }
        
        return rgba, bbox
    
    def _inpaint_cv2(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        Inpaint using OpenCV (fast fallback).
        
        Args:
            image: RGB image
            mask: Binary mask of areas to inpaint
            
        Returns:
            Inpainted image
        """
        import cv2
        
        # Convert to uint8 if needed
        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8)
        
        mask_uint8 = mask.astype(np.uint8) * 255
        
        # Use Telea's algorithm for inpainting
        inpainted = cv2.inpaint(
            image,
            mask_uint8,
            radius=3,
            flags=cv2.INPAINT_TELEA
        )
        
        return inpainted


def get_background_builder() -> BackgroundBuilder:
    """Get background builder instance."""
    return BackgroundBuilder()
