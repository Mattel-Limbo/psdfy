"""GroundingDINO model loader."""

import os
from typing import Optional, List, Tuple
import numpy as np

from app.core.config import settings
from app.core.errors import ModelNotReadyError


class GroundingDINOLoader:
    """Lazy loader for GroundingDINO model."""
    
    _instance = None
    _model = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize loader."""
        self.model_loaded = False
        self.device = settings.DEVICE if hasattr(settings, 'DEVICE') else 'cpu'
    
    def load(self, force_reload: bool = False) -> 'GroundingDINO':
        """
        Load GroundingDINO model lazily.
        
        Args:
            force_reload: Force reload even if already loaded
            
        Returns:
            GroundingDINO model instance
            
        Raises:
            ModelNotReadyError: If model cannot be loaded
        """
        if self._model is not None and not force_reload:
            return self._model
        
        try:
            # Try to import GroundingDINO
            try:
                from groundingdino.models import build_model
                from groundingdino.util.slconfig import SLConfig
            except ImportError:
                raise ModelNotReadyError(
                    "GroundingDINO not installed. Install with: "
                    "pip install git+https://github.com/IDEA-Research/GroundingDINO.git"
                )
            
            # Get weights path
            weights_path = getattr(settings, 'DINO_WEIGHTS_PATH', None)
            if not weights_path:
                weights_path = os.path.expanduser(
                    "~/.psdfy/weights/groundingdino_swinb_cogvlm.pth"
                )
            
            # Check if weights exist
            if not os.path.exists(weights_path):
                raise ModelNotReadyError(
                    f"GroundingDINO weights not found at {weights_path}. "
                    "Run 'psdfy install' to download weights."
                )
            
            # Build model
            config_file = "groundingdino/config/GroundingDINO_SwinB_cfg.py"
            self._model = build_model(config_file)
            
            # Load weights
            checkpoint = torch.load(weights_path, map_location=self.device)
            self._model.load_state_dict(checkpoint["model"])
            self._model.to(self.device)
            self._model.eval()
            
            self.model_loaded = True
            return self._model
            
        except ModelNotReadyError:
            raise
        except Exception as e:
            raise ModelNotReadyError(f"Failed to load GroundingDINO: {str(e)}")
    
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self.model_loaded and self._model is not None


def get_grounding_dino_loader() -> GroundingDINOLoader:
    """Get or create GroundingDINO loader instance."""
    return GroundingDINOLoader()
