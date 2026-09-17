"""
services/image_service.py - SVG and Image conversion service for UNFINIT Store Engine
Supports converting vector SVG files to high-resolution PNG (preserving alpha transparency)
and JPG (with white background fallback).
Uses cairosvg primarily, with svglib + reportlab as pure-Python fallback.
"""

import io
import logging
from pathlib import Path
from typing import Optional, Union, Tuple
from PIL import Image

logger = logging.getLogger("unfinit.image_service")

class ImageService:
    @staticmethod
    def is_svg(file_path_or_bytes: Union[str, Path, bytes]) -> bool:
        """Check if the provided content or file is an SVG."""
        try:
            if isinstance(file_path_or_bytes, (str, Path)):
                p = Path(file_path_or_bytes)
                if p.suffix.lower() == ".svg":
                    return True
                with open(p, "rb") as f:
                    sample = f.read(512).lower()
                    return b"<svg" in sample or b"<?xml" in sample
            elif isinstance(file_path_or_bytes, bytes):
                sample = file_path_or_bytes[:512].lower()
                return b"<svg" in sample or b"<?xml" in sample
        except Exception:
            pass
        return False

    @classmethod
    def convert_svg_to_png(
        cls,
        svg_input: Union[str, Path, bytes],
        output_path: Optional[Union[str, Path]] = None,
        scale: float = 2.0,
        dpi: int = 300
    ) -> bytes:
        """
        Convert SVG to PNG with alpha transparency preserved.
        Returns PNG bytes and optionally writes to output_path.
        """
        svg_bytes: bytes
        if isinstance(svg_input, (str, Path)):
            with open(svg_input, "rb") as f:
                svg_bytes = f.read()
        else:
            svg_bytes = svg_input

        png_data: Optional[bytes] = None

        # 1. Attempt cairosvg
        try:
            import cairosvg
            png_data = cairosvg.svg2png(bytestring=svg_bytes, scale=scale, dpi=dpi)
        except Exception as e_cairo:
            logger.debug("cairosvg conversion unavailable or failed: %s", e_cairo)

        # 2. Fallback to svglib + reportlab
        if png_data is None:
            try:
                from svglib.svglib import svg2rlg
                from reportlab.graphics import renderPM

                drawing = svg2rlg(io.BytesIO(svg_bytes))
                if drawing is not None:
                    out_buf = io.BytesIO()
                    renderPM.drawToFile(drawing, out_buf, fmt="PNG", dpi=dpi)
                    png_data = out_buf.getvalue()
            except Exception as e_svglib:
                logger.warning("svglib conversion failed: %s", e_svglib)

        if png_data is None:
            raise RuntimeError("SVG conversion failed: neither cairosvg nor svglib was able to process the SVG file.")

        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "wb") as f:
                f.write(png_data)

        return png_data

    @classmethod
    def convert_svg_to_jpg(
        cls,
        svg_input: Union[str, Path, bytes],
        output_path: Optional[Union[str, Path]] = None,
        scale: float = 2.0,
        dpi: int = 300,
        quality: int = 95,
        bg_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> bytes:
        """
        Convert SVG to JPG with solid background (default white).
        Returns JPG bytes and optionally writes to output_path.
        """
        # First get high-res PNG bytes
        png_bytes = cls.convert_svg_to_png(svg_input, scale=scale, dpi=dpi)
        
        # Load into PIL, flatten transparency with background color, save as JPG
        with Image.open(io.BytesIO(png_bytes)) as im:
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                im_converted = im.convert("RGBA")
                background = Image.new("RGB", im_converted.size, bg_color)
                background.paste(im_converted, mask=im_converted.split()[3])
                rgb_im = background
            else:
                rgb_im = im.convert("RGB")

            out_buf = io.BytesIO()
            rgb_im.save(out_buf, format="JPEG", quality=quality, optimize=True)
            jpg_data = out_buf.getvalue()

        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "wb") as f:
                f.write(jpg_data)

        return jpg_data

image_service = ImageService()
