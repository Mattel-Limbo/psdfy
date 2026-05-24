"""Image I/O utilities for loading and validating images."""

import io
from typing import Tuple
import numpy as np
from PIL import Image

from app.core.config import settings
from app.core.errors import (
    InvalidImageError,
    FileTooLargeError,
    UnsupportedMediaTypeError,
)


# Allowed MIME types and their magic bytes
ALLOWED_MIMES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG"],
    "image/webp": [b"RIFF"],  # RIFF....WEBP
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_file_magic(file_bytes: bytes) -> str:
    """
    Validate file magic bytes and return MIME type.
    
    Args:
        file_bytes: Raw file bytes
        
    Returns:
        MIME type string
        
    Raises:
        UnsupportedMediaTypeError: If file type is not supported
    """
    if len(file_bytes) < 4:
        raise UnsupportedMediaTypeError("File too small to determine type")
    
    # Check magic bytes
    for mime, magic_bytes_list in ALLOWED_MIMES.items():
        for magic_bytes in magic_bytes_list:
            if file_bytes.startswith(magic_bytes):
                return mime
    
    raise UnsupportedMediaTypeError(
        f"Unsupported file type. Allowed: {', '.join(ALLOWED_MIMES.keys())}"
    )


def validate_file_size(file_bytes: bytes) -> None:
    """
    Validate file size against MAX_UPLOAD_MB limit.
    
    Args:
        file_bytes: Raw file bytes
        
    Raises:
        FileTooLargeError: If file exceeds size limit
    """
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(
            f"File size {len(file_bytes) / 1024 / 1024:.1f}MB exceeds limit of {settings.MAX_UPLOAD_MB}MB"
        )


def load_image(file_bytes: bytes) -> Tuple[np.ndarray, Tuple[int, int], str]:
    """
    Load and validate image from bytes.
    
    Args:
        file_bytes: Raw file bytes
        
    Returns:
        Tuple of (image_array, (width, height), format)
        - image_array: RGB NumPy array (H, W, 3)
        - (width, height): Original image dimensions
        - format: Image format (JPEG, PNG, WEBP)
        
    Raises:
        InvalidImageError: If image cannot be loaded or is corrupted
    """
    try:
        # Validate file size
        validate_file_size(file_bytes)
        
        # Validate MIME type
        mime_type = validate_file_magic(file_bytes)
        
        # Load image with PIL
        img = Image.open(io.BytesIO(file_bytes))
        
        # Get format
        fmt = img.format or "UNKNOWN"
        
        # Check dimensions
        width, height = img.size
        if width > settings.MAX_IMAGE_DIM or height > settings.MAX_IMAGE_DIM:
            raise InvalidImageError(
                f"Image dimensions {width}x{height} exceed limit of {settings.MAX_IMAGE_DIM}x{settings.MAX_IMAGE_DIM}"
            )
        
        if width < 64 or height < 64:
            raise InvalidImageError(
                f"Image dimensions {width}x{height} too small (minimum 64x64)"
            )
        
        # Convert to RGB if needed
        if img.mode in ("RGBA", "LA", "P"):
            # Create white background for transparency
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
        
        # Convert to NumPy array
        img_array = np.array(img)
        
        return img_array, (width, height), fmt
        
    except InvalidImageError:
        raise
    except FileTooLargeError:
        raise
    except UnsupportedMediaTypeError:
        raise
    except Exception as e:
        raise InvalidImageError(f"Failed to load image: {str(e)}")


def resize_image_keep_aspect(
    image: np.ndarray,
    max_size: int
) -> Tuple[np.ndarray, float]:
    """
    Resize image keeping aspect ratio if larger than max_size.
    
    Args:
        image: Input image array (H, W, 3)
        max_size: Maximum dimension
        
    Returns:
        Tuple of (resized_image, scale_factor)
    """
    height, width = image.shape[:2]
    
    if max(height, width) <= max_size:
        return image, 1.0
    
    scale = max_size / max(height, width)
    new_height = int(height * scale)
    new_width = int(width * scale)
    
    resized = Image.fromarray(image).resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS
    )
    
    return np.array(resized), scale
