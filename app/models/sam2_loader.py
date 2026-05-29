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
            
            # Initialize Hydra with SAM2's config module before calling build_sam2.
            # build_sam2 uses hydra.compose() internally which requires this.
            from hydra.core.global_hydra import GlobalHydra
            from hydra import initialize_config_module
            import torch

            if not GlobalHydra.instance().is_initialized():
                initialize_config_module("sam2", version_base="1.2")

            # Build model architecture only (no checkpoint) — we load weights
            # manually so we can remap keys from old checkpoint format.
            self._model = build_sam2(
                config_file="configs/sam2/sam2_hiera_l.yaml",
                ckpt_path=None,
                device=self.device,
            )

            # Load checkpoint and remap old key names to new ones.
            # The original SAM2 release used different module names that were
            # renamed in later versions of the package:
            #   transformer.encoder.* → memory_attention.*
            #   maskmem_backbone.*    → memory_encoder.*
            _KEY_REMAP = {
                "transformer.encoder.": "memory_attention.",
                "maskmem_backbone.":    "memory_encoder.",
            }
            sd = torch.load(weights_path, map_location="cpu", weights_only=True)
            raw_sd = sd.get("model", sd)  # some checkpoints wrap under "model"
            remapped_sd = {}
            for k, v in raw_sd.items():
                new_k = k
                for old_prefix, new_prefix in _KEY_REMAP.items():
                    if k.startswith(old_prefix):
                        new_k = new_prefix + k[len(old_prefix):]
                        break
                remapped_sd[new_k] = v

            missing, unexpected = self._model.load_state_dict(remapped_sd, strict=False)
            # Filter out known non-critical keys before deciding to warn
            critical_missing = [k for k in missing if not k.startswith("no_mem_")]
            if critical_missing:
                import logging
                logging.warning(f"SAM2: missing keys after remap: {critical_missing[:5]}...")
            if unexpected:
                import logging
                logging.warning(f"SAM2: unexpected keys after remap: {unexpected[:5]}...")

            self._model.to(self.device)
            self._model.eval()
            
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
