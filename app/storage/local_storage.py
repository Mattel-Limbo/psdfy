"""Local storage backend for saving conversion outputs."""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.config import settings
from app.core.errors import AppError


class LocalStorage:
    """Local filesystem storage backend."""
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize local storage.
        
        Args:
            base_dir: Base directory for storage (default from config)
        """
        self.base_dir = Path(base_dir or settings.STORAGE_LOCAL_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def get_job_dir(self, job_id: str) -> Path:
        """Get directory for a job."""
        job_dir = self.base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir
    
    def save_psd(self, job_id: str, psd_bytes: bytes) -> str:
        """
        Save PSD file.
        
        Args:
            job_id: Job ID
            psd_bytes: PSD file bytes
            
        Returns:
            Relative path to saved file
        """
        job_dir = self.get_job_dir(job_id)
        psd_path = job_dir / "output.psd"
        
        with open(psd_path, "wb") as f:
            f.write(psd_bytes)
        
        return f"{job_id}/output.psd"
    
    def save_preview(self, job_id: str, layer_name: str, png_bytes: bytes) -> str:
        """
        Save preview PNG for a layer.
        
        Args:
            job_id: Job ID
            layer_name: Layer name
            png_bytes: PNG file bytes
            
        Returns:
            Relative path to saved file
        """
        job_dir = self.get_job_dir(job_id)
        preview_path = job_dir / f"preview_{layer_name}.png"
        
        with open(preview_path, "wb") as f:
            f.write(png_bytes)
        
        return f"{job_id}/preview_{layer_name}.png"
    
    def save_metadata(self, job_id: str, metadata: Dict[str, Any]) -> str:
        """
        Save metadata JSON.
        
        Args:
            job_id: Job ID
            metadata: Metadata dictionary
            
        Returns:
            Relative path to saved file
        """
        job_dir = self.get_job_dir(job_id)
        metadata_path = job_dir / "metadata.json"
        
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return f"{job_id}/metadata.json"
    
    def get_file_url(self, relative_path: str) -> str:
        """
        Get public URL for a file.
        
        Args:
            relative_path: Relative path from storage root
            
        Returns:
            Public URL
        """
        base_url = settings.PUBLIC_BASE_URL
        return f"{base_url}/files/{relative_path}"
    
    def cleanup_job(self, job_id: str) -> None:
        """
        Clean up job directory (on failure).
        
        Args:
            job_id: Job ID
        """
        job_dir = self.get_job_dir(job_id)
        
        # Remove all files in job directory
        for file_path in job_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        
        # Remove job directory if empty
        try:
            job_dir.rmdir()
        except OSError:
            pass


def get_local_storage() -> LocalStorage:
    """Get local storage instance."""
    return LocalStorage()
