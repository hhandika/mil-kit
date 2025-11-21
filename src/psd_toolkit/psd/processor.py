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

    def export(self, output_path, format="png"):
        """Composites the PSD and saves as PNG."""
        if not self.psd:
            raise RuntimeError("PSD not loaded.")

        # Ensure the target directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Composite merges layers; save exports using PIL/Pillow
        self.psd.composite().save(output_path, format=format.upper())
