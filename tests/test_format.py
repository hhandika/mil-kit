from psd_toolkit.psd.processor import PSDProcessor
from pathlib import Path
import tempfile

TEST_1_PSD_FILE = "tests/data/simple-1textlayer-with-artboard.psd"
TEST_2_PSD_FILE = (
    "tests/data/simple-2textlayer-with-artboard copy.psd"
)


def test_hide_text_layers():
    sample_psd_path = Path(TEST_1_PSD_FILE)

    processor = PSDProcessor(sample_psd_path)
    processor.load()
    hidden_count = processor.hide_text_layers()

    assert hidden_count == 1


def test_hide_text_layers_multiple():
    sample_psd_path = Path(TEST_2_PSD_FILE)

    processor = PSDProcessor(sample_psd_path)
    processor.load()
    hidden_count = processor.hide_text_layers()

    assert hidden_count == 2


def test_export_png():
    sample_psd_path = Path(TEST_1_PSD_FILE)

    processor = PSDProcessor(sample_psd_path)
    processor.load()
    processor.hide_text_layers()

    with tempfile.TemporaryDirectory() as tmpdirname:
        output_path = Path(tmpdirname) / "output.png"
        processor.export(output_path, format="png")
        assert output_path.exists()
        assert output_path.suffix.lower() == ".png"
