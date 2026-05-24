"""Mask post-processing pipeline."""

from typing import List
import numpy as np
import cv2

from app.core.config import settings
from app.core.errors import SegmentationError
from app.schemas.mask import Mask
from app.utils.geometry import calculate_iou


class MaskPostprocessor:
    """Post-processes raw SAM 2 masks."""
    
    def __init__(
        self,
        min_area_ratio: float = None,
        max_area_ratio: float = 0.95,
        nms_iou_threshold: float = 0.85,
        feather_radius: int = 2,
    ):
        """
        Initialize post-processor.
        
        Args:
            min_area_ratio: Minimum mask area as ratio of image (default from config)
            max_area_ratio: Maximum mask area as ratio of image
            nms_iou_threshold: IoU threshold for NMS
            feather_radius: Radius for alpha feathering
        """
        self.min_area_ratio = min_area_ratio or settings.MIN_MASK_AREA_RATIO
        self.max_area_ratio = max_area_ratio
        self.nms_iou_threshold = nms_iou_threshold
        self.feather_radius = feather_radius
    
    def process(self, masks: List[Mask], image_shape: tuple) -> List[Mask]:
        """
        Post-process a list of masks.
        
        Args:
            masks: List of Mask objects
            image_shape: Image shape (height, width)
            
        Returns:
            Processed list of Mask objects
        """
        if not masks:
            return []
        
        height, width = image_shape[:2]
        image_area = height * width
        
        # Step 1: Filter by area
        masks = self._filter_by_area(masks, image_area)
        
        # Step 2: Morphological cleanup
        masks = self._morphological_cleanup(masks)
        
        # Step 3: Fill holes
        masks = self._fill_holes(masks)
        
        # Step 4: NMS (Non-Maximum Suppression)
        masks = self._nms(masks)
        
        # Step 5: Alpha feathering
        masks = self._feather_edges(masks)
        
        # Step 6: Sanity checks
        masks = self._sanity_check(masks)
        
        return masks
    
    def _filter_by_area(self, masks: List[Mask], image_area: int) -> List[Mask]:
        """Filter masks by area ratio."""
        filtered = []
        min_pixels = int(image_area * self.min_area_ratio)
        max_pixels = int(image_area * self.max_area_ratio)
        
        for mask in masks:
            if min_pixels <= mask.area <= max_pixels:
                filtered.append(mask)
        
        return filtered
    
    def _morphological_cleanup(self, masks: List[Mask]) -> List[Mask]:
        """Apply morphological open/close to remove specks."""
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        
        for mask in masks:
            # Morphological open (remove small objects)
            mask.mask = cv2.morphologyEx(
                mask.mask.astype(np.uint8),
                cv2.MORPH_OPEN,
                kernel,
                iterations=1
            ).astype(np.bool_)
            
            # Morphological close (fill small holes)
            mask.mask = cv2.morphologyEx(
                mask.mask.astype(np.uint8),
                cv2.MORPH_CLOSE,
                kernel,
                iterations=1
            ).astype(np.bool_)
            
            # Recalculate area
            mask.area = int(mask.mask.sum())
        
        return masks
    
    def _fill_holes(self, masks: List[Mask]) -> List[Mask]:
        """Fill internal holes in masks."""
        for mask in masks:
            # Find contours
            contours, _ = cv2.findContours(
                mask.mask.astype(np.uint8),
                cv2.RETR_TREE,
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            if contours:
                # Create filled mask
                filled = np.zeros_like(mask.mask)
                cv2.drawContours(filled, contours, 0, 1, -1)
                mask.mask = filled.astype(np.bool_)
                mask.area = int(mask.mask.sum())
        
        return masks
    
    def _nms(self, masks: List[Mask]) -> List[Mask]:
        """Non-Maximum Suppression by IoU."""
        if len(masks) <= 1:
            return masks
        
        # Sort by score (descending)
        masks = sorted(masks, key=lambda m: m.score, reverse=True)
        
        keep = []
        for i, mask_i in enumerate(masks):
            keep_mask = True
            
            for mask_j in keep:
                iou = calculate_iou(mask_i.mask, mask_j.mask)
                if iou > self.nms_iou_threshold:
                    keep_mask = False
                    break
            
            if keep_mask:
                keep.append(mask_i)
        
        return keep
    
    def _feather_edges(self, masks: List[Mask]) -> List[Mask]:
        """Apply alpha feathering to edges."""
        for mask in masks:
            # Create alpha channel with feathering
            alpha = mask.mask.astype(np.float32) * 255
            
            # Apply Gaussian blur for feathering
            alpha = cv2.GaussianBlur(
                alpha,
                (self.feather_radius * 2 + 1, self.feather_radius * 2 + 1),
                0
            )
            
            # Threshold to binary
            mask.mask = (alpha > 127).astype(np.bool_)
            mask.area = int(mask.mask.sum())
        
        return masks
    
    def _sanity_check(self, masks: List[Mask]) -> List[Mask]:
        """Perform sanity checks on masks."""
        valid = []
        
        for mask in masks:
            # Check for empty mask
            if mask.area == 0:
                continue
            
            # Check for NaNs
            if np.isnan(mask.mask).any():
                continue
            
            # Check for valid score
            if not (0 <= mask.score <= 1):
                mask.score = np.clip(mask.score, 0, 1)
            
            # Recalculate bbox
            mask.bbox = calculate_bbox(mask.mask)
            
            valid.append(mask)
        
        return valid


# Global post-processor instance
_postprocessor = None


def get_postprocessor() -> MaskPostprocessor:
    """Get or create post-processor instance."""
    global _postprocessor
    if _postprocessor is None:
        _postprocessor = MaskPostprocessor()
    return _postprocessor
