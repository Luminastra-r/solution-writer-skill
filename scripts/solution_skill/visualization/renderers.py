"""Controlled renderers reusing Mermaid and SVG conversion entry points."""
from __future__ import annotations

import html
import shutil
import warnings
from pathlib import Path

from .theme import BLUE, ORANGE, INK, GRAY, FONT, PALE, BORDER, apply_theme, convert_themed_svg, palette, DATA_SERIES, DATA_PIE


def cjk_font(text):
    """Select an installed CJK font and fail instead of producing missing glyphs."""
    from matplotlib import font_manager, ft2font
    for name in ("Microsoft YaHei", "Noto Sans CJK SC", "Noto Serif SC", "SimHei", "PingFang SC"):
        try:
            path = font_manager.findfont(name, fallback_to_default=False)
            cmap = ft2font.FT2Font(path).get_charmap()
            if all(ord(c) in cmap for c in text if not c.isspace()):
                return path
        except (ValueError, RuntimeError):
            continue
    raise RuntimeError("no installed CJK font covers the diagram text")


def wrap(text, width=12):
    """Deterministic line wrapping including Chinese (full-width glyphs)."""
    lines, line, size = [], "", 0
    for c in str(text):
        units = 1 if ord(c) > 255 else 0.55
        if c == "\n" or size + units > width:
            lines.append(line)
            line, size = "", 0
        if c != "\n":
            line += c
            size += units
    if line:
        lines.append(line)
    return lines or [""]


def _text(x, y, text, width=12, size=15, color=INK):
    lines = wrap(text, width)
    start = y - (len(lines) - 1) * size * 0.7
    return "".join(f'<text x="{x}" y="{start+i*size*1.4}" text-anchor="middle" '
                   f'font-family="{FONT}" font-size="{size}" fill="{color}" '
                   f'dominant-baseline="central">{html.escape(t)}</text>' for i, t in enumerate(lines))


def _svg(title, desc, height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="680" height="{height}" viewBox="0 0 680 {height}">'
            f'<title>{html.escape(title)}</title><desc>{html.escape(desc)}</desc>'
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{BLUE}"/></marker></defs>'
            f'<rect width="680" height="{height}" fill="white"/>{body}</svg>')


