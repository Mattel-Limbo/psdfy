"""Mask dataclass and related schemas."""

from dataclasses import dataclass
from typing import Tuple, Dict
import numpy as np


@dataclass
class Mask:
    """Represents a single segmentation mask."""
    
    mask: np.ndarray  # Binary mask (H, W)
    bbox: Dict[str, int]  # {top, left, bottom, right}
    area: int  # Number of pixels in mask
    score: float  # Confidence score (0-1)
    label: str = "object"  # Object label
    
    def __post_init__(self):
        """Validate mask after initialization."""
        if self.mask.dtype != np.bool_:
            self.mask = self.mask.astype(np.bool_)
        
        # Calculate area if not provided
        if self.area == 0:
            self.area = int(self.mask.sum())
        
        # Validate score
        if not 0 <= self.score <= 1:
            self.score = float(np.clip(self.score, 0, 1))
