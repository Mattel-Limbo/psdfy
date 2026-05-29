"""Tests for DINO-only segmentation."""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from app.schemas.mask import Mask


@pytest.fixture
def sample_image():
    """Create a sample RGB image for testing."""
    return np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)


def test_segment_with_prompt_returns_rectangular_masks(sample_image):
    """Test that segment_with_prompt returns rectangular masks from DINO bboxes."""
    from app.services.segmenter import Segmenter
    
    with patch('app.services.segmenter.get_sam2_loader'), \
         patch('app.services.segmenter.get_grounding_dino_loader') as mock_dino_loader_factory:
        
        # Mock DINO loader
        mock_dino_loader = MagicMock()
        mock_dino_model = MagicMock()
        mock_dino_loader.load.return_value = mock_dino_model
        mock_dino_loader_factory.return_value = mock_dino_loader
        
        # Mock DINO predict to return fixed bboxes.
        # GroundingDINO returns [cx, cy, w, h] normalized to [0, 1].
        # First box: cx=0.25, cy=0.25, w=0.3, h=0.3  → xyxy [0.1, 0.1, 0.4, 0.4]
        # Second box: cx=0.7,  cy=0.7,  w=0.4, h=0.4  → xyxy [0.5, 0.5, 0.9, 0.9]
        with patch('app.services.segmenter.predict') as mock_predict:
            boxes = np.array([
                [0.25, 0.25, 0.3, 0.3],  # First object  (cxcywh)
                [0.70, 0.70, 0.4, 0.4],  # Second object (cxcywh)
            ])
            logits = np.array([0.9, 0.8])
            phrases = ["person", "table"]
            
            mock_predict.return_value = (boxes, logits, phrases)
            
            # Create segmenter and run
            segmenter = Segmenter()
            masks = segmenter.segment_with_prompt(sample_image, "person . table")
        
        # Verify results
        assert len(masks) == 2
        
        # Check first mask
        mask1 = masks[0]
        assert isinstance(mask1, Mask)
        assert mask1.label == "person"
        assert mask1.score == 0.9
        assert mask1.mask.dtype == np.bool_
        assert mask1.area > 0
        
        # Check second mask
        mask2 = masks[1]
        assert isinstance(mask2, Mask)
        assert mask2.label == "table"
        assert mask2.score == 0.8
        assert mask2.mask.dtype == np.bool_
        assert mask2.area > 0
        
        # Verify masks are rectangular (all pixels in bbox are True)
        h, w = sample_image.shape[:2]
        x1, y1, x2, y2 = int(0.1 * w), int(0.1 * h), int(0.4 * w), int(0.4 * h)
        
        # Check that the mask region matches the bbox
        mask_region = mask1.mask[y1:y2, x1:x2]
        assert np.all(mask_region)  # All pixels in bbox should be True


def test_segment_with_prompt_no_sam2_call(sample_image):
    """Test that segment_with_prompt does NOT call SAM2."""
    from app.services.segmenter import Segmenter
    
    with patch('app.services.segmenter.get_sam2_loader') as mock_sam2_loader_factory, \
         patch('app.services.segmenter.get_grounding_dino_loader') as mock_dino_loader_factory:
        
        # Mock loaders
        mock_sam2_loader = MagicMock()
        mock_sam2_loader_factory.return_value = mock_sam2_loader
        
        mock_dino_loader = MagicMock()
        mock_dino_model = MagicMock()
        mock_dino_loader.load.return_value = mock_dino_model
        mock_dino_loader_factory.return_value = mock_dino_loader
        
        # Mock DINO predict
        with patch('app.services.segmenter.predict') as mock_predict:
            boxes = np.array([[0.1, 0.1, 0.4, 0.4]])
            logits = np.array([0.9])
            phrases = ["object"]
            
            mock_predict.return_value = (boxes, logits, phrases)
            
            # Create segmenter and run
            segmenter = Segmenter()
            masks = segmenter.segment_with_prompt(sample_image, "object")
        
        # Verify SAM2 loader was NOT called
        mock_sam2_loader.load.assert_not_called()
        
        # Verify DINO loader WAS called
        mock_dino_loader.load.assert_called_once()


def test_segment_with_prompt_bbox_clamping(sample_image):
    """Test that bboxes are properly clamped to image bounds."""
    from app.services.segmenter import Segmenter
    
    with patch('app.services.segmenter.get_sam2_loader'), \
         patch('app.services.segmenter.get_grounding_dino_loader') as mock_dino_loader_factory:
        
        mock_dino_loader = MagicMock()
        mock_dino_model = MagicMock()
        mock_dino_loader.load.return_value = mock_dino_model
        mock_dino_loader_factory.return_value = mock_dino_loader
        
        # Mock DINO predict with bbox that exceeds image bounds
        with patch('app.services.segmenter.predict') as mock_predict:
            boxes = np.array([[-0.1, -0.1, 1.1, 1.1]])  # Exceeds bounds
            logits = np.array([0.9])
            phrases = ["object"]
            
            mock_predict.return_value = (boxes, logits, phrases)
            
            segmenter = Segmenter()
            masks = segmenter.segment_with_prompt(sample_image, "object")
        
        # Verify mask is clamped to image bounds
        mask = masks[0]
        h, w = sample_image.shape[:2]
        
        assert mask.bbox["top"] >= 0
        assert mask.bbox["left"] >= 0
        assert mask.bbox["bottom"] <= h
        assert mask.bbox["right"] <= w


def test_segment_auto_still_uses_sam2(sample_image):
    """Test that segment_auto still uses SAM2 (not affected by DINO changes)."""
    from app.services.segmenter import Segmenter
    
    with patch('app.services.segmenter.get_sam2_loader') as mock_sam2_loader_factory, \
         patch('app.services.segmenter.get_grounding_dino_loader'):
        
        mock_sam2_loader = MagicMock()
        mock_sam2_model = MagicMock()
        mock_sam2_loader.load.return_value = mock_sam2_model
        mock_sam2_loader_factory.return_value = mock_sam2_loader
        
        # Mock SAM2 automatic mask generator
        with patch('app.services.segmenter.SAM2AutomaticMaskGenerator') as mock_mask_gen_class:
            mock_mask_gen = MagicMock()
            mock_mask_gen_class.return_value = mock_mask_gen
            
            # Return mock masks
            mock_mask_gen.generate.return_value = [
                {
                    'segmentation': np.zeros((480, 640), dtype=bool),
                    'predicted_iou': 0.9,
                }
            ]
            
            segmenter = Segmenter()
            masks = segmenter.segment_auto(sample_image)
        
        # Verify SAM2 was used
        mock_sam2_loader.load.assert_called_once()
        mock_mask_gen.generate.assert_called_once()
