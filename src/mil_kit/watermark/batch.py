"""
Batch Processing Module for Image Watermarking.
Manages parallel watermarking of images with enhanced error handling and logging.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Generator, Optional, Tuple, List
from datetime import datetime
import logging
import shutil

from tqdm import tqdm
from mil_kit.watermark.add import WatermarkProcessor
from mil_kit.watermark.meta import MetadataParser


class WatermarkJob:
    """
    Manages the batch watermarking of images in a directory with parallel execution.

    Watermark text is resolved per file in the following order of precedence:

    1. Metadata file lookup — if ``meta_file`` is provided, the file stem is
       matched against the parsed MIL number index and the corresponding
       ``"{Photographer} / ASM-MIL"`` string is used.
    2. Fallback text — if no metadata match is found and ``watermark_text``
       is provided, that static string is used for every unmatched file.
    3. No metadata — if neither source yields a watermark string, the file is
       copied to ``output_dir/no_metadata/`` for review and counted separately
       in the summary.

    At least one of ``meta_file`` or ``watermark_text`` must be supplied.

    Features:
    - Metadata-driven per-file watermark text via ``MetadataParser``
    - Unmatched files copied to a ``no_metadata/`` directory for review
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
        meta_file: Optional[str] = None,
        watermark_text: Optional[str] = None,
        output_dir: Optional[str] = None,
        recursive: bool = False,
        output_format: str = "png",
        opacity: float = 0.8,
        max_workers: Optional[int] = None,
        max_resolution: Optional[int] = None,
        limit: Optional[int] = None,
        log_file: Optional[str] = None,
        overwrite: bool = True,
        verbose: bool = True,
    ) -> None:
        """
        Initialise the WatermarkJob processor.

        Args:
            input_dir (str): Directory containing source images.
            meta_file (str | None): Path to an Excel or CSV metadata file
                parsed by ``MetadataParser``. MIL numbers in the file are
                matched against image file stems to resolve per-file watermark
                text. Optional if ``watermark_text`` is provided.
            watermark_text (str | None): Static fallback watermark text used
                when a file stem has no match in the metadata, or as the sole
                watermark source when ``meta_file`` is not supplied.
            output_dir (str | None): Output directory. Defaults to ``input_dir``.
            recursive (bool): Search subdirectories recursively. Defaults to False.
            output_format (str): Output image format (e.g. ``"png"``). Defaults to ``"png"``.
            opacity (float): Watermark opacity between 0.0 and 1.0. Defaults to 0.8.
            max_workers (int | None): Maximum parallel workers. None uses CPU count.
            max_resolution (int | None): Maximum output image dimension in pixels.
            limit (int | None): Maximum number of files to process.
            log_file (str | None): Path to a log file. None disables file logging.
            overwrite (bool): Overwrite existing output files. Defaults to True.
            verbose (bool): Print detailed progress messages. Defaults to True.

        Raises:
            ValueError: If neither ``meta_file`` nor ``watermark_text`` is provided,
                ``output_format`` is unsupported, or ``opacity`` is out of range.
            FileNotFoundError: If ``input_dir`` does not exist.
            NotADirectoryError: If ``input_dir`` is not a directory.
            IOError: If the metadata file cannot be read or parsed.
        """
        if not meta_file and not watermark_text:
            raise ValueError("Either meta_file or watermark_text must be provided.")
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0.")

        self.input_dir = Path(input_dir)
        self.watermark_text = watermark_text
        self.recursive = recursive
        self.output_format = output_format.lower()
        self.opacity = opacity
        self.max_workers = max_workers
        self.max_resolution = max_resolution
        self.limit = limit
        self.overwrite = overwrite
        self.verbose = verbose

        if not self.input_dir.exists():
            raise FileNotFoundError(
                f"Input directory not found: {self.input_dir}"
            )
        if not self.input_dir.is_dir():
            raise NotADirectoryError(
                f"Input path is not a directory: {self.input_dir}"
            )
        if self.output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {self.output_format}. "
                f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        self.output_dir = Path(output_dir) if output_dir else self.input_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.metadata: Optional[MetadataParser] = None
        if meta_file:
            self.metadata = MetadataParser(meta_file)
            self.metadata.parse()

        self.stats = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "no_metadata": 0,
            "start_time": None,
            "end_time": None,
        }
        self.failed_files: List[Path] = []
        self.no_metadata_files: List[Path] = []

        self._setup_logging(log_file)

    def _setup_logging(self, log_file: Optional[str]) -> None:
        """
        Configure console and optional file logging for the batch job.

        The console handler emits INFO-level messages using a minimal format.
        The file handler, when enabled, emits DEBUG-level messages with full
        timestamps for post-run analysis.

        Args:
            log_file (str | None): Destination log file path. Passing ``None``
                skips file handler setup entirely.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        self.logger.handlers.clear()

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(console_handler)

        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, mode="a")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self.logger.addHandler(file_handler)

    def _print_settings(self) -> None:
        """Log the active configuration before processing begins."""
        self.logger.info("Watermark Job Settings:")
        self.logger.info(f"  Input Directory:  {self.input_dir}")
        self.logger.info(f"  Output Directory: {self.output_dir}")
        self.logger.info(f"  Metadata File:    {self.metadata.file_path if self.metadata else 'None'}")
        self.logger.info(f"  Fallback Text:    {self.watermark_text or 'None'}")
        self.logger.info(f"  Opacity:          {self.opacity}")
        self.logger.info(f"  Recursive:        {self.recursive}")
        self.logger.info(f"  Output Format:    {self.output_format}")
        self.logger.info(f"  Max Workers:      {self.max_workers or 'Auto (CPU count)'}")
        self.logger.info(f"  Max Resolution:   {self.max_resolution or 'No limit'}")
        self.logger.info(f"  Limit:            {self.limit or 'No limit'}")
        self.logger.info(f"  Overwrite:        {self.overwrite}")
        self.logger.info(f"  Verbose:          {self.verbose}")
        self.logger.info("")

    def run(self) -> dict:
        """
        Execute the batch watermarking job with parallel processing.

        Discovers all supported image files in ``input_dir``, resolves the
        watermark text for each via metadata or fallback, and writes results
        to ``output_dir``. Files with no metadata match and no fallback text
        are copied to ``output_dir/no_metadata/`` for manual review. A single
        file skips the thread pool to avoid unnecessary overhead.

        Returns:
            dict: Processing statistics with keys ``success``, ``failed``,
                ``skipped``, ``no_metadata``, ``start_time``, and ``end_time``.
        """
        self.stats["start_time"] = datetime.now()
        self._print_settings()

        files = list(self._get_files())
        if self.limit is not None:
            files = files[: self.limit]

        total_files = len(files)

        if total_files == 0:
            message = f"No supported image files found in {self.input_dir}"
            if self.recursive:
                message += " (including subdirectories)"
            self.logger.warning(message)
            return self.stats

        self.logger.info(f"Found {total_files} image file(s) in {self.input_dir}")

        if total_files == 1:
            self._process_single_file_wrapper(files[0])
        else:
            self._process_multiple_files(files, total_files)

        self.stats["end_time"] = datetime.now()
        self._print_summary(total_files)

        if self.failed_files:
            self._copy_failed_files()
        if self.no_metadata_files:
            self._copy_no_metadata_files()

        return self.stats

    def _process_multiple_files(self, files: List[Path], total_files: int) -> None:
        """
        Submit all image files to a thread pool and collect results as they complete.

        Args:
            files (List[Path]): Image paths to process.
            total_files (int): Total count used for the tqdm progress bar.
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_single_file, path): path
                for path in files
            }

            with tqdm(
                total=total_files,
                desc="Watermarking images",
                unit="file",
                disable=not self.verbose,
            ) as pbar:
                for future in as_completed(futures):
                    image_path = futures[future]
                    try:
                        success, message = future.result()
                        self._update_stats(success, image_path if not success else None)
                        if self.verbose:
                            tqdm.write(message)
                    except Exception as e:
                        self._update_stats(False, image_path)
                        error_msg = f"✗ {image_path.name}: Unexpected error - {e}"
                        if self.verbose:
                            tqdm.write(error_msg)
                        self.logger.error(error_msg)

                    pbar.update(1)

    def _process_single_file_wrapper(self, image_path: Path) -> None:
        """
        Process a single file outside the thread pool and log the result.

        Args:
            image_path (Path): Path to the image to process.
        """
        try:
            success, message = self._process_single_file(image_path)
            self._update_stats(success, image_path if not success else None)
            self.logger.info(message)
        except Exception as e:
            self._update_stats(False, image_path)
            self.logger.error(f"✗ {image_path.name}: Unexpected error - {e}")

    def _process_single_file(self, image_path: Path) -> Tuple[bool, str]:
        """
        Resolve watermark text then run the load → watermark → export pipeline.

        Watermark text resolution order:

        1. Metadata lookup by file stem (MIL number).
        2. Static fallback ``watermark_text``.
        3. No metadata — the file is appended to ``no_metadata_files``,
           its counter is incremented, and processing is skipped.

        Args:
            image_path (Path): Source image path.

        Returns:
            Tuple[bool, str]: A ``(success, message)`` pair where ``success``
                indicates whether the file was processed without error and
                ``message`` is a human-readable status string.
        """
        try:
            watermark_text = self._resolve_watermark_text(image_path)

            if not watermark_text:
                self.no_metadata_files.append(image_path)
                self.stats["no_metadata"] += 1
                return (
                    False,
                    f"? {image_path.name}: No metadata match for MIL# '{image_path.stem}' — queued for review",
                )

            dest_path = self._generate_output_path(image_path)

            if dest_path.exists() and not self.overwrite:
                self.stats["skipped"] += 1
                return (
                    False,
                    f"⊘ {image_path.name}: Skipped (output exists, overwrite=False)",
                )

            processor = WatermarkProcessor(
                file_path=image_path,
                watermark_text=watermark_text,
                opacity=self.opacity,
            )
            processor.load()
            processor.apply_text_watermark()
            processor.export(
                output_path=str(dest_path),
                format=self.output_format,
                max_resolution=self.max_resolution,
            )

            return True, f"✓ {image_path.name} [{watermark_text}] → {dest_path.name}"

        except FileNotFoundError as e:
            return False, f"✗ {image_path.name}: File not found - {e}"
        except PermissionError as e:
            return False, f"✗ {image_path.name}: Permission denied - {e}"
        except Exception as e:
            return False, f"✗ {image_path.name}: Processing failed - {e}"

    def _resolve_watermark_text(self, image_path: Path) -> Optional[str]:
        """
        Determine the watermark text for a given image file.

        Checks the metadata lookup table first using the file stem as the
        MIL number key. Falls back to the static ``watermark_text`` if no
        metadata record is found. Returns ``None`` if neither source yields
        a value, signalling that the file has no resolvable watermark.

        Args:
            image_path (Path): Source image whose stem is used as the lookup key.

        Returns:
            str | None: Resolved watermark text, or ``None`` if unresolvable.
        """
        if self.metadata:
            text = self.metadata.get_watermark_text(image_path.stem)
            if text:
                return text

        return self.watermark_text

    def _update_stats(self, success: bool, failed_path: Optional[Path] = None) -> None:
        """
        Increment success or failure counters and record the failed path if applicable.

        Files routed to ``no_metadata_files`` are tracked separately and do
        not pass through this method — they are appended directly inside
        ``_process_single_file`` to keep their handling self-contained.

        Args:
            success (bool): Whether the file was processed successfully.
            failed_path (Path | None): Path to record when ``success`` is False.
        """
        if success:
            self.stats["success"] += 1
        else:
            self.stats["failed"] += 1
            if failed_path:
                self.failed_files.append(failed_path)

    def _get_files(self) -> Generator[Path, None, None]:
        """
        Yield all supported image files in ``input_dir``.

        Yields:
            Path: Absolute path to each discovered image file.
        """
        extensions = {f"*.{ext}" for ext in self.SUPPORTED_FORMATS}
        pattern_prefix = "**/" if self.recursive else ""
        for ext_pattern in extensions:
            for path in self.input_dir.glob(f"{pattern_prefix}{ext_pattern}"):
                if path.is_file():
                    yield path

    def _generate_output_path(self, image_path: Path) -> Path:
        """
        Derive the output file path, preserving subdirectory structure when recursive.

        When ``recursive=True`` and ``output_dir != input_dir``, the relative
        subdirectory of the source file is recreated under ``output_dir`` so
        the original folder structure is mirrored in the output.

        Args:
            image_path (Path): Source image path.

        Returns:
            Path: Destination path including the converted file extension.
        """
        if self.recursive and self.output_dir != self.input_dir:
            relative_path = image_path.relative_to(self.input_dir)
            output_subdir = self.output_dir / relative_path.parent
            output_subdir.mkdir(parents=True, exist_ok=True)
            return output_subdir / f"{image_path.stem}.{self.output_format}"

        return self.output_dir / f"{image_path.stem}.{self.output_format}"

    def _copy_failed_files(self) -> None:
        """
        Copy all processing-error files to a ``failed_files/`` subdirectory
        inside ``output_dir`` for manual inspection after the job completes.
        """
        failed_dir = self.output_dir / "failed_files"
        failed_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Copying failed files to {failed_dir} for review.")
        for file in self.failed_files:
            shutil.copy(file, failed_dir)

    def _copy_no_metadata_files(self) -> None:
        """
        Copy all files that had no resolvable watermark metadata to a
        ``no_metadata/`` subdirectory inside ``output_dir``.

        These are source images whose file stem did not match any MIL number
        in the metadata file and for which no fallback ``watermark_text`` was
        provided. Copying them here preserves the originals in a dedicated
        location for manual review or re-processing once metadata is available.
        """
        no_meta_dir = self.output_dir / "no_metadata"
        no_meta_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Copying {len(self.no_metadata_files)} unmatched file(s) to {no_meta_dir} for review.")
        for file in self.no_metadata_files:
            shutil.copy(file, no_meta_dir)

    def _print_summary(self, total_files: int) -> None:
        """
        Print a formatted summary table after all files have been processed.

        Args:
            total_files (int): Total number of files discovered before processing.
        """
        duration = self.stats["end_time"] - self.stats["start_time"]

        print("\n" + "=" * 60)
        print("WATERMARKING COMPLETE")
        print("=" * 60)
        print(f"Total files:          {total_files}")
        print(f"✓ Successful:         {self.stats['success']}")
        print(f"✗ Failed:             {self.stats['failed']}")
        print(f"⊘ Skipped:            {self.stats['skipped']}")
        print(f"? No metadata:        {self.stats['no_metadata']}")
        print(f"Processing time:      {duration}")
        print(f"Output directory:     {self.output_dir}")
        print("=" * 60)

        if self.failed_files:
            print("\nFailed files:")
            for failed_file in self.failed_files:
                print(f"  - {failed_file}")

        if self.no_metadata_files:
            print("\nNo metadata match:")
            for f in self.no_metadata_files:
                print(f"  - {f}")

        self.logger.info(
            f"Watermark job completed: {self.stats['success']}/{total_files} successful, "
            f"{self.stats['no_metadata']} unmatched"
        )
