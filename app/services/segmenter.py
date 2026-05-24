"""Segmentation service using SAM 2."""

from typing import List
import numpy as np

from app.core.config import settings
from app.core.errors import SegmentationError
from app.schemas.mask import Mask
from app.models.sam2_loader import get_sam2_loader
from app.utils.geometry import calculate_bbox


class Segmenter:
    """Segmentation service using SAM 2."""
    
    def __init__(self):
        """Initialize segmenter."""
        self.loader = get_sam2_loader()
        self.model = None
    
    def _ensure_model_loaded(self):
        """Ensure SAM 2 model is loaded."""
        if self.model is None:
            self.model = self.loader.load()
    
    def segment_auto(self, image: np.ndarray) -> List[Mask]:
        """
        Segment image using SAM 2 automatic mask generation.
        
        Args:
            image: RGB image array (H, W, 3)
            
        Returns:
            List of Mask objects
            
        Raises:
            SegmentationError: If segmentation fails
        """
        try:
            self._ensure_model_loaded()
            
            # Get image dimensions
            height, width = image.shape[:2]
            
            # Resize if needed
            max_infer_size = settings.MAX_INFER_SIZE
            scale = 1.0
            if max(height, width) > max_infer_size:
                scale = max_infer_size / max(height, width)
                new_height = int(height * scale)
                new_width = int(width * scale)
                
                from PIL import Image
                img_pil = Image.fromarray(image)
                img_pil = img_pil.resize((new_width, new_width), Image.Resampling.LANCZOS)
                image = np.array(img_pil)
            
            # Run SAM 2 automatic mask generation
            try:
                from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
                mask_generator = SAM2AutomaticMaskGenerator(self.model)
                masks = mask_generator.generate(image)
            except ImportError:
                raise SegmentationError(
                    "SAM 2 automatic mask generator not available. "
                    "Install SAM 2 with: pip install git+https://github.com/facebookresearch/sam2.git"
                )
            
            # Convert to Mask objects
            result_masks = []
            for i, mask_data in enumerate(masks):
                mask_array = mask_data['segmentation']
                
                # Scale back to original size if needed
                if scale < 1.0:
                    from PIL import Image
                    mask_pil = Image.fromarray(mask_array.astype(np.uint8) * 255)
                    mask_pil = mask_pil.resize(
                        (width, height),
                        Image.Resampling.NEAREST
                    )
                    mask_array = np.array(mask_pil) > 127
                
                # Calculate bounding box
                bbox = calculate_bbox(mask_array)
                
                # Get area
                area = int(mask_array.sum())
                
                # Get score
                score = float(mask_data.get('predicted_iou', 0.5))
                
                # Create Mask object
                mask = Mask(
                    mask=mask_array,
                    bbox=bbox,
                    area=area,
                    score=score,
                    label=f"object_{i}",
                )
                
                result_masks.append(mask)
            
            return result_masks
            
        except SegmentationError:
            raise
        except Exception as e:
            raise SegmentationError(f"Segmentation failed: {str(e)}")
    
    def segment_with_prompt(
        self,
        image: np.ndarray,
        prompt: str,
    ) -> List[Mask]:
        """
        Segment image using text prompt with GroundingDINO + SAM 2.
        
        Args:
            image: RGB image array (H, W, 3)
            prompt: Text prompt (e.g., "person . table . book")
            
        Returns:
            List of Mask objects with labels
            
        Raises:
            SegmentationError: If segmentation fails
        """
        try:
            # For now, fall back to auto segmentation
            # TODO: Implement GroundingDINO integration in Issue #23
            return self.segment_auto(image)
            
        except SegmentationError:
            raise
        except Exception as e:
            raise SegmentationError(f"Prompt segmentation failed: {str(e)}")


# Global segmenter instance
_segmenter = None


def get_segmenter() -> Segmenter:
    """Get or create segmenter instance."""
    global _segmenter
    if _segmenter is None:
        _segmenter = Segmenter()
    return _segmenter
