"""Shadow layer extraction service."""

import numpy as np
import cv2
from typing import Tuple, Optional

from app.schemas.mask import Mask


class ShadowBuilder:
    """Builds shadow layer using LAB color heuristic."""
    
    def __init__(
        self,
        darkness_threshold: float = 0.3,
        chroma_threshold: float = 30,
    ):
        """
        Initialize shadow builder.
        
        Args:
            darkness_threshold: Threshold for darkness detection
            chroma_threshold: Threshold for chroma (color saturation)
        """
        self.darkness_threshold = darkness_threshold
        self.chroma_threshold = chroma_threshold
    
    def detect_shadow(
        self,
        image: np.ndarray,
        foreground_masks: list,
    ) -> Optional[Mask]:
        """
        Detect shadow layer using LAB color heuristic.
        
        Args:
            image: RGB image (H, W, 3)
            foreground_masks: List of foreground Mask objects
            
        Returns:
            Shadow Mask or None if no shadow detected
        """
        # Convert to LAB
        image_lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        L, a, b = cv2.split(image_lab)
        
        # Create union of foreground masks
        foreground_union = np.zeros(image.shape[:2], dtype=np.bool_)
        for mask in foreground_masks:
            foreground_union = np.logical_or(foreground_union, mask.mask)
        
        # Candidate shadow = outside foreground AND dark AND low chroma
        background_area = ~foreground_union
        
        # Darkness: L < threshold
        dark_pixels = L < (255 * self.darkness_threshold)
        
        # Low chroma: sqrt(a^2 + b^2) < threshold
        chroma = np.sqrt(a.astype(np.float32) ** 2 + b.astype(np.float32) ** 2)
        low_chroma = chroma < self.chroma_threshold
        
        # Combine conditions
        shadow_candidate = background_area & dark_pixels & low_chroma
        
        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        shadow_mask = cv2.morphologyEx(
            shadow_candidate.astype(np.uint8),
            cv2.MORPH_CLOSE,
            kernel,
            iterations=2
        ).astype(np.bool_)
        
        # Check if shadow is significant
        shadow_area = shadow_mask.sum()
        if shadow_area < 100:  # Minimum 100 pixels
            return None
        
        # Create Mask object
        return Mask(
            mask=shadow_mask,
            bbox=self._calculate_bbox(shadow_mask),
            area=int(shadow_area),
            score=0.7,  # Shadow detection is heuristic
            label="shadow",
        )
    
    def _calculate_bbox(self, mask: np.ndarray) -> dict:
        """Calculate bounding box from mask."""
        non_zero = np.where(mask)
        if len(non_zero[0]) == 0:
            return {"top": 0, "left": 0, "bottom": 0, "right": 0}
        
        return {
            "top": int(non_zero[0].min()),
            "left": int(non_zero[1].min()),
            "bottom": int(non_zero[0].max()) + 1,
            "right": int(non_zero[1].max()) + 1,
        }


def get_shadow_builder() -> ShadowBuilder:
    """Get shadow builder instance."""
    return ShadowBuilder()
