# mil-kit

![Tests](https://github.com/hhandika/mil-kit/actions/workflows/test.yml/badge.svg)
![GitHub Tag](https://img.shields.io/github/v/tag/hhandika/mil-kit?label=GitHub)
![PyPI - Version](https://img.shields.io/pypi/v/mil-kit?color=blue)

A Python toolkit for batch processing images, with a focus on PSD to image conversion and robust watermarking capabilities.

## Features

- **Two main commands**: `export` and `watermark`.
- 🚀 Batch process multiple files in a directory.
- ⚡ Parallel processing for faster execution.
- 📊 Progress bar with detailed status.
- 📁 Support for recursive directory processing.
- ⚡ Preserve folder structure in output.
- 📝 **`export`**: Automatically hide all text layers in PSD files.
- 🖼️ **`export`**: Export processed files as PNG (default) or other formats.
- 💧 **`watermark`**: Apply copyright watermarks to images.
- 📖 **`watermark`**: Metadata-driven watermarks from Excel/CSV files.
- fallback **`watermark`**: Use static text when no metadata match is found.
- 🎨 **`watermark`**: Customize watermark opacity.

## Installation

Install using pip:

```bash
pip install mil-kit
```

Or using uv:

```bash
uv add mil-kit
```

## Usage

### Command Line

`mil-kit` provides two main commands: `export` and `watermark`.

#### `export`

Batch hide text layers in PSDs and export them as images.

```bash
mil-kit export -d /path/to/psd/files
```

Process recursively, specify an output directory, and use JPEG format:

```bash
mil-kit export -d /path/to/psd/files -o /path/to/output -r -f jpeg --max-resolution 500
```

#### `watermark`

Apply a copyright watermark to a directory of images.

Apply a static watermark to all images:

```bash
mil-kit watermark -d /path/to/images -t "© 2024 Your Name"
```

Use a metadata file to apply dynamic watermarks. The file stem (e.g., `123` from `123.jpg`) is matched against the `MIL#` column in the metadata file.

```bash
mil-kit watermark -d /path/to/images --meta-file /path/to/metadata.csv
```

Use a metadata file with a fallback watermark for images with no match:

```bash
mil-kit watermark -d /path/to/images --meta-file /path/to/metadata.csv -t "Default Watermark" --opacity 0.5
```

### Options

#### Common Options (for `export` and `watermark`)

- `-d, --dir`: Input directory containing image files (required).
- `-o, --output`: Output directory for processed files (default: input directory).
- `-f, --output-format`: Output image format (default: png).
- `-r, --recursive`: Process subdirectories recursively.
- `--max-resolution`: Set maximum resolution for output images.
- `--limit`: Limit the number of files to process.
- `--max-workers`: Maximum number of parallel workers (default: CPU count).
- `--log-file`: Path to a log file.
- `--no-overwrite`: Skip files that already exist in the output directory.
- `--quiet`: Suppress detailed progress output.

#### `watermark` Specific Options

- `-m, --meta-file`: Path to an Excel or CSV metadata file.
- `-t, --text`: Static fallback watermark text.
- `--opacity`: Watermark opacity between 0.0 and 1.0 (default: 0.8).

### Python API

You can also use `mil-kit` as a Python library.

#### `PSDProcessor`

```python
from mil_kit.psd.processor import PSDProcessor
from mil_kit.psd.batch import BatchJob

# Process a single file
processor = PSDProcessor("image.psd")
processor.load()
processor.hide_non_image_layers()
processor.export("output.jpg", format="jpeg")

# If you want to export with max resolution
processor.export("output_resized.jpg", format="jpeg", max_resolution=500)

# Batch process
job = BatchJob(
    input_dir="./psd_files",
    output_dir="./output",
    recursive=True,
    output_format="png",
    max_workers=4
)
job.run()
```

#### `WatermarkProcessor`

```python
from mil_kit.watermark.add import WatermarkProcessor
from mil_kit.watermark.batch import WatermarkJob

# Process a single file
processor = WatermarkProcessor("photo.png", watermark_text="2024 Studio Name", opacity=0.8)
processor.load()
processor.apply_text_watermark()
processor.export("output/photo.png", format="png", max_resolution=1920)

# Batch process
job = WatermarkJob(
    input_dir="images",
    meta_file="metadata.csv",
    watermark_text="Default Watermark",
    output_dir="watermarked_output",
)
job.run()
```

## Requirements

- Python >= 3.10
- fastexcel >= 0.19.0
- pillow >= 12.0.0
- polars >= 1.38.1
- psd-tools >= 1.12.0
- tqdm >= 4.67.1

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Issues

Report bugs and request features on [GitHub Issues](https://github.com/hhandika/mil-kit/issues).
