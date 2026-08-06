#!/usr/bin/env python3
"""Convert SVG files to PNG for DOCX embedding.

Engine order:
1) cairosvg  (best fidelity; needs cairo runtime, may be unavailable on Windows)
2) svglib + reportlab  (pure-python fallback)

Usage:
    python scripts/svg_to_png.py input.svg [-o output.png] [--width 1200]

Exit code 0 on success, 1 when every engine failed.
"""

import argparse
import os
import sys
from pathlib import Path


def convert_with_cairosvg(svg_path: Path, png_path: Path, width: int) -> None:
    import cairosvg  # noqa: PLC0415

    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=width)


CJK_FONT_CANDIDATES = [
    # (font file path, subfontIndex for .ttc collections)
    (r"C:\Windows\Fonts\simhei.ttf", None),        # Windows SimHei
    (r"C:\Windows\Fonts\msyh.ttc", 0),             # Windows Microsoft YaHei
    (r"C:\Windows\Fonts\simsun.ttc", 0),           # Windows SimSun
    ("/System/Library/Fonts/PingFang.ttc", 0),     # macOS PingFang
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),  # Linux Noto
    ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),          # Linux WenQuanYi
]

CJK_FONT_NAME = "SWSkillCJK"


def _register_cjk_font() -> str:
    """Register the first available CJK TTF via svglib's font map (which also
    registers it with reportlab). Returns the usable font name."""
    from svglib.svglib import register_font  # noqa: PLC0415

    for path, subfont_index in CJK_FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            # svglib's register_font wires the font into both its own FontMap
            # and reportlab's pdfmetrics; plain pdfmetrics.registerFont alone
            # leaves svglib falling back to Helvetica.
            name, ok = register_font(CJK_FONT_NAME, path)
            if ok and name:
                return name
        except Exception:
            # Retry .ttc collections via reportlab with explicit subfont index,
            # then teach svglib's map the alias.
            try:
                from reportlab.pdfbase import pdfmetrics  # noqa: PLC0415
                from reportlab.pdfbase.ttfonts import TTFont  # noqa: PLC0415
                from svglib.fonts import _font_map  # noqa: PLC0415

                kwargs = {"subfontIndex": subfont_index} if subfont_index is not None else {}
                pdfmetrics.registerFont(TTFont(CJK_FONT_NAME, path, **kwargs))
                _font_map.register_font(CJK_FONT_NAME, rlgFontName=CJK_FONT_NAME)
                return CJK_FONT_NAME
            except Exception:
                continue
    return ""


def _inject_font_family(svg_text: str, font_name: str) -> str:
    """Force every <text>/<tspan> without an explicit font-family onto font_name."""
    import re  # noqa: PLC0415

    def _fix_tag(match: "re.Match") -> str:
        tag = match.group(0)
        if "font-family" in tag:
            # Replace whatever family was requested; unmapped families render as
            # tofu under renderPM, while our registered font covers CJK + Latin.
            tag = re.sub(r"font-family:[^;\"']*", f"font-family:{font_name}", tag)
            tag = re.sub(r'font-family="[^"]*"', f'font-family="{font_name}"', tag)
            return tag
        # svglib resolves fonts from the CSS `style` attribute, not the XML
        # `font-family` attribute, so inject into style.
        style_match = re.search(r'style="([^"]*)"', tag)
        if style_match:
            new_style = f"font-family:{font_name};" + style_match.group(1)
            return tag.replace(style_match.group(0), f'style="{new_style}"')
        return tag[:-1] + f' style="font-family:{font_name}">'

    return re.sub(r"<(text|tspan)\b[^>]*?>", _fix_tag, svg_text)


def convert_with_svglib(svg_path: Path, png_path: Path, width: int) -> None:
    import sys  # noqa: PLC0415

    # rlPyCairo (reportlab's renderPM backend) does `try: import cairocffi
    # except ImportError: import cairo`. When cairocffi is installed but the
    # system cairo DLL is missing (typical on Windows), cairocffi raises
    # OSError which escapes that guard. Poison the broken module so rlPyCairo
    # falls back to pycairo, whose Windows wheel bundles cairo.
    try:
        import cairocffi  # noqa: F401, PLC0415
    except Exception:
        sys.modules["cairocffi"] = None

    from reportlab.graphics import renderPM  # noqa: PLC0415
    from svglib.svglib import svg2rlg  # noqa: PLC0415

    font_name = _register_cjk_font()
    if font_name:
        svg_text = _inject_font_family(svg_path.read_text(encoding="utf-8"), font_name)
        tmp_svg = svg_path.with_suffix(".fontfixed.svg")
        tmp_svg.write_text(svg_text, encoding="utf-8")
        try:
            drawing = svg2rlg(str(tmp_svg))
        finally:
            tmp_svg.unlink(missing_ok=True)
    else:
        drawing = svg2rlg(str(svg_path))

    if drawing is None:
        raise RuntimeError("svglib could not parse the SVG file")
    # Scale so that output width matches the requested pixel width.
    scale = width / drawing.width if drawing.width else 1.0
    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)
    renderPM.drawToFile(drawing, str(png_path), fmt="PNG", dpi=96)


ENGINES = [
    ("cairosvg", convert_with_cairosvg),
    ("svglib", convert_with_svglib),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert SVG to PNG (cairosvg, svglib fallback).")
    parser.add_argument("svg", help="Input SVG file path")
    parser.add_argument("-o", "--output", help="Output PNG path (default: same name with .png)")
    parser.add_argument("--width", type=int, default=1200, help="Output width in px (default: 1200)")
    args = parser.parse_args()

    svg_path = Path(args.svg)
    if not svg_path.exists():
        print(f"Input SVG not found: {svg_path}")
        return 1
    png_path = Path(args.output) if args.output else svg_path.with_suffix(".png")
    png_path.parent.mkdir(parents=True, exist_ok=True)

    errors = []
    for name, func in ENGINES:
        try:
            func(svg_path, png_path, args.width)
            print(f"OK [{name}] {svg_path} -> {png_path} (width={args.width}px)")
            return 0
        except Exception as e:  # try next engine
            errors.append(f"[{name}] {e}")

    print("All engines failed:")
    for err in errors:
        print(f"  {err}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
