import argparse
import sys
from importlib.metadata import version

from mil_kit.psd.batch import BatchJob
from mil_kit.watermark.batch import WatermarkJob


def get_version() -> str:
    try:
        return version("mil-kit")
    except Exception:
        return "unknown"


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-d", "--dir",
        required=True,
        help="Input directory containing image files",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory (default: input directory)",
    )
    parser.add_argument(
        "-f", "--output-format",
        default="png",
        help="Output format (default: png)",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Process subdirectories recursively",
    )
    parser.add_argument(
        "--max-resolution",
        type=int,
        help="Maximum resolution for output images",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of files to process",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        help="Maximum number of parallel workers (default: CPU count)",
    )
    parser.add_argument(
        "--log-file",
        help="Path to log file",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip files that already exist in the output directory",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed progress output",
    )


def get_arg() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch process PSD files and apply watermarks.",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=get_version(),
        help="Show program's version number and exit",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="<command>",
    )

    # --- export subcommand ---
    export_parser = subparsers.add_parser(
        "export",
        help="Batch hide text layers in PSDs and export images",
    )
    add_common_args(export_parser)

    # --- watermark subcommand ---
    watermark_parser = subparsers.add_parser(
        "watermark",
        help="Apply a copyright watermark to a directory of images",
    )
    add_common_args(watermark_parser)

    watermark_source = watermark_parser.add_argument_group(
        "watermark source (at least one required)"
    )
    watermark_source.add_argument(
        "-m", "--meta-file",
        help=(
            "Path to an Excel or CSV metadata file. Image file stems are "
            "matched against MIL# and the watermark text is set to "
            "'Photographer / ASM-MIL' for each matched file."
        ),
    )
    watermark_source.add_argument(
        "-t", "--text",
        help=(
            "Static fallback watermark text used when a file has no "
            "metadata match, or as the sole watermark source when "
            "--meta-file is not provided."
        ),
    )

    watermark_parser.add_argument(
        "--opacity",
        type=float,
        default=0.8,
        help="Watermark opacity between 0.0 and 1.0 (default: 0.8)",
    )

    return parser


def run_export(args: argparse.Namespace) -> None:
    job = BatchJob(
        input_dir=args.dir,
        output_dir=args.output,
        recursive=args.recursive,
        output_format=args.output_format,
        max_workers=args.max_workers,
        max_resolution=args.max_resolution,
        limit=args.limit,
        log_file=args.log_file,
        overwrite=not args.no_overwrite,
        verbose=not args.quiet,
    )
    job.run()


def run_watermark(args: argparse.Namespace) -> None:
    if not args.meta_file and not args.text:
        print(
            "Error: watermark requires --meta-file, --text, or both.",
            file=sys.stderr,
        )
        sys.exit(1)

    job = WatermarkJob(
        input_dir=args.dir,
        meta_file=args.meta_file,
        watermark_text=args.text,
        output_dir=args.output,
        recursive=args.recursive,
        output_format=args.output_format,
        opacity=args.opacity,
        max_workers=args.max_workers,
        max_resolution=args.max_resolution,
        limit=args.limit,
        log_file=args.log_file,
        overwrite=not args.no_overwrite,
        verbose=not args.quiet,
    )
    job.run()


def main() -> None:
    parser = get_arg()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(1)

    handlers = {
        "export": run_export,
        "watermark": run_watermark,
    }

    try:
        handlers[args.command](args)
    except Exception as e:
        print(f"Critical Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
