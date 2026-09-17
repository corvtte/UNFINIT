"""
services/image_service.py - SVG and Image conversion service for UNFINIT Store Engine
Supports converting vector SVG files to high-resolution PNG (preserving alpha transparency)
and JPG (with white background fallback).
Uses cairosvg primarily, with svglib + reportlab as pure-Python fallback.
"""

import io
import re
import html
import logging
import xml.etree.ElementTree as ET
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

    @classmethod
    def convert_svg_to_image(
        cls,
        svg_input: Union[str, Path, bytes],
        fmt: str = "PNG",
        output_path: Optional[Union[str, Path]] = None,
        scale: float = 2.0,
        dpi: int = 300,
        **kwargs
    ) -> bytes:
        """
        Convert SVG to either PNG (transparent alpha) or JPG (white background).
        """
        fmt_clean = str(fmt).upper().strip()
        if fmt_clean in ("JPG", "JPEG"):
            return cls.convert_svg_to_jpg(svg_input, output_path=output_path, scale=scale, dpi=dpi, **kwargs)
        return cls.convert_svg_to_png(svg_input, output_path=output_path, scale=scale, dpi=dpi)

    @classmethod
    def recolor_svg(cls, svg_input: Union[str, bytes], hex_color: str) -> str:
        """
        Recolor SVG fill and stroke attributes and styles to hex_color,
        preserving vector structure and skipping 'none', 'transparent', and 'url(...)'.
        Returns recolored SVG string.
        """
        if isinstance(svg_input, bytes):
            svg_str = svg_input.decode("utf-8", errors="replace")
        else:
            svg_str = str(svg_input)

        clean_hex = str(hex_color).strip()
        if not clean_hex.startswith("#") and len(clean_hex) in (3, 6, 8):
            clean_hex = f"#{clean_hex}"

        # Strategy 1: ElementTree XML Manipulation
        try:
            ET.register_namespace("", "http://www.w3.org/2000/svg")
            root = ET.fromstring(svg_str.encode("utf-8"))
            for elem in root.iter():
                # 1. Attribute fill
                if "fill" in elem.attrib:
                    f_val = elem.attrib["fill"].strip().lower()
                    if f_val not in ("none", "transparent") and not f_val.startswith("url("):
                        elem.attrib["fill"] = clean_hex

                # 2. Attribute stroke
                if "stroke" in elem.attrib:
                    s_val = elem.attrib["stroke"].strip().lower()
                    if s_val not in ("none", "transparent") and not s_val.startswith("url("):
                        elem.attrib["stroke"] = clean_hex

                # 3. Inline style
                if "style" in elem.attrib:
                    styles = elem.attrib["style"].split(";")
                    new_styles = []
                    for st in styles:
                        if not st.strip():
                            continue
                        if ":" in st:
                            prop, val = st.split(":", 1)
                            p_clean = prop.strip().lower()
                            v_clean = val.strip().lower()
                            if p_clean == "fill" and v_clean not in ("none", "transparent") and not v_clean.startswith("url("):
                                new_styles.append(f"{prop.strip()}:{clean_hex}")
                            elif p_clean == "stroke" and v_clean not in ("none", "transparent") and not v_clean.startswith("url("):
                                new_styles.append(f"{prop.strip()}:{clean_hex}")
                            else:
                                new_styles.append(st.strip())
                        else:
                            new_styles.append(st.strip())
                    elem.attrib["style"] = "; ".join(new_styles)

                # 4. Content of <style> tags
                if elem.tag.endswith("style") and elem.text:
                    def _recolor_css(m):
                        prop, val = m.group(1), m.group(2).strip()
                        if val.lower() in ("none", "transparent") or val.lower().startswith("url("):
                            return m.group(0)
                        return f"{prop}: {clean_hex}"

                    elem.text = re.sub(r'\b(fill|stroke)\s*:\s*([^;}"\']+)', _recolor_css, elem.text, flags=re.IGNORECASE)

            recolored_xml = ET.tostring(root, encoding="unicode")
            if "<svg" in recolored_xml:
                return recolored_xml
        except Exception as e_xml:
            logger.debug("[recolor_svg] XML parsing fallback to regex: %s", e_xml)

        # Strategy 2: Robust Regex Replacement Fallback
        def _recolor_attr_fb(m):
            attr, q1, val, q2 = m.group(1), m.group(2), m.group(3).strip(), m.group(4)
            if val.lower() in ("none", "transparent") or val.lower().startswith("url("):
                return m.group(0)
            return f"{attr}={q1}{clean_hex}{q2}"

        def _recolor_prop_fb(m):
            prop, val = m.group(1), m.group(2).strip()
            if val.lower() in ("none", "transparent") or val.lower().startswith("url("):
                return m.group(0)
            return f"{prop}: {clean_hex}"

        res = svg_str
        res = re.sub(r'\b(fill|stroke)\s*=\s*(["\'])([^"\']*)(["\'])', _recolor_attr_fb, res, flags=re.IGNORECASE)
        res = re.sub(r'\b(fill|stroke)\s*:\s*([^;}"\']+)', _recolor_prop_fb, res, flags=re.IGNORECASE)
        return res

    @classmethod
    def text_to_svg(
        cls,
        text: str,
        font_size: int = 48,
        fill: str = "#FFFFFF",
        font_family: str = "Vazirmatn, Arial, sans-serif"
    ) -> str:
        """
        Generate clean, scalable SVG vector markup containing the text.
        """
        clean_text = str(text or "").strip()
        width = max(240, int(len(clean_text) * font_size * 0.75 + 80))
        height = max(120, int(font_size * 2.6))
        clean_hex = str(fill).strip()
        if not clean_hex.startswith("#") and len(clean_hex) in (3, 6, 8):
            clean_hex = f"#{clean_hex}"

        escaped_text = html.escape(clean_text)
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    .svg-text {{
      font-family: {font_family};
      font-size: {font_size}px;
      font-weight: bold;
      fill: {clean_hex};
      text-anchor: middle;
      dominant-baseline: central;
    }}
  </style>
  <text x="{width // 2}" y="{height // 2}" font-size="{font_size}" fill="{clean_hex}" class="svg-text">{escaped_text}</text>
</svg>'''

image_service = ImageService()
