"""Shared chart tokens and controlled SVG paints; never accepts model-authored code."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

BLUE, ORANGE, INK, GRAY = "#204B8C", "#F45938", "#1B1D1E", "#6F7679"
PALE, BORDER, WHITE = "#EDF2F8", "#A6BAD5", "#FFFFFF"
FONT = "Noto Serif SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif"
PALETTES = {
    "sage": {"group":"#F2F0EB", "card":"#DFF3EC", "ink":"#145748", "accent":"#167D69", "muted":"#73736F", "border":"#94BFB1", "line":"#929690", "soft":"#DFF3EC"},
    "tech": {"group":"#F5FBFD", "card":"#FFFFFF", "ink":"#252525", "accent":"#185899", "muted":"#727272", "border":"#D5E8EF", "line":"#3488DA", "soft":"#E4F8FC"},
    "data": {"group":"#FFFFFF", "card":"#E7F5F0", "ink":"#333333", "accent":"#20A080", "muted":"#747474", "border":"#E4E4E4", "line":"#C8C8C8", "contrast":"#A4472A"},
}


def choose_theme(tasks, request):
    """One deterministic document theme; chart overrides must be explicit."""
    text = str(request.get("raw_input", ""))
    return "tech" if any(word in text for word in ("数字", "平台", "AI", "系统")) else (
        "sage" if any(t.get("type") == "business_model" for t in tasks if isinstance(t, dict)) else "tech")


def palette(task):
    return PALETTES["data" if task["type"] == "data_chart" else task.get("theme", "sage")]
ACCENT_GRADIENTS = {"sage": ("#DFF3EC", "#C8E9DD"), "tech": ("#185899", "#3488DA")}
DATA_SERIES = ("#20A080", "#A4472A", "#56778B", "#8A7558")
DATA_PIE = DATA_SERIES + ("#84B5A8", "#D4AE9E", "#B7CCD6", "#D0C2AA")
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def element(tag, attributes=None, **kwargs):
    return ET.Element(f"{{{NS}}}{tag}", {**(attributes or {}), **{k: str(v) for k, v in kwargs.items()}})


def _header(root, title, font, colors):
    """Reserve space above geometry; use a group to avoid nested-SVG unit drift."""
    from .renderers import wrap
    lines = wrap(title, 27)
    header_height = max(40, 28*len(lines)+12)
    vx, vy, w, h = map(float, root.get("viewBox").replace(",", " ").split())
    content_height = h*640/w
    height = header_height + content_height + 36
    outer = element("svg", width=680, height=height, viewBox=f"0 0 680 {height}")
    title_node = element("title")
    title_node.text = title
    outer.append(title_node)
    outer.append(element("rect", width=680, height=height, fill=WHITE))
    outer.append(element("rect", {"data-sw-paint": "main"}, x=20, y=12, width=40,
                         height=3, fill=colors["accent"]))
    # Outline only the added heading: ReportLab cannot map all CJK bold variants.
    # These remain true vector glyphs and are identical under both rasterizers.
    for i, line in enumerate(lines):
        title_path = _text_path(line, font, 340, 16+(header_height-28*len(lines))/2+23+i*28)
        title_path.set("fill", colors["ink"])
        outer.append(title_path)
    root.tag = f"{{{NS}}}g"
    for attr in ("x", "y", "width", "height", "viewBox"):
        root.attrib.pop(attr, None)
    root.attrib.pop("style", None)
    root.set("transform", f"translate(20,{header_height+24}) scale({640/w}) translate({-vx},{-vy})")
    outer.append(root)
    return outer


def _text_path(text, font, center, baseline):
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    from matplotlib.path import Path
    from matplotlib.transforms import Affine2D
    path = TextPath((0, 0), text, size=22, prop=FontProperties(family=font))
    box = path.get_extents()
    path = path.transformed(Affine2D().scale(1, -1).translate(center-(box.x0+box.x1)/2, baseline))
    commands = {Path.MOVETO: "M", Path.LINETO: "L", Path.CURVE3: "Q", Path.CURVE4: "C", Path.CLOSEPOLY: "Z"}
    data = " ".join(commands[code] + (" ".join(f"{v:.4f}" for v in vertices) if code != Path.CLOSEPOLY else "")
                    for vertices, code in path.iter_segments(curves=True, simplify=False))
    return element("path", {"aria-label": text, "data-sw-heading": "true"}, d=data, fill=WHITE)


def apply_theme(path, task, font, mode="solid"):
    root = ET.parse(path).getroot()
    colors = palette(task)
    # Data and Mermaid are intentionally flat; no blanket gradient retrofit.
    controlled = mode == "controlled" and task["type"] != "data_chart" and root.get("class") != "flowchart"
    replacement = {BLUE:colors["accent"], ORANGE:colors["accent"], INK:colors["ink"],
                   GRAY:colors["muted"], PALE:colors["card"], BORDER:colors["border"],
                   "#F7F9FC":colors["group"], "#DDE7F2":colors.get("soft", colors["card"]), "#FCEBE7":colors.get("soft", colors["card"])}
    if task["type"] != "data_chart":
        for node in root.iter():
            for key, value in list(node.attrib.items()):
                for old, new in replacement.items():
                    value = re.sub(re.escape(old), new, value, flags=re.I)
                node.set(key, value)
            if node.tag == f"{{{NS}}}style" and node.text:
                for old, new in replacement.items():
                    node.text = re.sub(re.escape(old), new, node.text, flags=re.I)
    if task["type"] in ("architecture", "business_model"):
        root = _header(root, task["title"], font, colors)
    gradients = {"main": ACCENT_GRADIENTS[task.get("theme", "sage")]}
    # Only explicitly marked model cards/critical nodes, never every process node.
    for node in root.iter():
        name = node.attrib.pop("data-sw-paint", None)
        if name:
            node.set("fill", "url(#sw-main)" if controlled else colors["accent"])
        classes = node.get("class", "").split()
        if "node" in classes and not any(c in classes for c in ("start", "finish", "decision")):
            for shape in node.iter():
                if shape.tag.rsplit("}", 1)[-1] in ("rect", "polygon"):
                    style = re.sub(r"(?:^|;)\s*stroke(?:-width)?\s*:[^;]*", "", shape.get("style", ""))
                    shape.set("style", style+f';stroke:{colors["border"]} !important;stroke-width:0.8px !important')
    used = {name for name in gradients if any(f"url(#sw-{name})" in str(n.attrib) for n in root.iter())}
    if used:
        defs = element("defs")
        for name in sorted(used):
            gradient = element("linearGradient", {"data-sw-solid": colors["accent"], "gradientUnits":"objectBoundingBox"}, id=f"sw-{name}",
                               x1="0%", y1="0%", x2="100%", y2="0%")
            for offset, color in zip(("0%", "100%"), gradients[name]):
                gradient.append(element("stop", {"stop-color": color}, offset=offset))
            defs.append(gradient)
        root.insert(0, defs)
    root.set("data-sw-gradient-mode", "controlled" if used else "solid")
    root.set("data-sw-theme", "data" if task["type"] == "data_chart" else task.get("theme", "sage"))
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def flatten_gradients(path):
    """Persist the SAME solid SVG that will be converted for DOCX; no silent loss."""
    root = ET.parse(path).getroot()
    paints = {n.get("id"): n.get("data-sw-solid") for n in root.iter()
              if n.tag == f"{{{NS}}}linearGradient" and n.get("data-sw-solid")}
    for node in root.iter():
        for key, value in list(node.attrib.items()):
            for name, color in paints.items():
                value = value.replace(f"url(#{name})", color)
            node.set(key, value)
        for child in list(node):
            if child.get("id") in paints:
                node.remove(child)
    root.set("data-sw-gradient-mode", "solid_fallback")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def convert_themed_svg(svg, png, width):
    import svg_to_png
    from PIL import Image
    root = ET.parse(svg).getroot()
    if root.get("data-sw-gradient-mode") != "controlled":
        return ["PNG conversion: " + svg_to_png.convert_svg(svg, png, width)]
    try:
        # svglib can silently drop gradient paints; only Cairo handles this branch.
        svg_to_png.convert_with_cairosvg(svg, png, width)
        with Image.open(png) as image:
            image.verify()
        return ["PNG conversion: cairosvg; controlled gradients preserved"]
    except Exception as exc:
        png.unlink(missing_ok=True)
        flatten_gradients(svg)
        converter = svg_to_png.convert_svg(svg, png, width)
        return [f"gradient fallback to solid: {exc}", "PNG conversion: " + converter]
