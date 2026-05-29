"""Tests for mask post-processing."""

import pytest
import numpy as np
from app.services.mask_postprocess import MaskPostprocessor
from app.schemas.mask import Mask


@pytest.fixture
def postprocessor():
    """Create post-processor instance."""
    return MaskPostprocessor()


def create_test_mask(height: int = 256, width: int = 256, area_ratio: float = 0.1) -> Mask:
    """Create a test mask."""
    mask_array = np.zeros((height, width), dtype=np.bool_)
    
    # Create a circular mask
    center_y, center_x = height // 2, width // 2
    radius = int(np.sqrt((height * width * area_ratio) / np.pi))
    
    y, x = np.ogrid[:height, :width]
    circle_mask = (x - center_x) ** 2 + (y - center_y) ** 2 <= radius ** 2
    mask_array[circle_mask] = True
    
    area = int(mask_array.sum())
    
    return Mask(
        mask=mask_array,
        bbox={"top": 0, "left": 0, "bottom": height, "right": width},
        area=area,
        score=0.9,
        label="test_object",
    )


def test_filter_by_area_removes_small_masks(postprocessor):
    """Test that small masks are filtered out."""
    image_shape = (256, 256)
    
    # Create a very small mask (< 0.5% of image)
    small_mask = create_test_mask(area_ratio=0.001)
    
    # Create a normal mask
    normal_mask = create_test_mask(area_ratio=0.1)
    
    masks = [small_mask, normal_mask]
    filtered = postprocessor._filter_by_area(masks, image_shape[0] * image_shape[1])
    
    # Small mask should be removed
    assert len(filtered) == 1
    assert filtered[0].label == "test_object"


def test_filter_by_area_removes_large_masks(postprocessor):
    """Test that masks covering > 95% of image are filtered out."""
    image_shape = (256, 256)
    total_pixels = image_shape[0] * image_shape[1]

    # Create a very large mask (> 95% of image) using a rectangle, not a circle
    # (a circle can only cover ~78.5% of a square at most)
    large_mask_array = np.zeros((256, 256), dtype=np.bool_)
    large_mask_array[:250, :250] = True  # covers ~95.4% of 256x256
    large_mask = Mask(
        mask=large_mask_array,
        bbox={"top": 0, "left": 0, "bottom": 250, "right": 250},
        area=int(large_mask_array.sum()),
        score=0.9,
        label="test_object",
    )

    # Create a normal mask
    normal_mask = create_test_mask(area_ratio=0.1)

    masks = [large_mask, normal_mask]
    filtered = postprocessor._filter_by_area(masks, total_pixels)

    # Large mask should be removed
    assert len(filtered) == 1
    assert filtered[0].label == "test_object"


def test_nms_removes_overlapping_masks(postprocessor):
    """Test that NMS removes overlapping masks."""
    # Create two overlapping masks
    mask1 = create_test_mask(area_ratio=0.1)
    mask1.score = 0.9
    
    mask2 = create_test_mask(area_ratio=0.1)
    mask2.score = 0.5
    
    # Make them overlap significantly
    mask2.mask[:100, :100] = mask1.mask[:100, :100]
    
    masks = [mask1, mask2]
    nms_result = postprocessor._nms(masks)
    
    # Only the higher-scoring mask should remain
    assert len(nms_result) == 1
    assert nms_result[0].score == 0.9


def test_process_returns_valid_masks(postprocessor):
    """Test that process returns valid masks."""
    image_shape = (256, 256)
    
    masks = [
        create_test_mask(area_ratio=0.1),
        create_test_mask(area_ratio=0.15),
    ]
    
    processed = postprocessor.process(masks, image_shape)
    
    # All masks should be valid
    assert len(processed) > 0
    for mask in processed:
        assert mask.area > 0
        assert 0 <= mask.score <= 1
        assert not np.isnan(mask.mask).any()
