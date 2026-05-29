"""PSD writer service using pytoshop."""

import io
from collections import OrderedDict
from typing import List, Tuple
import numpy as np

from app.core.errors import PSDWriteError


class PSDWriter:
    """Writes multi-layer PSD files."""

    def write_psd(
        self,
        layers: List[Tuple[np.ndarray, str, dict]],
        canvas_width: int,
        canvas_height: int,
    ) -> bytes:
        """
        Write a multi-layer PSD file.

        Args:
            layers: List of (rgba_array, layer_name, bbox) tuples
            canvas_width: Canvas width
            canvas_height: Canvas height

        Returns:
            PSD file bytes

        Raises:
            PSDWriteError: If PSD writing fails
        """
        try:
            try:
                import pytoshop
                from pytoshop import layers as psd_layers, enums
            except ImportError:
                raise PSDWriteError(
                    "pytoshop not installed. Install with: pip install pytoshop"
                )

            layer_records = []

            for rgba, layer_name, bbox in layers:
                # Ensure uint8 RGBA
                if rgba.dtype != np.uint8:
                    rgba = (rgba * 255).clip(0, 255).astype(np.uint8)
                if rgba.ndim == 2 or rgba.shape[2] == 1:
                    rgba = np.dstack([rgba[:, :, 0]] * 3 + [np.full(rgba.shape[:2], 255, dtype=np.uint8)])
                elif rgba.shape[2] == 3:
                    rgba = np.dstack([rgba, np.full(rgba.shape[:2], 255, dtype=np.uint8)])

                top = int(bbox.get("top", 0))
                left = int(bbox.get("left", 0))
                bottom = int(bbox.get("bottom", rgba.shape[0]))
                right = int(bbox.get("right", rgba.shape[1]))

                # Clamp to canvas bounds
                top = max(0, min(top, canvas_height))
                left = max(0, min(left, canvas_width))
                bottom = max(top, min(bottom, canvas_height))
                right = max(left, min(right, canvas_width))

                # pytoshop requires channel data sized to the layer bbox,
                # not the full canvas.
                cropped = rgba[top:bottom, left:right, :]

                channels = OrderedDict([
                    (-1, psd_layers.ChannelImageData(image=cropped[:, :, 3])),  # alpha
                    (0,  psd_layers.ChannelImageData(image=cropped[:, :, 0])),  # R
                    (1,  psd_layers.ChannelImageData(image=cropped[:, :, 1])),  # G
                    (2,  psd_layers.ChannelImageData(image=cropped[:, :, 2])),  # B
                ])

                record = psd_layers.LayerRecord(
                    top=top,
                    left=left,
                    bottom=bottom,
                    right=right,
                    name=layer_name,
                    channels=channels,
                    blend_mode=enums.BlendMode.normal,
                    opacity=255,
                )
                layer_records.append(record)

            layer_info = psd_layers.LayerInfo(layer_records=layer_records)
            layer_and_mask_info = psd_layers.LayerAndMaskInfo(layer_info=layer_info)

            psd = pytoshop.PsdFile(
                num_channels=3,
                height=canvas_height,
                width=canvas_width,
                color_mode=enums.ColorMode.rgb,
            )
            psd.layer_and_mask_info = layer_and_mask_info

            output = io.BytesIO()
            psd.write(output)
            return output.getvalue()

        except PSDWriteError:
            raise
        except Exception as e:
            raise PSDWriteError(f"Failed to write PSD: {str(e)}")

    def write_simple_psd(
        self,
        image: np.ndarray,
        layer_name: str = "image",
    ) -> bytes:
        """
        Write a simple single-layer PSD.

        Args:
            image: RGB image array (H, W, 3)
            layer_name: Name for the layer

        Returns:
            PSD file bytes

        Raises:
            PSDWriteError: If PSD writing fails
        """
        height, width = image.shape[:2]

        if image.shape[2] == 3:
            rgba = np.dstack([image, np.full((height, width), 255, dtype=np.uint8)])
        else:
            rgba = image

        layers = [(rgba, layer_name, {
            "top": 0,
            "left": 0,
            "bottom": height,
            "right": width,
        })]

        return self.write_psd(layers, width, height)


def get_psd_writer() -> PSDWriter:
    """Get PSD writer instance."""
    return PSDWriter()
