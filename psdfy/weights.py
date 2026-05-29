"""Model weights downloader."""

import os
import hashlib
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error


class WeightsDownloader:
    """Downloads and verifies model weights."""
    
    # Model URLs and checksums
    MODELS = {
        "sam2": {
            # Versioned URL (092824 release) — matches key names expected by
            # the current sam2 package. The old unversioned URL produced
            # checkpoints with different key names (transformer.encoder.*,
            # maskmem_backbone.*) that require remapping in sam2_loader.py.
            "url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2_hiera_large.pt",
            "filename": "sam2_hiera_large.pt",
            "sha256": "unknown",  # TODO: Get actual checksum
        },
        "groundingdino": {
            "url": "https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth",
            "filename": "groundingdino_swint_ogc.pth",
            "sha256": "unknown",  # TODO: Get actual checksum
        },
    }
    
    def __init__(self, weights_dir: Optional[str] = None):
        """
        Initialize downloader.
        
        Args:
            weights_dir: Directory to store weights
        """
        if weights_dir:
            self.weights_dir = Path(weights_dir)
        else:
            self.weights_dir = Path.home() / ".psdfy" / "weights"
        
        self.weights_dir.mkdir(parents=True, exist_ok=True)
    
    def download_model(
        self,
        model_name: str,
        force: bool = False,
        progress_callback=None,
    ) -> Path:
        """
        Download a model.
        
        Args:
            model_name: Model name (sam2, groundingdino)
            force: Force re-download even if exists
            progress_callback: Callback for progress updates
            
        Returns:
            Path to downloaded file
        """
        if model_name not in self.MODELS:
            raise ValueError(f"Unknown model: {model_name}")
        
        model_info = self.MODELS[model_name]
        file_path = self.weights_dir / model_info["filename"]
        
        # Check if already exists
        if file_path.exists() and not force:
            if progress_callback:
                progress_callback(f"Model {model_name} already exists")
            return file_path
        
        # Download
        if progress_callback:
            progress_callback(f"Downloading {model_name}...")
        
        try:
            # Create request with User-Agent header
            request = urllib.request.Request(
                model_info["url"],
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            
            # Download file
            with urllib.request.urlopen(request) as response:
                total_size = int(response.headers.get('content-length', 0))
                block_size = 8192
                downloaded = 0
                
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Call progress callback
                        if progress_callback and total_size > 0:
                            progress_callback(f"Downloading {model_name}... {downloaded}/{total_size} bytes")
        except urllib.error.URLError as e:
            # Clean up partial download
            if file_path.exists():
                file_path.unlink()
            raise RuntimeError(f"Failed to download {model_name}: {e}")
        except Exception as e:
            # Clean up partial download
            if file_path.exists():
                file_path.unlink()
            raise RuntimeError(f"Failed to download {model_name}: {e}")
        
        # Verify checksum if available
        if model_info["sha256"] != "unknown":
            if progress_callback:
                progress_callback(f"Verifying {model_name}...")
            
            actual_sha256 = self._calculate_sha256(file_path)
            if actual_sha256 != model_info["sha256"]:
                file_path.unlink()
                raise RuntimeError(
                    f"Checksum mismatch for {model_name}. "
                    f"Expected {model_info['sha256']}, got {actual_sha256}"
                )
        
        if progress_callback:
            progress_callback(f"Downloaded {model_name}")
        
        return file_path
    
    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _make_progress_hook(self, callback):
        """Create progress hook for urlretrieve."""
        def hook(block_num, block_size, total_size):
            if callback and total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, int(100 * downloaded / total_size))
                # Use \r to overwrite the same line instead of creating new lines
                import sys
                sys.stdout.write(f"\rProgress: {percent}%")
                sys.stdout.flush()
        return hook


def get_weights_downloader(weights_dir: Optional[str] = None) -> WeightsDownloader:
    """Get weights downloader instance.
    
    Args:
        weights_dir: Optional directory to store weights
        
    Returns:
        WeightsDownloader instance
    """
    return WeightsDownloader(weights_dir)
