"""
Batch Processing Module for PSD Files
Manages parallel processing of PSD files with enhanced error handling and logging.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Generator, Optional, Tuple, List
from datetime import datetime
import logging
from tqdm import tqdm
from mil_kit.psd.processor import PSDProcessor
import os
import shutil


class BatchJob:
    """
    Manages the processing of a directory of files with parallel execution.

    Features:
    - Parallel processing using ThreadPoolExecutor
    - Progress tracking with tqdm
    - Detailed logging and error handling
    - Flexible output options
    - Processing statistics and reporting
    """

    SUPPORTED_FORMATS = ["png", "jpg", "jpeg", "tiff", "bmp", "webp"]

    def __init__(
        self,
        input_dir: str,
        output_dir: Optional[str] = None,
        recursive: bool = False,
        output_format: str = "png",
        max_workers: Optional[int] = None,
        max_resolution: Optional[int] = None,
        limit: Optional[int] = None,
        log_file: Optional[str] = None,
        overwrite: bool = True,
        verbose: bool = True,
    ):
        """
        Initialize the BatchJob processor.

        Args:
            input_dir: Directory containing PSD files
            output_dir: Output directory (defaults to input_dir)
            recursive: Search subdirectories recursively
            output_format: Output image format (png, jpg, etc.)
            max_workers: Max parallel workers (None = CPU count)
            log_file: Path to log file (None = no file logging)
            overwrite: Overwrite existing output files
            verbose: Print detailed progress messages
        """
        self.input_dir = Path(input_dir)
        self.recursive = recursive
        self.output_format = output_format.lower()
        self.max_workers = max_workers
        self.max_resolution = max_resolution
        self.limit = limit
        self.overwrite = overwrite
        self.verbose = verbose

        # Validate input directory
        if not self.input_dir.exists():
            raise FileNotFoundError(
                f"Input directory not found: {self.input_dir}"
            )

        if not self.input_dir.is_dir():
            raise NotADirectoryError(
                f"Input path is not a directory: {self.input_dir}"
            )

        # Validate output format
        if self.output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {self.output_format}. "
                f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        # Set up output directory
        self.output_dir = (
            Path(output_dir) if output_dir else self.input_dir
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize statistics
        self.stats = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "total_layers_hidden": 0,
            "start_time": None,
            "end_time": None,
        }

        self.failed_files = []  # Track failed files for reporting

        # Set up logging
        self._setup_logging(log_file)

    def _setup_logging(self, log_file: Optional[str]):
        """Configure logging for the batch job."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(
            logging.DEBUG if self.verbose else logging.INFO
        )

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter("%(message)s")
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        # File handler (if specified)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, mode="a")
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
    
    def _print_settings(self):
        """Print the current settings of the batch job."""
        self.logger.info("Batch Job Settings:")
        self.logger.info(f"Input Directory: {self.input_dir}")
        self.logger.info(f"Output Directory: {self.output_dir}")
        self.logger.info(f"Recursive: {self.recursive}")
        self.logger.info(f"Output Format: {self.output_format}")
        self.logger.info(
            f"Max Workers: {self.max_workers or 'Auto (CPU count)'}"
        )
        self.logger.info(f"Max Resolution: {self.max_resolution or 'No limit'}")
        self.logger.info(f"Limit: {self.limit or 'No limit'}")
        self.logger.info(f"Overwrite Existing: {self.overwrite}")
        self.logger.info(f"Verbose Output: {self.verbose}")
        self.logger.info("")

    def run(self):
        """
        Execute the batch processing with parallel execution.

        Returns:
            Dictionary containing processing statistics
        """
        self.stats["start_time"] = datetime.now()
        self._print_settings()

        files = list(self._get_files())
        if self.limit is not None and len(files) > self.limit:
            files = files[:self.limit]
        total_files = len(files)

        if total_files == 0:
            message = f"No PSD files found in {self.input_dir}"
            if self.recursive:
                message += " (including subdirectories)"
            self.logger.warning(message)
            return self.stats

        self.logger.info(
            f"Found {total_files} PSD file(s) in {self.input_dir}"
        )

        if total_files == 1:
            # Single file - no need for parallelism
            self._process_single_file_wrapper(files[0])
        else:
            # Multiple files - use parallel processing
            self._process_multiple_files(files, total_files)

        self.stats["end_time"] = datetime.now()
        self._print_summary(total_files)
        if self.failed_files:
            self._copy_failed_file()

    def _process_multiple_files(
        self, files: List[Path], total_files: int
    ):
        """Process multiple files in parallel."""
        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    self._process_single_file, psd_path
                ): psd_path
                for psd_path in files
            }

            with tqdm(
                total=total_files,
                desc="Processing PSD files",
                unit="file",
                disable=not self.verbose,
            ) as pbar:
                for future in as_completed(futures):
                    psd_path = futures[future]

                    try:
                        success, message, count = future.result()
                        self._update_stats(
                            success,
                            count,
                            psd_path if not success else None,
                        )

                        if self.verbose:
                            tqdm.write(message)

                    except Exception as e:
                        self._update_stats(False, 0, psd_path)
                        error_msg = f"✗ {psd_path.name}: Unexpected error - {e}"
                        if self.verbose:
                            tqdm.write(error_msg)
                        self.logger.error(error_msg)

                    pbar.update(1)

    def _process_single_file_wrapper(self, psd_path: Path):
        """Wrapper for processing a single file (non-parallel)."""
        try:
            success, message, count = self._process_single_file(
                psd_path
            )
            self._update_stats(
                success, count, psd_path if not success else None
            )
            self.logger.info(message)
        except Exception as e:
            self._update_stats(False, 0, psd_path)
            error_msg = f"✗ {psd_path.name}: Unexpected error - {e}"
            self.logger.error(error_msg)

    def _process_single_file(
        self, psd_path: Path
    ) -> Tuple[bool, str, int]:
        """
        Process a single PSD file.

        Returns:
            Tuple of (success: bool, message: str, layers_hidden: int)
        """
        try:
            dest_path = self._generate_output_path(psd_path)

            # Check if output exists and overwrite is disabled
            if dest_path.exists() and not self.overwrite:
                return (
                    False,
                    f"⊘ {psd_path.name}: Skipped (output exists, overwrite=False)",
                    0,
                )

            # Load and process PSD
            processor = PSDProcessor(psd_path)
            processor.load()

            # Hide text layers
            count = processor.hide_non_image_layers()

            # Export to specified format
            processor.export(dest_path, format=self.output_format, 
                             max_resolution=self.max_resolution)

            return (
                True,
                f"✓ {psd_path.name}: Hidden {count} text layer(s) → {dest_path.name}",
                count,
            )

        except FileNotFoundError as e:
            return (
                False,
                f"✗ {psd_path.name}: File not found - {e}",
                0,
            )

        except PermissionError as e:
            return (
                False,
                f"✗ {psd_path.name}: Permission denied - {e}",
                0,
            )

        except Exception as e:
            return (
                False,
                f"✗ {psd_path.name}: Processing failed - {e}",
                0,
            )

    def _update_stats(
        self,
        success: bool,
        layers_hidden: int,
        failed_path: Optional[Path] = None,
    ):
        """Update processing statistics."""
        if success:
            self.stats["success"] += 1
            self.stats["total_layers_hidden"] += layers_hidden
        else:
            self.stats["failed"] += 1
            if failed_path:
                self.failed_files.append(failed_path)

    def _get_files(self) -> Generator[Path, None, None]:
        """Generator that yields PSD files."""
        pattern = "**/*.psd" if self.recursive else "*.psd"
        for path in self.input_dir.glob(pattern):
            if path.is_file():
                yield path

    def _generate_output_path(self, psd_path: Path) -> Path:
        """Generate the output file path, preserving directory structure if recursive."""
        if self.recursive and self.output_dir != self.input_dir:
            # Preserve subdirectory structure
            relative_path = psd_path.relative_to(self.input_dir)
            output_subdir = self.output_dir / relative_path.parent
            output_subdir.mkdir(parents=True, exist_ok=True)
            return (
                output_subdir
                / f"{psd_path.stem}.{self.output_format}"
            )
        else:
            return (
                self.output_dir
                / f"{psd_path.stem}.{self.output_format}"
            )

    def _copy_failed_file(self):
        """Copy failed file to output directory for review (if needed)."""
        failed_dir = os.path.join(self.output_dir, "failed_files")
        os.makedirs(failed_dir, exist_ok=True)
        self.logger.info(
            f"Copying failed files to {failed_dir} for review."
        )
        for file in self.failed_files:
            shutil.copy(file, failed_dir)

    def _print_summary(self, total_files: int):
        """Print detailed processing summary."""
        duration = self.stats["end_time"] - self.stats["start_time"]

        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Total files:          {total_files}")
        print(f"✓ Successful:         {self.stats['success']}")
        print(f"✗ Failed:             {self.stats['failed']}")
        print(f"⊘ Skipped:            {self.stats['skipped']}")
        print(
            f"Text layers hidden:   {self.stats['total_layers_hidden']}"
        )
        print(f"Processing time:      {duration}")
        print(f"Output directory:     {self.output_dir}")
        print("=" * 60)

        # Log failed files if any
        if self.failed_files:
            print("\nFailed files:")
            for failed_file in self.failed_files:
                print(f"  - {failed_file}")

        # Log to file
        self.logger.info(
            f"Batch job completed: {self.stats['success']}/{total_files} successful"
        )
