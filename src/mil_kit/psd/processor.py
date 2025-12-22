from PIL import Image
from psd_tools import PSDImage
from pathlib import Path


class PSDProcessor:
    """
    Handles the loading, modification, and exporting of a single PSD file.
    """

    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.psd = None
        self.hidden_count = 0

    def load(self):
        """Loads the PSD file."""
        try:
            self.psd = PSDImage.open(self.file_path)
        except Exception as e:
            raise IOError(f"Failed to open PSD: {e}")

    def hide_text_layers(self):
        """Iterates through all layers and hides those of kind 'type'."""
        if not self.psd:
            raise RuntimeError("PSD not loaded. Call load() first.")

        self.hidden_count = 0
        # descendants() iterates recursively through groups
        for layer in self.psd.descendants():
            if layer.kind == "type" and layer.visible:
                layer.visible = False
                self.hidden_count += 1

        return self.hidden_count

    def hide_non_image_layers(self):
        """
        Hides all non-raster layers including text, vectors, shapes, and adjustments.
        Only keeps pixel/image layers visible.
        """
        if not self.psd:
            raise RuntimeError("PSD not loaded. Call load() first.")

        self.hidden_count = 0
        self.hidden_by_type = {
            "type": 0,  # Text layers
            "shape": 0,  # Vector/shape layers
            "adjustment": 0,  # Adjustment layers
            "other": 0,  # Other non-pixel layers
        }

        # descendants() iterates recursively through groups
        for layer in self.psd.descendants():
            # Only keep pixel/image layers visible
            if layer.visible and layer.kind != "pixel":
                layer.visible = False
                self.hidden_count += 1

                # Track what type was hidden
                if layer.kind in self.hidden_by_type:
                    self.hidden_by_type[layer.kind] += 1
                else:
                    self.hidden_by_type["other"] += 1

        return self.hidden_count

    def export(self, output_path, format="png", max_resolution=None):
        """Composites the PSD and saves as PNG. Optionally resizes to max_resolution.

        Args:
            output_path (str): Path to save the exported image.
            format (str): Image format to save as (e.g., 'png', 'jpeg').
            max_resolution (int, optional): Maximum width/height for the output image.
            If set, the image will be downscaled to fit within this size while preserving aspect ratio.
        Raises:
            RuntimeError: If PSD is not loaded.
        """

        if not self.psd:
            raise RuntimeError("PSD not loaded.")

        # Ensure the target directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        composite = self.psd.composite()
        if max_resolution:
            # In-place downscale with preserved aspect ratio, no upscaling
            composite.thumbnail(
                (max_resolution, max_resolution),
                resample=Image.LANCZOS,  # or Image.BICUBIC
            )

        composite.save(output_path, format=format.upper())
