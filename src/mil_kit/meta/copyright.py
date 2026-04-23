
from __future__ import annotations

from pathlib import Path
from typing import Dict

import polars as pl


class MetadataParser:
    """
    Parses image metadata from an Excel or CSV file and builds a lookup
    table mapping MIL numbers to formatted watermark strings.

    Only two columns are retained from the source file regardless of how
    many columns are present: the MIL number column and the Photographer
    column. All other columns are discarded after loading.

    The watermark text for each record is formatted as::

        {Photographer} / ASM-MIL

    The lookup table is keyed by the MIL number cast to a string so it
    can be matched directly against an image file stem (e.g. ``"2314"``).

    Attributes:
        file_path (Path): Path to the source metadata file.
        mil_col (str): Raw column name used for the MIL number field.
        photographer_col (str): Raw column name used for the Photographer field.
        records (Dict[str, str]): Populated after ``parse()`` is called.
            Maps MIL number string → watermark text string.

    Example:
        >>> parser = MetadataParser("meta.xlsx")
        >>> parser.parse()
        >>> text = parser.get_watermark_text("2314")
        >>> print(text)
        HA York / ASM-MIL
    """

    _SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
    _WATERMARK_SUFFIX = "ASM-MIL"

    def __init__(
        self,
        file_path: str,
        mil_col: str = "MIL #",
        photographer_col: str = "Photographer",
    ) -> None:
        """
        Initialise the parser with a path to a metadata file.

        Args:
            file_path (str): Path to an Excel (``.xlsx``, ``.xls``) or
                CSV (``.csv``) metadata file.
            mil_col (str): Column name for the MIL number field.
                Defaults to ``"MIL #"`` to match the standard template.
            photographer_col (str): Column name for the photographer field.
                Defaults to ``"Photographer"``.

        Raises:
            FileNotFoundError: If ``file_path`` does not exist.
            ValueError: If the file extension is not supported.
        """
        self.file_path = Path(file_path)
        self.mil_col = mil_col
        self.photographer_col = photographer_col
        self.records: Dict[str, str] = {}

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"Metadata file not found: {self.file_path}"
            )
        if self.file_path.suffix.lower() not in self._SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: '{self.file_path.suffix}'. "
                f"Supported: {', '.join(self._SUPPORTED_EXTENSIONS)}"
            )

    def parse(self) -> Dict[str, str]:
        """
        Load the metadata file, extract MIL numbers and photographer names,
        and build the internal ``records`` lookup table.

        Column names are normalised by stripping leading/trailing whitespace
        before matching, so minor formatting differences in the source file
        are tolerated. Rows where either the MIL number or the photographer
        name is null or empty are silently dropped.

        Returns:
            Dict[str, str]: The populated ``records`` mapping of
                ``{mil_number: watermark_text}``.

        Raises:
            KeyError: If ``mil_col`` or ``photographer_col`` cannot be found
                in the file after normalisation.
            IOError: If the file cannot be read or parsed.
        """
        try:
            df = self._load_file()
        except Exception as e:
            raise IOError(f"Failed to read metadata file: {e}")

        df = df.rename({col: col.strip() for col in df.columns})

        missing = [
            col for col in (self.mil_col, self.photographer_col)
            if col not in df.columns
        ]
        if missing:
            raise KeyError(
                f"Column(s) not found in metadata file: {missing}. "
                f"Available columns: {df.columns}"
            )

        df = (
            df
            .select([self.mil_col, self.photographer_col])
            .with_columns([
                pl.col(self.mil_col).cast(pl.Utf8).str.strip_chars(),
                pl.col(self.photographer_col)
                .cast(pl.Utf8)
                .str.strip_chars()
                .fill_null("")
            ])
            .drop_nulls([self.mil_col])
            .filter(
                pl.col(self.mil_col).str.len_chars().gt(0)
            )
        )

        self.records = {}
        for row in df.iter_rows(named=True):
            mil_key = self._to_int_str(row[self.mil_col])
            if mil_key is not None:
                photographer = row[self.photographer_col]
                if not photographer:
                    photographer = "Unknown"
                self.records[mil_key] = self._format_watermark(photographer)

        return self.records

    def normalize_stem(self, file_stem: str) -> str | None:
        """
        Return the normalised integer key for a given file stem.

        Convenience wrapper around :meth:`_to_int_str` used by callers that
        need to inspect the lookup key without performing a full lookup.

        Args:
            file_stem (str): Raw file stem string to normalise.

        Returns:
            str | None: Plain integer string, or ``None`` if not parseable.
        """
        return self._to_int_str(file_stem.strip())

    def get_watermark_text(self, file_stem: str) -> str | None:
        """
        Return the watermark text for a given file stem (MIL number).

        Both the file stem and the MIL numbers stored in ``records`` are
        normalised to plain integer strings (e.g. ``"2314.0"`` → ``"2314"``)
        so that float-formatted values read from Excel always match.

        Args:
            file_stem (str): The image file stem to look up, expected to
                match a MIL number in the metadata (e.g. ``"2314"``).

        Returns:
            str | None: The formatted watermark string
                (e.g. ``"HA York / ASM-MIL"``) if a match is found,
                or ``None`` if the file stem is not in the records.
        """
        key = self._to_int_str(file_stem.strip())
        if key is None:
            return None
        return self.records.get(key)

    @staticmethod
    def _to_int_str(value: str) -> str | None:
        """
        Convert a string representation of a number to a plain integer string.

        Handles both integer strings (``"2314"``) and float strings that Excel
        may produce (``"2314.0"``). Returns ``None`` if the value cannot be
        parsed as a number.

        Args:
            value (str): The raw string to normalise.

        Returns:
            str | None: Plain integer string (e.g. ``"2314"``), or ``None``
                if parsing fails.
        """
        try:
            return str(int(float(value)))
        except (ValueError, TypeError):
            return None

    def _load_file(self) -> pl.DataFrame:
        """
        Dispatch file loading based on the file extension.

        Polars reads all columns as strings (``infer_schema_length=0``) to
        prevent MIL numbers from being silently cast to floats or integers,
        which would break string-based key matching.

        Returns:
            pl.DataFrame: Raw dataframe from the source file.
        """
        suffix = self.file_path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            return pl.read_excel(
                self.file_path,
                infer_schema_length=0,
            )
        return pl.read_csv(
            self.file_path,
            infer_schema_length=0,
        )

    def _format_watermark(self, photographer: str) -> str:
        """
        Format a photographer name into the standard watermark string.

        Args:
            photographer (str): Photographer name as read from the metadata.

        Returns:
            str: Formatted string in the form ``"{photographer} / ASM-MIL"``.
        """
        return f"{photographer} / {self._WATERMARK_SUFFIX}"
