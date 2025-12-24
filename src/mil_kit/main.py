import argparse
import sys
from mil_kit.job import BatchJob
from importlib.metadata import version

def get_version() -> str:
    """Extract version from pyproject.toml in current directory or parent dirs."""
    try:
        return version("mil-kit")
    except Exception:
        return "unknown"


def main():
    parser = argparse.ArgumentParser(
        description="Batch hide text layers in PSDs and export PNGs."
    )
    parser.add_argument(
        "-d",
        "--dir",
        required=True,
        help="Input directory containing PSD files",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output directory (default: input directory)",
    )
    parser.add_argument(
        "-f",
        "--output-format",
        default="png",
        help="Output format (default: png)",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Process subdirectories recursively",
    )
    parser.add_argument(
        "--max-resolution",
        type=int,
        help="Maximum resolution for output images",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=get_version(),
        help="Show program's version number and exit"
    )

    args = parser.parse_args()

    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    try:
        job = BatchJob(
            args.dir,
            args.output,
            args.recursive,
            output_format=args.output_format,
            max_resolution=args.max_resolution,
        )
        job.run()
    except Exception as e:
        print(f"Critical Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
