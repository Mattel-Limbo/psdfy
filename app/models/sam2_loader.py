"""SAM 2 model loader."""

import os
from typing import Optional
import numpy as np

from app.core.config import settings
from app.core.errors import ModelNotReadyError


class SAM2Loader:
    """Lazy loader for SAM 2 model."""
    
    _instance = None
    _model = None
    _device = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize loader."""
        self.model_loaded = False
        self.device = settings.DEVICE if hasattr(settings, 'DEVICE') else 'cpu'
    
    def load(self, force_reload: bool = False) -> 'SAM2':
        """
        Load SAM 2 model lazily.
        
        Args:
            force_reload: Force reload even if already loaded
            
        Returns:
            SAM2 model instance
            
        Raises:
            ModelNotReadyError: If model cannot be loaded
        """
        if self._model is not None and not force_reload:
            return self._model
        
        try:
            # Try to import SAM 2
            try:
                from sam2.build_sam import build_sam2
            except ImportError:
                raise ModelNotReadyError(
                    "SAM 2 not installed. Install with: pip install git+https://github.com/facebookresearch/sam2.git"
                )
            
            # Get weights path
            weights_path = getattr(settings, 'SAM2_WEIGHTS_PATH', None)
            if not weights_path:
                weights_path = os.path.expanduser("~/.psdfy/weights/sam2_hiera_large.pt")
            
            # Check if weights exist
            if not os.path.exists(weights_path):
                raise ModelNotReadyError(
                    f"SAM 2 weights not found at {weights_path}. "
                    "Run 'psdfy install' to download weights."
                )
            
            # Build model
            self._model = build_sam2(
                config_file="configs/sam2_hiera_l.yaml",
                ckpt_path=weights_path,
                device=self.device,
            )
            
            self.model_loaded = True
            return self._model
            
        except ModelNotReadyError:
            raise
        except Exception as e:
            raise ModelNotReadyError(f"Failed to load SAM 2: {str(e)}")
    
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self.model_loaded and self._model is not None


# Global loader instance
_sam2_loader = None


def get_sam2_loader() -> SAM2Loader:
    """Get or create SAM 2 loader instance."""
    global _sam2_loader
    if _sam2_loader is None:
        _sam2_loader = SAM2Loader()
    return _sam2_loader
