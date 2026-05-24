"""Layer naming and deduplication improvements."""

from typing import List
import numpy as np

from app.schemas.mask import Mask
from app.utils.geometry import calculate_iou
from app.utils.naming import sanitize_layer_name


class LayerNamer:
    """Handles layer naming and deduplication."""
    
    def __init__(self, iou_threshold: float = 0.85):
        """
        Initialize layer namer.
        
        Args:
            iou_threshold: IoU threshold for deduplication
        """
        self.iou_threshold = iou_threshold
    
    def deduplicate_masks(self, masks: List[Mask]) -> List[Mask]:
        """
        Remove duplicate masks using IoU threshold.
        
        Args:
            masks: List of Mask objects
            
        Returns:
            Deduplicated list of Mask objects
        """
        if len(masks) <= 1:
            return masks
        
        # Sort by score (descending)
        sorted_masks = sorted(masks, key=lambda m: m.score, reverse=True)
        
        keep = []
        for mask_i in sorted_masks:
            is_duplicate = False
            
            for mask_j in keep:
                iou = calculate_iou(mask_i.mask, mask_j.mask)
                if iou > self.iou_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                keep.append(mask_i)
        
        return keep
    
    def assign_layer_names(
        self,
        masks: List[Mask],
        use_labels: bool = True,
    ) -> List[Mask]:
        """
        Assign meaningful names to layers.
        
        Args:
            masks: List of Mask objects
            use_labels: Use detected labels if available
            
        Returns:
            Masks with assigned names
        """
        # Sort by area (descending)
        sorted_masks = sorted(masks, key=lambda m: m.area, reverse=True)
        
        # Assign names
        for i, mask in enumerate(sorted_masks):
            if use_labels and mask.label and mask.label != "object":
                # Use detected label
                mask.label = sanitize_layer_name(mask.label)
            else:
                # Use generic name
                mask.label = f"object_{i}"
        
        return sorted_masks
    
    def order_layers(
        self,
        masks: List[Mask],
        image_height: int,
    ) -> List[Mask]:
        """
        Order layers for PSD composition.
        
        Order: background, shadow, static objects (by area), 
        foreground objects (by vertical position), main_object on top.
        
        Args:
            masks: List of Mask objects
            image_height: Image height for vertical position calculation
            
        Returns:
            Ordered list of Mask objects
        """
        # Separate by type
        main_object = None
        static_objects = []
        foreground_objects = []
        
        # Find main object (largest non-full mask)
        for mask in masks:
            if mask.area > 0.5 * (image_height * image_height):
                # Likely background or full image
                continue
            if main_object is None or mask.area > main_object.area:
                if main_object is not None:
                    static_objects.append(main_object)
                main_object = mask
            else:
                static_objects.append(mask)
        
        # Sort static objects by area (descending)
        static_objects.sort(key=lambda m: m.area, reverse=True)
        
        # Sort foreground by vertical position (lower y = closer to camera)
        foreground_objects.sort(key=lambda m: m.bbox["top"])
        
        # Combine in order
        ordered = []
        if static_objects:
            ordered.extend(static_objects)
        if foreground_objects:
            ordered.extend(foreground_objects)
        if main_object:
            ordered.append(main_object)
        
        return ordered


def get_layer_namer() -> LayerNamer:
    """Get layer namer instance."""
    return LayerNamer()
