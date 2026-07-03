#!/usr/bin/env python3
"""
Render business-style diagrams from structured JSON specs.

Pipeline:
1) JSON spec -> Mermaid source (stable template-driven conversion)
2) Mermaid source -> PNG image (mmdc preferred, Kroki optional fallback)
3) Emit manifest for downstream DOCX embedding
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


THEME_PRESETS = {
    "default": {
        "primaryColor": "#E8EEF5",
        "primaryBorderColor": "#1F4E79",
        "primaryTextColor": "#10253E",
        "secondaryColor": "#DDE7F2",
        "tertiaryColor": "#F4F7FB",
        "lineColor": "#6B7785",
        "clusterBkg": "#F7F9FC",
        "clusterBorder": "#A7B6C5",
        "processFill": "#E8EEF5",
        "dataFill": "#F7F3E8",
        "qualityFill": "#E7F1EC",
    },
    "chapter1": {
        "primaryColor": "#E9F0F8",
        "primaryBorderColor": "#2D5F8B",
        "primaryTextColor": "#173049",
        "secondaryColor": "#D8E6F4",
        "tertiaryColor": "#F4F8FC",
        "lineColor": "#60758A",
        "clusterBkg": "#F5F9FD",
        "clusterBorder": "#9CB6CF",
        "processFill": "#E9F0F8",
        "dataFill": "#F8F2E6",
        "qualityFill": "#E6F1EA",
    },
    "chapter2": {
        "primaryColor": "#E8F2EE",
        "primaryBorderColor": "#2F6B55",
        "primaryTextColor": "#153329",
        "secondaryColor": "#DCEDE5",
        "tertiaryColor": "#F5FAF7",
        "lineColor": "#668070",
        "clusterBkg": "#F3FAF6",
        "clusterBorder": "#A4C2B3",
        "processFill": "#E8F2EE",
        "dataFill": "#F5F0E6",
        "qualityFill": "#E3F0EA",
    },
    "chapter3": {
        "primaryColor": "#EEF0F8",
        "primaryBorderColor": "#4A5E8C",
        "primaryTextColor": "#222E4A",
        "secondaryColor": "#E2E6F4",
        "tertiaryColor": "#F7F8FC",
        "lineColor": "#6E7690",
        "clusterBkg": "#F6F7FD",
        "clusterBorder": "#B2B8D1",
        "processFill": "#EEF0F8",
        "dataFill": "#F7F0E8",
        "qualityFill": "#E9F3ED",
    },
}


@dataclass
class RenderResult:
    diagram_id: str
    title: str
    chapter: str
    mermaid_path: str
    image_path: str
    status: str
    svg_path: str = ""
    error: str = ""


def _safe_id(raw: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", raw.strip())
    if not s:
        return "node"
    if re.match(r"^\d", s):
        s = f"n_{s}"
    return s


def _escape_label(text: str) -> str:
    text = (text or "").replace('"', "'").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _node_shape(kind: str, label: str) -> str:
    k = (kind or "process").lower()
    label = _escape_label(label)
    if k == "start":
        return f'(["{label}"])'
    if k == "end":
        return f'(["{label}"])'
    if k == "decision":
        return f'{{"{label}"}}'
    if k == "data":
        return f'[("{label}")]'
    return f'["{label}"]'


def _class_for_kind(kind: str) -> str:
    k = (kind or "process").lower()
    if k in {"start", "end", "decision", "data", "quality"}:
        return k
    return "process"


def _theme_for_key(theme_key: str) -> Dict[str, str]:
    return THEME_PRESETS.get(theme_key, THEME_PRESETS["default"])


def _mermaid_init(theme_key: str) -> str:
    theme = _theme_for_key(theme_key)
    return """%%{init: {"theme": "base", "themeVariables": {
  "fontFamily": "Microsoft YaHei",
  "primaryColor": "%(primaryColor)s",
  "primaryBorderColor": "%(primaryBorderColor)s",
  "primaryTextColor": "%(primaryTextColor)s",
  "secondaryColor": "%(secondaryColor)s",
  "tertiaryColor": "%(tertiaryColor)s",
  "lineColor": "%(lineColor)s",
  "clusterBkg": "%(clusterBkg)s",
  "clusterBorder": "%(clusterBorder)s"
}}}%%""" % theme


def _class_def(theme_key: str) -> str:
    theme = _theme_for_key(theme_key)
    return """
