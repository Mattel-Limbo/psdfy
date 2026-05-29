"""GroundingDINO model loader."""

import os
from typing import Optional, List, Tuple
import numpy as np
from pathlib import Path

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
            # Import torch here to avoid import errors if not installed
            import torch
            
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
                    "~/.psdfy/weights/groundingdino_swint_ogc.pth"
                )
            
            # Check if weights exist
            if not os.path.exists(weights_path):
                raise ModelNotReadyError(
                    f"GroundingDINO weights not found at {weights_path}. "
                    "Run 'psdfy install' to download weights."
                )
            
            # Get config file path from groundingdino package
            try:
                import groundingdino
                groundingdino_dir = Path(groundingdino.__file__).parent
                # Try SwinT config first (matches groundingdino_swint_ogc.pth)
                config_file = groundingdino_dir / "config" / "GroundingDINO_SwinT_OGC.py"
                if not config_file.exists():
                    # Fallback to SwinB
                    config_file = groundingdino_dir / "config" / "GroundingDINO_SwinB_cfg.py"
                if not config_file.exists():
                    # Try any config file in the directory
                    configs = list((groundingdino_dir / "config").glob("*.py"))
                    if configs:
                        config_file = configs[0]
                    else:
                        raise FileNotFoundError("No GroundingDINO config file found")
            except Exception as e:
                raise ModelNotReadyError(
                    f"Failed to locate GroundingDINO config: {str(e)}"
                )
            
            # Compatibility patch: transformers 5.x removed BertModel.get_head_mask
            # which GroundingDINO's BERT encoder still calls internally.
            try:
                from transformers import BertModel
                import torch as _torch
                if not hasattr(BertModel, "get_head_mask"):
                    def _get_head_mask(self, head_mask, num_hidden_layers, is_attention_chunked=False):
                        if head_mask is not None:
                            if head_mask.dim() == 1:
                                head_mask = head_mask.unsqueeze(0).unsqueeze(0).unsqueeze(-1).unsqueeze(-1)
                                head_mask = head_mask.expand(num_hidden_layers, -1, -1, -1, -1)
                            elif head_mask.dim() == 2:
                                head_mask = head_mask.unsqueeze(1).unsqueeze(-1).unsqueeze(-1)
                            if is_attention_chunked:
                                head_mask = head_mask.unsqueeze(-1)
                        else:
                            head_mask = [None] * num_hidden_layers
                        return head_mask
                    BertModel.get_head_mask = _get_head_mask

                # Compatibility patch: transformers 5.x removed the 'device' positional
                # parameter from get_extended_attention_mask. GroundingDINO still passes
                # it positionally, so a torch.device ends up in the 'dtype' slot, causing
                # tensor.to(dtype=<device>) to fail. Detect and discard the misplaced arg.
                from transformers.modeling_utils import PreTrainedModel
                _orig_geam = PreTrainedModel.get_extended_attention_mask
                def _patched_geam(self, attention_mask, input_shape, device=None, dtype=None):
                    # If a torch.device was passed as dtype (transformers 5.x positional shift)
                    if isinstance(dtype, _torch.device):
                        dtype = None
                    if isinstance(device, _torch.device):
                        device = None
                    # Call original without the removed 'device' arg if signature changed
                    try:
                        return _orig_geam(self, attention_mask, input_shape, device, dtype)
                    except TypeError:
                        return _orig_geam(self, attention_mask, input_shape, dtype=dtype)
                PreTrainedModel.get_extended_attention_mask = _patched_geam
            except Exception:
                pass

            # Build model — build_model expects an SLConfig object, not a path string
            cfg = SLConfig.fromfile(str(config_file))
            self._model = build_model(cfg)
            
            # Load weights — strip DataParallel 'module.' prefix if present
            checkpoint = torch.load(weights_path, map_location=self.device)
            state_dict = checkpoint["model"]
            # Checkpoints saved with nn.DataParallel have 'module.' prefix on every key
            if all(k.startswith("module.") for k in state_dict.keys()):
                state_dict = {k[len("module."):]: v for k, v in state_dict.items()}
            self._model.load_state_dict(state_dict, strict=False)
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
