"""Tests for layer builder."""

import pytest
import numpy as np
from app.services.layer_builder import LayerBuilder
from app.schemas.mask import Mask


@pytest.fixture
def layer_builder():
    """Create layer builder instance."""
    return LayerBuilder()


def create_test_image(height: int = 256, width: int = 256) -> np.ndarray:
    """Create a test RGB image."""
    return np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)


def create_test_mask(height: int = 256, width: int = 256) -> Mask:
    """Create a test mask."""
    mask_array = np.zeros((height, width), dtype=np.bool_)
    mask_array[50:150, 50:150] = True
    
    return Mask(
        mask=mask_array,
        bbox={"top": 50, "left": 50, "bottom": 150, "right": 150},
        area=10000,
        score=0.9,
        label="test_object",
    )


def test_build_layers_creates_rgba_layers(layer_builder):
    """Test that build_layers creates RGBA layers."""
    image = create_test_image()
    masks = [create_test_mask()]
    
    layers = layer_builder.build_layers(image, masks)
    
    assert len(layers) == 1
    rgba, name, bbox = layers[0]
    
    # Check RGBA format
    assert rgba.shape == (256, 256, 4)
    assert rgba.dtype == np.uint8
    
    # Check that alpha channel is set correctly
    assert np.all(rgba[50:150, 50:150, 3] == 255)  # Inside mask
    assert np.all(rgba[0:50, 0:50, 3] == 0)  # Outside mask


def test_build_background_creates_background_layer(layer_builder):
    """Test that build_background creates background layer."""
    image = create_test_image()
    masks = [create_test_mask()]
    
    rgba, name, bbox = layer_builder.build_background(image, masks)
    
    # Check format
    assert rgba.shape == (256, 256, 4)
    assert name == "background"
    
    # Check that alpha is inverted (opaque outside mask, transparent inside)
    assert np.all(rgba[50:150, 50:150, 3] == 0)  # Inside mask (transparent)
    assert np.all(rgba[0:50, 0:50, 3] == 255)  # Outside mask (opaque)


def test_build_layers_with_multiple_masks(layer_builder):
    """Test building layers with multiple masks."""
    image = create_test_image()
    
    # Create multiple masks
    mask1 = create_test_mask()
    mask1.label = "object_1"
    
    mask2 = create_test_mask()
    mask2.mask[100:200, 100:200] = True
    mask2.label = "object_2"
    
    masks = [mask1, mask2]
    
    layers = layer_builder.build_layers(image, masks)
    
    assert len(layers) == 2
    assert layers[0][1] == "object_1"
    assert layers[1][1] == "object_2"