def model_svg(d):
    colors = palette(d)
    y, body = 8, []
    for layer in d["layers"]:
        items = layer["items"]
        columns = min(2, len(items))
        width = (460-(columns-1)*18)/columns
        card_h = max(64, max(len(wrap(t, (width-28)/16)) for t in items)*24+24)
        rows = (len(items)+columns-1)//columns
        header_h = max(0, len(wrap(layer["title"], 7))*24+16)
        height = max(header_h, rows*card_h+(rows-1)*16)+32
        body.append(f'<rect x="16" y="{y}" width="648" height="{height}" rx="10" fill="{colors["group"]}"/>')
        body.append(_text(88, y+height/2, layer["title"], width=7, size=18, color=colors["ink"]))
        for i, item in enumerate(items):
            x, cy = 184+(i%columns)*(width+18), y+16+(i//columns)*(card_h+16)
            body.append(f'<rect x="{x}" y="{cy}" width="{width}" height="{card_h}" rx="7" fill="{colors["card"]}" stroke="{colors["border"]}" stroke-width="0.8"/>')
            if d.get("theme") == "tech":
                body.append(f'<path d="M{x+12},{cy+1} H{x+width-12}" stroke="{colors["accent"]}" stroke-width="2"/>')
            body.append(_text(x+width/2,cy+card_h/2,item,width=(width-28)/16,size=16,color=colors["ink"]))
        y += height+18
    return _svg(d["title"], d.get("purpose", "业务分层模型"), y, "".join(body))


def graph_svg(d):
    """Offline fallback for sparse graphs. Never discards edges or changes semantics.

    Nodes sit in separate rows; directed edges use exterior lanes so they cannot
    run through nodes. Dense graphs require Mermaid rather than unreadable fallback.
    """
    nodes, edges = d["nodes"], d.get("edges", [])
    if len(nodes) > 10 or len(edges) > 12 or d.get("groups"):
        raise ValueError("SVG fallback supports <=10 nodes/12 edges without groups; install mmdc or split graph")
    if not edges and d["type"] == "architecture":
        colors, body = palette(d), []
        columns = min(2, len(nodes))
        w = (624-24*(columns-1))/columns
        h = max(80, max(len(wrap(n["label"], (w-32)/17)) for n in nodes)*25+40)
        for i, node in enumerate(nodes):
            x, y = 28+(i%columns)*(w+24), 16+(i//columns)*(h+22)
            body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{colors["card"]}" stroke="{colors["border"]}" stroke-width="0.8"/>')
            body.append(f'<path d="M{x+12},{y+1} H{x+w-12}" stroke="{colors["accent"]}" stroke-width="2"/>')
            body.append(_text(x+w/2,y+h/2,node["label"],width=(w-32)/17,size=17,color=colors["ink"]))
        return _svg(d["title"],d.get("purpose","能力模块，无依赖关系"),y+h+16,"".join(body))
    layout = d.get("layout", "auto")
    horizontal = layout in ("LR", "RL") or (layout == "auto" and len(nodes) <= 4)
    if horizontal and len(nodes) > 4:
        horizontal = False  # readable Word width
    positions, boxes, body = {}, {}, []
    if horizontal:
        step = 640 / len(nodes)
        max_rows = max(len(wrap(n["label"], (step-24)/15 * (0.6 if n.get("kind") == "decision" else 1))) for n in nodes)
        h = max(70, max_rows*22+28)
        order = list(reversed(nodes)) if layout == "RL" else nodes
        for i, n in enumerate(order):
            boxes[n["id"]] = (20+i*step, 32, step-18, h)
        height = h + 100 + 32*len(edges)
    else:
        y = 20
        order = list(reversed(nodes)) if layout == "BT" else nodes
        for n in order:
            h = max(64, len(wrap(n["label"], 12 if n.get("kind") == "decision" else 22))*22+36)
            boxes[n["id"]] = (170, y, 340, h)
            y += h+36
        height = y+20
    for nid, (x, y, w, h) in boxes.items():
        positions[nid] = (x+w/2, y+h/2)
    if horizontal:
        routed = sum(bool(e.get("label")) or abs(boxes[e["from"]][0]-boxes[e["to"]][0]) > (boxes[e["from"]][2]+18)*1.01 for e in edges)
        height = max(y+h for _, y, _, h in boxes.values())+36+32*routed
    # Paths first, nodes second. Edge lanes are separated and label width bounded.
    routed_index = 0
    for i, e in enumerate(edges):
        x1, y1, w1, h1 = boxes[e["from"]]
        x2, y2, w2, h2 = boxes[e["to"]]
        if horizontal and not e.get("label") and abs(x1-x2) <= (w1+18)*1.01:
            start, end = (x1+w1, x2-3) if x2 > x1 else (x1, x2+w2+3)
            path = f'M{start},{y1+h1/2} H{end}'
            tip, direction = (end, y1+h1/2), (1 if x2 > x1 else -1, 0)
        elif not horizontal and not e.get("label") and (abs(y1+h1+36-y2) < 1 or abs(y2+h2+36-y1) < 1):
            start, end = (y1+h1, y2-3) if y2 > y1 else (y1, y2+h2+3)
            path = f'M{x1+w1/2},{start} V{end}'
            tip, direction = (x1+w1/2, end), (0, 1 if y2 > y1 else -1)
        elif horizontal:
            lane = max(y1+h1, y2+h2)+30+32*routed_index
            routed_index += 1
            path = f'M{x1+w1/2},{y1+h1} V{lane} H{x2+w2/2} V{y2+h2+3}'
            tx, ty = (x1+x2+w1/2+w2/2)/2, lane-10
            tip, direction = (x2+w2/2, y2+h2+3), (0, -1)
        else:
            # Alternate sides with exterior edge labels; no node intersections.
            right = i % 2 == 0
            lane = 540+18*(i//2) if right else 140-18*(i//2)
            a, b = (x1+w1, x2+w2+3) if right else (x1, x2-3)
            path = f'M{a},{y1+h1/2} H{lane} V{y2+h2/2} H{b}'
            tx, ty = (605 if right else 75), (y1+h1/2+y2+h2/2)/2
            tip, direction = (b, y2+h2/2), (-1 if right else 1, 0)
        dash = ' stroke-dasharray="5 4"' if e.get("style") == "dashed" else ""
        body.append(f'<path d="{path}" fill="none" stroke="{BLUE}" stroke-width="1.5"{dash}/>')
        # Explicit arrow polygons preserve direction under svglib as well as CairoSVG.
        px, py = tip
        dx, dy = direction
        body.append(f'<polygon points="{px},{py} {px-8*dx+4*dy},{py-8*dy-4*dx} {px-8*dx-4*dy},{py-8*dy+4*dx}" fill="{BLUE}"/>')
        if e.get("label"):
            if len(wrap(e["label"], 8)) > 2:
                raise ValueError("edge label too long for SVG fallback; use Mermaid")
            body.append(_text(tx, ty, e["label"], width=8, size=12, color=GRAY))
    for n in nodes:
        x, y, w, h = boxes[n["id"]]
        fill = BLUE if n.get("kind") in ("start", "end") else PALE
        accent = ""
        if n.get("kind") == "decision":
            body.append(f'<polygon points="{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}" fill="{fill}" stroke="{BLUE}"/>')
        else:
            body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"{accent} fill="{fill}" stroke="{BORDER}" stroke-width="0.8"/>')
        body.append(_text(x+w/2, y+h/2, n["label"], width=(w-24)/15*(0.6 if n.get("kind") == "decision" else 1),
                          color="#FFFFFF" if fill == BLUE else INK))
    return _svg(d["title"], d.get("purpose", "节点及关系"), height, "".join(body))


def data_chart(d, svg, png, width):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt, font_manager
    font = cjk_font("".join(d["labels"]) + d.get("unit", "") + "".join(s.get("name", "") for s in d["series"]))
    font_name = font_manager.FontProperties(fname=font).get_name()
    colors = palette(d)
    style = {"font.family": font_name, "font.size": 12, "axes.unicode_minus": False,
             "axes.prop_cycle": matplotlib.cycler(color=DATA_SERIES),
             "svg.fonttype": "path", "text.color": colors["ink"], "axes.labelcolor": colors["muted"],
             "axes.edgecolor": colors["line"], "axes.linewidth": 0.7, "xtick.color": colors["muted"], "ytick.color": colors["ink"]}
    with plt.rc_context(style), warnings.catch_warnings():
        warnings.filterwarnings("error", message="Glyph .* missing from font")
        fig, ax = plt.subplots(figsize=(7, max(3.6, min(10, len(d["labels"])*len(d["series"])*0.4+1.2))), layout="constrained")
        try:
            chart = d.get("chart", "bar")
            labels = ["\n".join(wrap(t, 8)) for t in d["labels"]]
            series = d["series"]
            x = list(range(len(labels)))
            if chart == "pie":
                ax.pie(series[0]["values"], labels=labels, autopct="%1.1f%%",
                       colors=DATA_PIE)
            elif chart == "bar":
                bar_width = 0.8 / len(series)
                for i, s in enumerate(series):
                    bars = ax.barh([v+(i-(len(series)-1)/2)*bar_width for v in x], s["values"],
                                   height=bar_width*0.76, label=s.get("name", ""), hatch=["", "//", "..", "xx"][i], linewidth=0.5, edgecolor="white")
                    if i == 0:
                        for index, bar in enumerate(bars):
                            bar.set_gid(f"sw-primary-bar-{index}")
                    ax.bar_label(bars, labels=[f"{value:,.6g}" for value in s["values"]], padding=4, fontsize=11)
                ax.margins(x=0.15)
                ax.set_yticks(x, labels)
                ax.invert_yaxis()
                ax.set_xlabel(d.get("unit", ""))
            elif chart == "line":
                for i, s in enumerate(series):
                    line, = ax.plot(x, s["values"], marker=["o","s","^","D"][i], linestyle=["-","--","-.",":"][i], linewidth=2, markersize=6, label=s.get("name", ""))
                    line.set_gid(f"sw-series-{i}")
                    if i == 0:
                        ax.fill_between(x, s["values"], 0, color=colors["card"], zorder=0)
                    for px, value in zip(x, s["values"]):
                        if len(x) <= 6:
                            ax.annotate(f"{value:,.6g}", (px,value), xytext=(0,9 if i%2 == 0 else -17), textcoords="offset points", ha="center", fontsize=11, color=colors["muted"])
                low = min(0, min(v for s in series for v in s["values"]))
                high = max(0, max(v for s in series for v in s["values"]))
                pad = (high-low or 1)*0.12
                ax.set_ylim(low-pad if low < 0 else 0, high+pad)
                ax.margins(x=0.14)
                ax.set_xticks(x, labels)
                ax.set_ylabel(d.get("unit", ""))
            else:
                for i, s in enumerate(series):
                    ax.scatter(d["x_values"], s["values"], marker=["o","s","^","D"][i], label=s.get("name", ""))
                if d.get("numeric_x"):
                    ax.set_xlabel(d.get("x_label", ""))
                else:
                    ax.set_xticks(d["x_values"], labels)
                ax.set_ylabel(d.get("unit", ""))
            if chart != "pie":
                ax.spines[["top", "right"]].set_visible(False)
                ax.grid(axis="x" if chart == "bar" else "y", color=colors["border"], linewidth=0.7)
                ax.tick_params(length=0, pad=8)
                from matplotlib.ticker import FuncFormatter
                (ax.xaxis if chart == "bar" else ax.yaxis).set_major_formatter(FuncFormatter(lambda value, pos: f"{value:,.6g}"))
                ax.set_axisbelow(True)
                if len(series) > 1:
                    ax.legend(loc="upper left", bbox_to_anchor=(0, 1.22), ncol=min(2,len(series)), frameon=False, borderaxespad=0, handlelength=2.6)
            fig.savefig(svg, format="svg")
            fig.savefig(png, dpi=width/7, facecolor="white")
        finally:
            plt.close(fig)


def render(d, out_dir, cfg):
    """Returns renderer, paths, and warnings. Both formats are default outputs."""
    from render_diagrams import build_mermaid, _try_render
    svg, png, mmd = [out_dir / f"{d['id']}.{suffix}" for suffix in ("svg", "png", "mmd")]
    notes = []
    if d["type"] in ("flowchart", "architecture"):
        texts = [str(n["label"]) for n in d["nodes"]] + [str(e.get("label", "")) for e in d.get("edges", [])]
    elif d["type"] == "business_model":
        texts = [str(t) for l in d["layers"] for t in [l["title"], *l["items"]]]
    else:
        texts = d["labels"]
    font_path = cjk_font(d["title"] + "".join(texts))
    from matplotlib import font_manager
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    notes.append("CJK font: " + str(font_path))
    if d["type"] == "data_chart":
        data_chart(d, svg, png, cfg["png_width"])
        apply_theme(svg, d, font_name, cfg.get("gradient_mode", "solid"))
        if d.get("chart", "bar") == "bar":
            notes.extend(convert_themed_svg(svg, png, cfg["png_width"]))
        return "matplotlib", svg, png, "", notes
    if d["type"] in ("flowchart", "architecture"):
        graph = dict(d)
        graph["theme_key"] = "solution"  # DOCX palette; retain legacy standalone themes
        src = build_mermaid(graph)
        src = src.replace("Noto Serif SC, Microsoft YaHei, sans-serif", font_name)
        mmd.write_text(src, encoding="utf-8")
        engine = cfg["engine"]
        mmdc = cfg.get("mmdc_bin") or shutil.which("mmdc")
        if engine in ("mmdc", "kroki") or (engine == "auto" and mmdc):
            use = "kroki" if engine == "kroki" else "mmdc"
            ok, err = _try_render(src, mmd, png, svg, use, mmdc or "mmdc",
                                  cfg.get("kroki_url"), 0, 0.1, cfg.get("scale", 3), cfg["timeout"])
            if ok:
                apply_theme(svg, d, font_name, cfg.get("gradient_mode", "solid"))
                notes.extend(convert_themed_svg(svg, png, cfg["png_width"]))
                if err:
                    notes.append(err)
                return use, svg, png, mmd, notes
            if engine != "auto":
                raise RuntimeError(err)
            notes.append("Mermaid failed; local SVG fallback: " + err)
        svg.write_text(graph_svg(d).replace(FONT, font_name), encoding="utf-8")
        renderer = "svg_graph"
    else:
        svg.write_text(model_svg(d).replace(FONT, font_name), encoding="utf-8")
        renderer = "svg_template"
    apply_theme(svg, d, font_name, cfg.get("gradient_mode", "solid"))
    notes.extend(convert_themed_svg(svg, png, cfg["png_width"]))
    return renderer, svg, png, mmd if mmd.exists() else "", notes
