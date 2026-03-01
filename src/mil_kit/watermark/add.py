from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import os


class WatermarkProcessor:
    """
    Handles loading, watermarking, and exporting of a single image file.

    This class follows a strict three-step pipeline:
        1. ``load()``                 — open the source image into memory
        2. ``apply_text_watermark()`` — render a copyright watermark onto it
        3. ``export()``               — save the result to disk

    Each step must be called in order. Calling ``export()`` before
    ``apply_text_watermark()``, or either before ``load()``, will raise
    a ``RuntimeError``.

    The watermark is rendered as a copyright notice (e.g.
    ``© 2024 Studio Name``) anchored to the bottom-left corner of the
    image with a semi-transparent dark pill background for legibility
    on both light and dark images. When the text is wider than the
    available canvas width, it is automatically wrapped onto multiple
    lines so no text is ever clipped.

    Attributes:
        file_path (Path): Absolute or relative path to the source image.
        watermark_text (str): The copyright text to render. A ``©`` symbol
            is prepended automatically if not already present.
        opacity (float): Watermark opacity in the range [0.0, 1.0], where
            0.0 is fully transparent and 1.0 is fully opaque.
        image (Image.Image | None): The loaded source image in RGBA mode.
            ``None`` until ``load()`` is called.
        watermarked (Image.Image | None): The composited result after
            ``apply_text_watermark()`` is called. ``None`` beforehand.

    Example:
        >>> processor = WatermarkProcessor("photo.png", watermark_text="2024 Studio Name", opacity=0.8)
        >>> processor.load()
        >>> processor.apply_text_watermark()
        >>> processor.export("output/photo.png", format="png", max_resolution=1920)
    """

    _COPYRIGHT_SYMBOL = "©"
    _PADDING = 8
    _MARGIN = 4
    _LINE_SPACING = 4
    _FONT_DIVISOR = 40
    _MIN_FONT_SIZE = 12
    _BACKGROUND_COLOR = (0, 0, 0)
    _TEXT_COLOR = (255, 255, 255)
    _CORNER_RADIUS = 6

    def __init__(
        self,
        file_path: str,
        watermark_text: str,
        opacity: float = 0.8,
    ) -> None:
        """
        Initialises the processor with a source file path and watermark settings.

        Args:
            file_path (str): Path to the source image file. Supported formats
                are any format readable by Pillow (PNG, JPEG, TIFF, BMP, WebP, etc.).
            watermark_text (str): Non-empty copyright text to render. If the
                string does not already begin with ``©``, the symbol is
                prepended automatically (e.g. ``"2024 Studio"`` becomes
                ``"© 2024 Studio"``).
            opacity (float): Watermark opacity between 0.0 (invisible) and
                1.0 (fully opaque). Defaults to 0.8.

        Raises:
            ValueError: If ``watermark_text`` is empty or ``opacity`` is
                outside the [0.0, 1.0] range.
        """
        if not watermark_text:
            raise ValueError("watermark_text must be provided.")
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0.")

        self.file_path = Path(file_path)
        self.watermark_text = (
            watermark_text
            if watermark_text.startswith(self._COPYRIGHT_SYMBOL)
            else f"{self._COPYRIGHT_SYMBOL} {watermark_text}"
        )
        self.opacity = opacity

        self.image: Image.Image | None = None
        self.watermarked: Image.Image | None = None

    def load(self) -> None:
        """
        Opens the source image from ``file_path`` and converts it to RGBA mode.

        Converting to RGBA ensures a consistent alpha channel is present before
        compositing, regardless of the original image mode (e.g. RGB, L, P).

        Raises:
            IOError: If the file cannot be opened or is not a valid image format.
        """
        try:
            self.image = Image.open(self.file_path).convert("RGBA")
        except Exception as e:
            raise IOError(f"Failed to open image: {e}")

    def apply_text_watermark(self) -> None:
        """
        Renders a copyright watermark anchored to the bottom-left corner.

        Layout:
            - Font size scales with canvas width (``width // 40``), with a
              minimum of ``_MIN_FONT_SIZE`` px, ensuring legibility across
              image sizes.
            - If the full text exceeds the available canvas width (minus
              margins and padding), it is word-wrapped onto multiple lines.
              Each line is fitted greedily word by word so the pill never
              overflows the canvas horizontally.
            - The text block is drawn inside a rounded-rectangle pill with a
              semi-transparent dark background so it remains readable on
              both light and dark source images.
            - ``_LINE_SPACING`` extra pixels are added between each wrapped
              line for readability.
            - A margin of ``_MARGIN`` px separates the pill from the canvas
              edges on all sides.
            - Both the pill background and text alpha are derived from
              ``self.opacity`` so a single parameter controls the overall
              watermark intensity.

        The watermark layer is composited onto ``self.image`` using
        ``Image.alpha_composite`` and the result is stored in
        ``self.watermarked``.

        Raises:
            RuntimeError: If ``load()`` has not been called beforehand.
        """
        if not self.image:
            raise RuntimeError("Image not loaded. Call load() first.")

        layer = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        font = self._load_font(
            size=max(self._MIN_FONT_SIZE, self.image.width // self._FONT_DIVISOR)
        )

        max_text_width = self.image.width - (self._MARGIN + self._PADDING) * 2
        lines = self._wrap_text(self.watermark_text, font, max_text_width, draw)

        line_height = self._line_height(font, draw)
        total_text_h = (
            line_height * len(lines)
            + self._LINE_SPACING * (len(lines) - 1)
        )
        widest_line_w = max(
            draw.textlength(line, font=font) for line in lines
        )

        bg_alpha = int(180 * self.opacity)
        text_alpha = int(255 * self.opacity)

        pill_x0 = self._MARGIN
        pill_y0 = self.image.height - total_text_h - (self._PADDING * 2) - self._MARGIN
        pill_x1 = pill_x0 + int(widest_line_w) + (self._PADDING * 2)
        pill_y1 = pill_y0 + total_text_h + (self._PADDING * 2)

        draw.rounded_rectangle(
            [pill_x0, pill_y0, pill_x1, pill_y1],
            radius=self._CORNER_RADIUS,
            fill=(*self._BACKGROUND_COLOR, bg_alpha),
        )

        text_x = pill_x0 + self._PADDING
        text_y = pill_y0 + self._PADDING
        for line in lines:
            draw.text(
                (text_x, text_y),
                line,
                fill=(*self._TEXT_COLOR, text_alpha),
                font=font,
            )
            text_y += line_height + self._LINE_SPACING

        self.watermarked = Image.alpha_composite(self.image, layer)

    def export(
        self,
        output_path: str,
        format: str = "png",
        max_resolution: int | None = None,
    ) -> None:
        """
        Saves the watermarked image to disk at the specified path.

        The output directory is created automatically if it does not exist.
        When ``max_resolution`` is set, ``Image.thumbnail`` is used to
        downscale the image so that neither dimension exceeds the given value
        while preserving the original aspect ratio. Images smaller than
        ``max_resolution`` are never upscaled.

        Because JPEG does not support an alpha channel, images saved in JPEG
        format are automatically converted from RGBA to RGB before writing.
        All other formats retain the alpha channel.

        Args:
            output_path (str): Destination file path, including file name
                and extension (e.g. ``"output/result.png"``).
            format (str): Pillow-compatible format string such as ``"png"``,
                ``"jpeg"``, or ``"tiff"``. Case-insensitive. Defaults to
                ``"png"``.
            max_resolution (int | None): If provided, the image is downscaled
                so its longest side does not exceed this value in pixels.
                Defaults to ``None`` (no resizing).

        Raises:
            RuntimeError: If ``load()`` has not been called, or if
                ``apply_text_watermark()`` has not been called.
        """
        if not self.image:
            raise RuntimeError("Image not loaded. Call load() first.")
        if not self.watermarked:
            raise RuntimeError("Watermark not applied. Call apply_text_watermark() first.")

        output = self.watermarked
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if max_resolution:
            output = output.copy()
            output.thumbnail(
                (max_resolution, max_resolution),
                resample=Image.LANCZOS,
            )

        if format.lower() in ("jpg", "jpeg"):
            output = output.convert("RGB")

        output.save(output_path, format=format.upper())

    @staticmethod
    def _wrap_text(
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        max_width: int,
        draw: ImageDraw.ImageDraw,
    ) -> list[str]:
        """
        Word-wrap ``text`` so no rendered line exceeds ``max_width`` pixels.

        Words are added to the current line greedily. When adding the next
        word would exceed ``max_width``, the current line is flushed and a
        new line is started. A single word that is itself wider than
        ``max_width`` is placed on its own line without splitting — it will
        overflow slightly rather than break mid-word.

        Args:
            text (str): The full watermark string to wrap.
            font: The font used to measure rendered text widths.
            max_width (int): Maximum allowed line width in pixels.
            draw (ImageDraw.ImageDraw): Draw context used for text measurement.

        Returns:
            list[str]: Ordered list of wrapped lines ready for rendering.
        """
        words = text.split()
        lines: list[str] = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

        return lines

    @staticmethod
    def _line_height(
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        draw: ImageDraw.ImageDraw,
    ) -> int:
        """
        Return the rendered pixel height of a single line of text.

        Uses a representative uppercase string to capture ascenders and
        descenders consistently across different font sizes.

        Args:
            font: The font to measure.
            draw (ImageDraw.ImageDraw): Draw context used for measurement.

        Returns:
            int: Line height in pixels.
        """
        bbox = font.getbbox("Ag")
        return bbox[3] - bbox[1]

    @staticmethod
    def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """
        Attempts to load a bold TrueType font at the given point size.

        Walks a list of common system font paths for Linux, macOS, and Windows.
        Returns the first font found as a ``FreeTypeFont``. Falls back to
        Pillow's built-in bitmap font if no system font is available, which
        ignores the ``size`` argument and renders at a fixed small size.

        Args:
            size (int): Desired font size in points for TrueType fonts.

        Returns:
            ImageFont.FreeTypeFont | ImageFont.ImageFont: A loaded font object
                ready for use with ``ImageDraw.text()``.
        """
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()
