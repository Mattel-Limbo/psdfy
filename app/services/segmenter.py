"""Segmentation service using SAM 2."""

from typing import List
import numpy as np

from app.core.config import settings
from app.core.errors import SegmentationError
from app.schemas.mask import Mask
from app.models.sam2_loader import get_sam2_loader
from app.models.dino_loader import get_grounding_dino_loader
from app.utils.geometry import calculate_bbox

try:
    from groundingdino.util.inference import predict
except ImportError:
    predict = None  # type: ignore[assignment]

try:
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
except ImportError:
    SAM2AutomaticMaskGenerator = None  # type: ignore[assignment,misc]


class Segmenter:
    """Segmentation service using SAM 2 and GroundingDINO."""
    
    def __init__(self):
        """Initialize segmenter."""
        self.sam2_loader = get_sam2_loader()
        self.dino_loader = get_grounding_dino_loader()
        self.sam2_model = None
    
    def _ensure_sam2_loaded(self):
        """Ensure SAM 2 model is loaded."""
        if self.sam2_model is None:
            self.sam2_model = self.sam2_loader.load()
    
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
            self._ensure_sam2_loaded()
            
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
                img_pil = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
                image = np.array(img_pil)
            
            # Run SAM 2 automatic mask generation
            if SAM2AutomaticMaskGenerator is None:
                raise SegmentationError(
                    "SAM 2 automatic mask generator not available. "
                    "Install SAM 2 with: pip install git+https://github.com/facebookresearch/sam2.git"
                )
            mask_generator = SAM2AutomaticMaskGenerator(
                model=self.sam2_model,
                points_per_side=settings.SAM2_POINTS_PER_SIDE,
                pred_iou_thresh=settings.SAM2_PRED_IOU_THRESH,
                stability_score_thresh=settings.SAM2_STABILITY_SCORE_THRESH,
                min_mask_region_area=settings.SAM2_MIN_MASK_REGION_AREA,
            )
            masks = mask_generator.generate(image)
            
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
        Segment image using text prompt with GroundingDINO.
        
        Args:
            image: RGB image array (H, W, 3)
            prompt: Text prompt (e.g., "person . table . book")
            
        Returns:
            List of Mask objects with labels (rectangular masks from bboxes)
            
        Raises:
            SegmentationError: If segmentation fails
        """
        try:
            # Load GroundingDINO
            dino_model = self.dino_loader.load()
            
            # Get image dimensions
            height, width = image.shape[:2]
            
            # Prepare image for DINO
            # DINO expects RGB image as numpy array
            if image.dtype != np.uint8:
                image_uint8 = (image * 255).astype(np.uint8)
            else:
                image_uint8 = image
            
            # Run GroundingDINO
            if predict is None:
                raise SegmentationError(
                    "GroundingDINO inference not available. "
                    "Install with: pip install git+https://github.com/IDEA-Research/GroundingDINO.git"
                )

            import torch
            from torchvision import transforms as T

            # GroundingDINO expects a normalized float tensor (3, H, W)
            transform = T.Compose([
                T.ToPILImage(),
                T.Resize((800, 800)),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
            image_tensor = transform(image_uint8)

            # Predict bboxes and labels
            boxes, logits, phrases = predict(
                model=dino_model,
                image=image_tensor,
                caption=prompt,
                box_threshold=0.3,
                text_threshold=0.25,
                device="cpu",
            )
            
            # Convert bboxes to rectangular masks
            # boxes and logits are torch tensors — convert to numpy
            boxes_np = boxes.cpu().numpy() if hasattr(boxes, 'cpu') else boxes
            logits_np = logits.cpu().numpy() if hasattr(logits, 'cpu') else logits
            
            result_masks = []
            
            for idx, (box, logit, phrase) in enumerate(zip(boxes_np, logits_np, phrases)):
                # box format from DINO: [cx, cy, w, h] normalized to [0, 1]
                cx, cy, w, h = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                
                # Convert cxcywh -> xyxy
                x1 = cx - w / 2
                y1 = cy - h / 2
                x2 = cx + w / 2
                y2 = cy + h / 2
                
                # Convert to pixel coordinates
                px1 = int(x1 * width)
                py1 = int(y1 * height)
                px2 = int(x2 * width)
                py2 = int(y2 * height)
                
                # Clamp to image bounds
                px1 = max(0, min(px1, width - 1))
                py1 = max(0, min(py1, height - 1))
                px2 = max(px1 + 1, min(px2, width))
                py2 = max(py1 + 1, min(py2, height))
                
                # Create rectangular mask
                mask_array = np.zeros((height, width), dtype=np.bool_)
                mask_array[py1:py2, px1:px2] = True
                
                # Calculate area
                area = int(mask_array.sum())
                
                # Create bbox dict
                bbox = {
                    "top": py1,
                    "left": px1,
                    "bottom": py2,
                    "right": px2,
                }
                
                # Create Mask object
                mask = Mask(
                    mask=mask_array,
                    bbox=bbox,
                    area=area,
                    score=float(logit),
                    label=phrase,
                )
                
                result_masks.append(mask)
            
            return result_masks
            
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
