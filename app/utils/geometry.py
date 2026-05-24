"""Geometry utilities for bounding boxes and masks."""

from typing import Tuple, Dict


def calculate_bbox(mask: 'np.ndarray') -> Dict[str, int]:
    """
    Calculate bounding box from a binary mask.
    
    Args:
        mask: Binary mask array (H, W)
        
    Returns:
        Dict with keys: top, left, bottom, right
    """
    import numpy as np
    
    non_zero = np.where(mask)
    if len(non_zero[0]) == 0:
        return {"top": 0, "left": 0, "bottom": 0, "right": 0}
    
    return {
        "top": int(non_zero[0].min()),
        "left": int(non_zero[1].min()),
        "bottom": int(non_zero[0].max()) + 1,
        "right": int(non_zero[1].max()) + 1,
    }


def calculate_iou(mask1: 'np.ndarray', mask2: 'np.ndarray') -> float:
    """
    Calculate Intersection over Union (IoU) between two masks.
    
    Args:
        mask1: Binary mask array (H, W)
        mask2: Binary mask array (H, W)
        
    Returns:
        IoU value between 0 and 1
    """
    import numpy as np
    
    intersection = np.logical_and(mask1, mask2).sum()
    union = np.logical_or(mask1, mask2).sum()
    
    if union == 0:
        return 0.0
    
    return intersection / union


def crop_to_bbox(image: 'np.ndarray', bbox: Dict[str, int]) -> 'np.ndarray':
    """
    Crop image to bounding box.
    
    Args:
        image: Image array (H, W, C)
        bbox: Dict with keys: top, left, bottom, right
        
    Returns:
        Cropped image array
    """
    return image[bbox["top"]:bbox["bottom"], bbox["left"]:bbox["right"]]
