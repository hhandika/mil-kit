from mil_kit.psd.processor import PSDProcessor
from pathlib import Path
from PIL import Image
import tempfile

TEST_1_PSD_FILE = "tests/data/simple-1textlayer-with-artboard.psd"
TEST_2_PSD_FILE = (
    "tests/data/simple-2textlayer-with-artboard copy.psd"
)


def test_max_resolution():
    sample_psd_path = Path(TEST_1_PSD_FILE)

    processor = PSDProcessor(sample_psd_path)
    processor.load()
    processor.hide_text_layers()

    max_resolution = 120

    with tempfile.TemporaryDirectory() as tmpdirname:
        output_path = Path(tmpdirname) / "output.png"
        processor.export(
            output_path,
            format="png",
            max_resolution=max_resolution,
        )
        assert output_path.exists()
        assert output_path.suffix.lower() == ".png"

        with Image.open(output_path) as img:
            width, height = img.size
            assert width <= max_resolution
            assert height <= max_resolution
