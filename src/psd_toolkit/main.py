import argparse
import sys
from pathlib import Path
from psd_toolkit.psd.processor import PSDProcessor
from tqdm import tqdm


class BatchJob:
    """
    Manages the processing of a directory of files.
    """

    def __init__(
        self,
        input_dir,
        output_dir=None,
        recursive=False,
        output_format="png",
    ):
        self.input_dir = Path(input_dir)
        self.recursive = recursive
        self.output_format = output_format.lower()

        # If no output dir is specified, use input dir
        self.output_dir = (
            Path(output_dir) if output_dir else self.input_dir
        )

        self.stats = {"success": 0, "failed": 0, "skipped": 0}

    def run(self):
        """Executes the batch processing."""
        files = list(self._get_files())
        total_files = len(files)

        if total_files == 0:
            print(f"No PSD files found in {self.input_dir}")
            return

        print(
            f"Found {total_files} PSD file(s). Starting process...\n"
        )

        # Wrap the iterable with tqdm
        for psd_path in tqdm(
            files, desc="Processing PSD files", unit="file"
        ):
            try:
                processor = PSDProcessor(psd_path)
                processor.load()

                count = processor.hide_text_layers()

                dest_path = self._generate_output_path(psd_path)
                processor.export(dest_path, format=self.output_format)

                # Use tqdm.write() instead of print() to avoid breaking the progress bar
                tqdm.write(
                    f"✓ {psd_path.name}: Hidden {count} layers"
                )
                self.stats["success"] += 1

            except Exception as e:
                tqdm.write(f"✗ {psd_path.name}: Failed - {e}")
                self.stats["failed"] += 1

        self._print_summary(total_files)

    def _get_files(self):
        """Generator that yields PSD files based on recursion setting."""
        if not self.input_dir.exists():
            raise FileNotFoundError(
                f"Input directory not found: {self.input_dir}"
            )

        pattern = "*.psd"
        return (
            self.input_dir.rglob(pattern)
            if self.recursive
            else self.input_dir.glob(pattern)
        )

    def _generate_output_path(self, psd_path):
        """Determines the destination path, preserving folder structure if recursive."""
        if self.recursive and self.output_dir != self.input_dir:
            # Create mirror structure: output/subfolder/file.png
            rel_path = psd_path.relative_to(self.input_dir)
            return self.output_dir / rel_path.with_suffix(
                f".{self.output_format}"
            )
        else:
            # Flat structure or same folder
            return (
                self.output_dir
                / f"{psd_path.stem}.{self.output_format}"
            )

    def _print_summary(self, total):
        print(f"\n{'=' * 40}")
        print("Processing Complete")
        print(f"Total Files: {total}")
        print(f"Successful:  {self.stats['success']}")
        print(f"Failed:      {self.stats['failed']}")
        print(f"{'=' * 40}")


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

    args = parser.parse_args()

    try:
        job = BatchJob(args.dir, args.output, args.recursive)
        job.run()
    except Exception as e:
        print(f"Critical Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
