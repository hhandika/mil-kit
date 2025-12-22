# mil-kit

![Tests](https://github.com/hhandika/mil-kit/actions/workflows/test.yml/badge.svg)
![GitHub Tag](https://img.shields.io/github/v/tag/hhandika/mil-kit?label=GitHub)
![PyPI - Version](https://img.shields.io/pypi/v/mil-kit?color=blue)

A Python toolkit for batch processing the Mammal Image Library (MIL) images. Reshape, convert, and optimize images for the mammal diversity database and other applications.

## Features

- 🚀 Batch process multiple PSD files in a directory
- ⚡ Parallel processing for faster execution
- 📊 Progress bar with detailed status
- 📝 Automatically hide all text layers
- 🖼️ Export processed files as PNG (default) or other formats
- 📁 Support for recursive directory processing
- ⚡ Preserve folder structure in output

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

Process PSD files in a directory:

```bash
mil-kit -d /path/to/psd/files
```

Process recursively, specify output directory, and use JPEG format:

```bash
mil-kit -d /path/to/psd/files -o /path/to/output -r -f jpeg --max-resolution 500
```

### Options

- `-d, --dir`: Input directory containing PSD files (required)
- `-o, --output`: Output directory for processed files (default: input directory)
- `-f, --output-format`: Output image format (default: png)
- `-r, --recursive`: Process subdirectories recursively
- `--max-resolution`: Set maximum resolution for output images (if needed)

### Python API

You can also use mil-kit as a Python library:

```python
from mil_kit.psd.processor import PSDProcessor
from mil_kit.job import BatchJob

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

## Requirements

- Python >= 3.10
- psd-tools >= 1.12.0
- pillow >= 12.0.0
- tqdm >= 4.67.1

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Issues

Report bugs and request features on [GitHub Issues](https://github.com/hhandika/psd-toolkit/issues).
