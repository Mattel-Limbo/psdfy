"""Alpha matting service for edge refinement."""

import numpy as np
import cv2
from typing import Optional

from app.schemas.mask import Mask


class AlphaMattingService:
    """Refines mask edges using alpha matting."""
    
    def __init__(self, enable_matting: bool = False):
        """
        Initialize alpha matting service.
        
        Args:
            enable_matting: Enable alpha matting (requires pymatting)
        """
        self.enable_matting = enable_matting
        self.matting_available = False
        
        if enable_matting:
            try:
                import pymatting
                self.matting_available = True
            except ImportError:
                pass
    
    def refine_mask(self, mask: Mask, image: np.ndarray) -> Mask:
        """
        Refine mask edges using alpha matting.
        
        Args:
            mask: Input Mask object
            image: RGB image (H, W, 3)
            
        Returns:
            Refined Mask object
        """
        if not self.enable_matting or not self.matting_available:
            return mask
        
        try:
            import pymatting
            
            # Create trimap from mask
            trimap = self._create_trimap(mask.mask)
            
            # Run alpha matting
            alpha = pymatting.estimate_alpha_cf(image, trimap)
            
            # Convert alpha to binary mask with soft edges
            refined_mask = (alpha > 0.5).astype(np.bool_)
            
            # Update mask
            mask.mask = refined_mask
            mask.area = int(refined_mask.sum())
            
            return mask
            
        except Exception:
            # Fall back to original mask on error
            return mask
    
    def _create_trimap(self, mask: np.ndarray) -> np.ndarray:
        """
        Create trimap from binary mask.
        
        Trimap: 0=background, 128=unknown, 255=foreground
        
        Args:
            mask: Binary mask (H, W)
            
        Returns:
            Trimap (H, W)
        """
        trimap = np.zeros_like(mask, dtype=np.uint8)
        
        # Foreground
        trimap[mask] = 255
        
        # Unknown region (dilate mask slightly)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dilated = cv2.dilate(mask.astype(np.uint8), kernel, iterations=2)
        
        # Unknown = dilated - original
        unknown = dilated & ~mask.astype(np.uint8)
        trimap[unknown.astype(np.bool_)] = 128
        
        return trimap


def get_alpha_matting_service() -> AlphaMattingService:
    """Get alpha matting service instance."""
    return AlphaMattingService(enable_matting=False)  # Disabled by default
