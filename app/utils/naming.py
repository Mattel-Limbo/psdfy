"""Naming utilities for layers."""

import re
from typing import Optional


def sanitize_layer_name(name: str, max_length: int = 255) -> str:
    """
    Sanitize layer name for PSD compatibility.
    
    Args:
        name: Original layer name
        max_length: Maximum name length
        
    Returns:
        Sanitized layer name
    """
    # Remove control characters
    name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)
    
    # Replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    
    # Truncate to max length
    if len(name) > max_length:
        name = name[:max_length]
    
    # Ensure not empty
    if not name or name.isspace():
        name = "layer"
    
    return name.strip()


def generate_object_name(index: int, label: Optional[str] = None) -> str:
    """
    Generate a layer name for an object.
    
    Args:
        index: Object index
        label: Optional label from detection model
        
    Returns:
        Layer name
    """
    if label:
        return sanitize_layer_name(label)
    return f"object_{index}"
