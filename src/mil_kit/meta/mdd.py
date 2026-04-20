"""
Merge metadata with mdd metadata then export as JSON.
"""
import polars as pl
import re

from PIL import Image
from pathlib import Path

MIL_COL = ["milNo", "genus", "specificEpithet", "descriptionOfImage", "photographer", "locationWhereImageTaken", "distributionOfSpecies", "dateImageTaken"]
MDD_COLS = ["id", "genus", "specificEpithet"]


class MetadataForMdd:
    """
    A class to merge metadata with mdd metadata and export as JSON.

    Attributes:
        mil_path (Path): Path to the MIL metadata file.
        mdd_path (Path): Path to the MDD metadata file.
        mil_img_dir (Path): Path to the MIL image directory.

    Methods:
        to_json(self, output_path: Path) -> None:
            Merge metadata with mdd metadata and export as JSON.
            Check if there are any missing images.
    """
    def __init__(self, mil_path: Path, mdd_path: Path, mil_img_dir: Path) -> None:
        self.mil_path = mil_path
        self.mdd_path = mdd_path
        self.mil_img_dir = mil_img_dir

    def to_json(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() != ".json":
            output_path = output_path.with_suffix(output_path.suffix + ".json")
        merged_df = self._load_metadata()
        merged_df.write_json(output_path)

    def _load_metadata(self) -> pl.DataFrame:
        mil_df = self._load_file(self.mil_path)
        mdd_df = self._load_file(self.mdd_path)
        mil_df = self._clean_column_names(mil_df)
        mdd_df = self._clean_column_names(mdd_df)

        mil_df = (
            mil_df.select(MIL_COL)
            .rename({
                "milNo": "milId",
                "descriptionOfImage": "description",
                "locationWhereImageTaken": "location",
                "distributionOfSpecies": "distribution",
                "dateImageTaken": "dateTaken",
            })
            .with_columns([
                pl.col("specificEpithet").str.ends_with("?").alias("isUncertainIdentification"),
                pl.col("specificEpithet").map_elements(
                    self._strip_epithet_qualifier, return_dtype=pl.String
                ).alias("specificEpithet"),
            ])
            .with_columns(
                (pl.col("genus") + "_" + pl.col("specificEpithet")).alias("scientificName")
            )
            .drop(["genus", "specificEpithet"])
        )

        mdd_df = (
            mdd_df.select(MDD_COLS)
            .rename({"id": "mddId"})
            .with_columns(
                (pl.col("genus") + "_" + pl.col("specificEpithet")).alias("scientificName")
            )
            .drop(["genus", "specificEpithet"])
        )

        merged_df = mil_df.join(mdd_df, on="scientificName", how="left")
        img_df = self._build_img_df()
        merged_df = merged_df.join(img_df, on="milId", how="left")
        self._check_missing_images(merged_df)
        return merged_df.drop("scientificName")
    
    def _check_missing_images(self, merged_df: pl.DataFrame) -> None:
        """Check for missing images. Raise an error if any images are missing."""
        missing_images = merged_df.filter(pl.col("orientation").is_null())
        if missing_images.height > 0:
            missing_mil_ids = missing_images.select("milId").to_series().to_list()
            missing_mil_ids.sort()
            raise ValueError(f"Missing {len(missing_mil_ids)} images: {missing_mil_ids}")
    
    def _build_img_df(self) -> pl.DataFrame:
        """Build a dataframe of all images in the MIL image directory. Return a dataframe of images."""
        image_files = self._find_all_images()
        img_df = pl.DataFrame({
            "milId": [self._get_mil_id_from_filename(f) for f in image_files],
            "orientation": [self._get_orientation_from_image(f) for f in image_files],
        })
        return img_df

    def _find_all_images(self) -> list[Path]:
        """Read all images in the MIL image directory. Return a list of paths to the images."""
        found_files = self.mil_img_dir.rglob("*")
        image_files = [f for f in found_files if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")]
        return image_files
        
    def _get_mil_id_from_filename(self, file_path: Path) -> str:
        """Extract the MIL ID from the filename. Return the MIL ID."""
        return file_path.stem

    def _get_orientation_from_image(self, file_path: Path) -> str:
        """Extract the orientation from the filename. Return the orientation."""
        with Image.open(file_path) as img:
            width, height = img.size
            if width > height:
                return "landscape"
            elif width < height:
                return "portrait"
            else:
                return "square"

    @staticmethod
    def _strip_epithet_qualifier(epithet: str | None) -> str | None:
        """Removes a trailing '?' qualifier from specificEpithet.
        
        A trailing '?' indicates an uncertain species-level identification,
        following open nomenclature conventions (cf. Darwin Core identificationQualifier).
        """
        if epithet is None:
            return None
        return epithet.removesuffix("?")


    def _clean_column_names(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Clean column names by stripping whitespace, replacing '#' with 'No',
        removing special characters, and converting to camelCase.

        Args:
            df (pl.DataFrame): Input dataframe with raw column names.

        Returns:
            pl.DataFrame: Dataframe with cleaned column names.
        """
        def to_camel(col: str) -> str:
            col = col.strip().replace("#", "No")
            col = re.sub(r"[^\w\s]", "", col)     
            words = re.sub(r"([a-z])([A-Z])", r"\1 \2", col).split()
            return words[0].lower() + "".join(w.capitalize() for w in words[1:])

        return df.rename(to_camel)



    def _load_file(self, file_path: Path) -> pl.DataFrame:
        """
        Dispatch file loading based on the file extension.

        Polars reads all columns as strings (``infer_schema_length=0``) to
        prevent MIL numbers from being silently cast to floats or integers,
        which would break string-based key matching.

        Returns:
            pl.DataFrame: Raw dataframe from the source file.
        """
        suffix = file_path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            return pl.read_excel(file_path, infer_schema_length=0)
        return pl.read_csv(file_path, infer_schema_length=0)