classDef start fill:%(primaryBorderColor)s,stroke:%(primaryBorderColor)s,color:#FFFFFF,stroke-width:1.8px;
classDef end fill:%(primaryBorderColor)s,stroke:%(primaryBorderColor)s,color:#FFFFFF,stroke-width:1.8px;
classDef process fill:%(processFill)s,stroke:%(primaryBorderColor)s,color:%(primaryTextColor)s,stroke-width:1.4px;
classDef decision fill:%(tertiaryColor)s,stroke:%(lineColor)s,color:%(primaryTextColor)s,stroke-width:1.4px;
classDef data fill:%(dataFill)s,stroke:#AF7B2A,color:#4B3520,stroke-width:1.4px;
classDef quality fill:%(qualityFill)s,stroke:#2F7D57,color:#1D4A34,stroke-width:1.4px;
classDef legend fill:#FFFFFF,stroke:%(clusterBorder)s,color:%(primaryTextColor)s,stroke-dasharray: 4 2;
""" % theme


def _normalize_diagram(diagram: Dict) -> Dict:
    normalized = dict(diagram)
    nodes = list(normalized.get("nodes", []))[:14]
    node_ids = {str(node.get("id", "")) for node in nodes}
    normalized["nodes"] = nodes
    normalized["edges"] = [
        edge
        for edge in normalized.get("edges", [])
        if str(edge.get("from", "")) in node_ids and str(edge.get("to", "")) in node_ids
    ][:20]
    groups = []
    for group in normalized.get("groups", []):
        members = [str(node_id) for node_id in group.get("node_ids", []) if str(node_id) in node_ids]
        if members:
            groups.append({"id": group.get("id"), "title": group.get("title"), "node_ids": members})
    normalized["groups"] = groups
    legend = normalized.get("legend") or []
    normalized["legend"] = [str(item).strip() for item in legend[:5] if str(item).strip()]
    normalized["theme_key"] = str(normalized.get("theme_key", "default")).strip() or "default"
    return normalized


def build_mermaid(diagram: Dict) -> str:
    diagram = _normalize_diagram(diagram)
    layout = diagram.get("layout", "TB")
    nodes = diagram.get("nodes", [])
    edges = diagram.get("edges", [])
    groups = diagram.get("groups", [])
    theme_key = diagram.get("theme_key", "default")

    lines = [_mermaid_init(theme_key), f"flowchart {layout}"]
    class_lines: List[str] = []

    # Keep stable mapping for group checks and edge checks.
    node_map: Dict[str, Dict] = {}
    for n in nodes:
        raw_id = str(n.get("id", ""))
        node_map[raw_id] = n

    grouped = set()
    for g in groups:
        gid = _safe_id(str(g.get("id", "group")))
        gtitle = _escape_label(str(g.get("title", gid)))
        lines.append(f'  subgraph {gid}["{gtitle}"]')
        for nid in g.get("node_ids", []):
            nid_raw = str(nid)
            node = node_map.get(nid_raw)
            if not node:
                continue
            sid = _safe_id(nid_raw)
            lines.append(f'    {sid}{_node_shape(node.get("kind", "process"), node.get("label", sid))}')
            class_lines.append(f"  class {sid} {_class_for_kind(node.get('kind', 'process'))};")
            grouped.add(nid_raw)
        lines.append("  end")

    # Emit ungrouped nodes.
    for raw_id, node in node_map.items():
        if raw_id in grouped:
            continue
        sid = _safe_id(raw_id)
        lines.append(f'  {sid}{_node_shape(node.get("kind", "process"), node.get("label", sid))}')
        class_lines.append(f"  class {sid} {_class_for_kind(node.get('kind', 'process'))};")

    # Edges.
    for e in edges:
        src = _safe_id(str(e.get("from", "")))
        dst = _safe_id(str(e.get("to", "")))
        if not src or not dst:
            continue
        label = _escape_label(str(e.get("label", "")))
        style = str(e.get("style", "solid")).lower()
        arrow = "-.->" if style == "dashed" else "-->"
        if label:
            lines.append(f'  {src} {arrow}|"{label}"| {dst}')
        else:
            lines.append(f"  {src} {arrow} {dst}")

    legend_items = diagram.get("legend", [])
    if legend_items:
        lines.append('  subgraph legend_block["图例"]')
        for index, item in enumerate(legend_items, start=1):
            legend_id = f"legend_{index}"
            lines.append(f'    {legend_id}["{_escape_label(item)}"]')
            class_lines.append(f"  class {legend_id} legend;")
        lines.append("  end")

    lines.append(_class_def(theme_key).strip())
    lines.extend(class_lines)
    return "\n".join(lines) + "\n"


def _render_with_mmdc(
    mermaid_path: Path,
    output_path: Path,
    mmdc_bin: str,
    scale: float,
    timeout: int,
) -> Tuple[bool, str]:
    cmd = [
        mmdc_bin,
        "-i",
        str(mermaid_path),
        "-o",
        str(output_path),
        "-b",
        "transparent",
        "-s",
        str(scale),
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
        if p.stderr.strip():
            return True, p.stderr.strip()
        return True, ""
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or e.stdout or str(e)).strip()
    except Exception as e:
        return False, str(e)


def _render_with_kroki(mermaid_src: str, image_path: Path, kroki_url: str, timeout: int) -> Tuple[bool, str]:
    url = kroki_url.rstrip("/") + "/mermaid/png"
    try:
        r = requests.post(url, data=mermaid_src.encode("utf-8"), headers={"Content-Type": "text/plain"}, timeout=timeout)
        if r.status_code != 200:
            return False, f"Kroki HTTP {r.status_code}: {r.text[:200]}"
        image_path.write_bytes(r.content)
        return True, ""
    except Exception as e:
        return False, str(e)


def _try_render(
    mermaid_src: str,
    mermaid_path: Path,
    image_path: Path,
    svg_path: Optional[Path],
    engine: str,
    mmdc_bin: str,
    kroki_url: Optional[str],
    retries: int,
    backoff_seconds: float,
    scale: float,
    timeout: int,
) -> Tuple[bool, str]:
    mermaid_path.write_text(mermaid_src, encoding="utf-8")
    last_error = ""

    for i in range(retries + 1):
        if engine == "mmdc":
            ok, err = _render_with_mmdc(mermaid_path, image_path, mmdc_bin, scale, timeout)
            if ok and svg_path is not None:
                ok_svg, err_svg = _render_with_mmdc(mermaid_path, svg_path, mmdc_bin, scale, timeout)
                if not ok_svg:
                    err = err_svg
        elif engine == "kroki":
            if not kroki_url:
                ok, err = False, "Kroki URL is required when engine=kroki."
            else:
                ok, err = _render_with_kroki(mermaid_src, image_path, kroki_url, timeout)
        else:
            ok, err = False, f"Unsupported engine: {engine}"

        if ok:
            return True, err

        last_error = err
        if i < retries:
            time.sleep(backoff_seconds * (2 ** i))

    return False, last_error


def _load_specs(path: Path) -> List[Dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("diagrams"), list):
        return payload["diagrams"]
    raise ValueError("Invalid spec JSON. Expected list or {'diagrams': [...]} format.")


def _ensure_mmdc(engine: str, provided_bin: Optional[str]) -> str:
    if engine != "mmdc":
        return provided_bin or "mmdc"
    if provided_bin:
        return provided_bin
    found = shutil.which("mmdc")
    if not found:
        raise FileNotFoundError("mmdc not found. Install mermaid-cli or pass --engine kroki.")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Render diagrams from structured JSON specs.")
    parser.add_argument("--spec-json", required=True, help="Path to JSON specs.")
    parser.add_argument("--out-dir", required=True, help="Output directory for .mmd/.png/.json.")
    parser.add_argument("--engine", choices=["mmdc", "kroki"], default="mmdc", help="Rendering engine.")
    parser.add_argument("--mmdc-bin", help="Path to mmdc binary.")
    parser.add_argument("--kroki-url", help="Kroki base URL, e.g. https://kroki.io")
    parser.add_argument("--retries", type=int, default=2, help="Retries on render failure.")
    parser.add_argument("--backoff-seconds", type=float, default=1.0, help="Base seconds for exponential backoff.")
    parser.add_argument("--scale", type=float, default=2.0, help="Render scale for mmdc.")
    parser.add_argument("--timeout", type=int, default=60, help="Per-render timeout (seconds).")
    parser.add_argument("--chapter-filter", help="Comma-separated chapter values, e.g. chapter1,chapter2,chapter3")
    parser.add_argument("--export-svg", action="store_true", help="Export an SVG copy alongside PNG.")
    args = parser.parse_args()

    spec_path = Path(args.spec_json)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        specs = _load_specs(spec_path)
    except Exception as e:
        print(f"Failed to load spec JSON: {e}")
        return 1

    chapter_allow = None
    if args.chapter_filter:
        chapter_allow = {x.strip() for x in args.chapter_filter.split(",") if x.strip()}

    try:
        mmdc_bin = _ensure_mmdc(args.engine, args.mmdc_bin)
    except Exception as e:
        print(str(e))
        return 1

    results: List[RenderResult] = []
    for idx, d in enumerate(specs, start=1):
        chapter = str(d.get("chapter", "")).strip()
        if chapter_allow is not None and chapter not in chapter_allow:
            continue

        did = str(d.get("id", f"diagram_{idx}")).strip() or f"diagram_{idx}"
        title = str(d.get("title", did)).strip()
        safe = _safe_id(did).lower()
        mermaid_path = out_dir / f"{safe}.mmd"
        image_path = out_dir / f"{safe}.png"
        svg_path = out_dir / f"{safe}.svg"

        try:
            mermaid_src = build_mermaid(d)
            ok, msg = _try_render(
                mermaid_src=mermaid_src,
                mermaid_path=mermaid_path,
                image_path=image_path,
                svg_path=svg_path if args.export_svg else None,
                engine=args.engine,
                mmdc_bin=mmdc_bin,
                kroki_url=args.kroki_url,
                retries=max(0, args.retries),
                backoff_seconds=max(0.1, args.backoff_seconds),
                scale=max(1.0, args.scale),
                timeout=max(5, args.timeout),
            )
            if ok:
                results.append(
                    RenderResult(
                        diagram_id=did,
                        title=title,
                        chapter=chapter,
                        mermaid_path=str(mermaid_path.resolve()),
                        image_path=str(image_path.resolve()),
                        svg_path=str(svg_path.resolve()) if args.export_svg and svg_path.exists() else "",
                        status="ok",
                        error=msg,
                    )
                )
            else:
                results.append(
                    RenderResult(
                        diagram_id=did,
                        title=title,
                        chapter=chapter,
                        mermaid_path=str(mermaid_path.resolve()),
                        image_path=str(image_path.resolve()),
                        svg_path=str(svg_path.resolve()) if args.export_svg and svg_path.exists() else "",
                        status="failed",
                        error=msg,
                    )
                )
        except Exception as e:
            results.append(
                RenderResult(
                    diagram_id=did,
                    title=title,
                    chapter=chapter,
                    mermaid_path=str(mermaid_path.resolve()),
                    image_path=str(image_path.resolve()),
                    svg_path=str(svg_path.resolve()) if args.export_svg and svg_path.exists() else "",
                    status="failed",
                    error=str(e),
                )
            )

    manifest = {
        "generated_at": int(time.time()),
        "engine": args.engine,
        "items": [r.__dict__ for r in results],
    }
    manifest_path = out_dir / "diagram_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [x for x in results if x.status != "ok"]
    print(f"Rendered {len(results) - len(failed)}/{len(results)} diagrams. Manifest: {manifest_path}")
    if failed:
        for item in failed:
            print(f"[FAILED] {item.diagram_id}: {item.error}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
