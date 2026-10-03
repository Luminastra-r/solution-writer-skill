"""Best-effort rendering and embedding between merge and export."""
from __future__ import annotations
import json
import time
from pathlib import Path
from .planning import options, validate_task, split_graph, validate_content
from .renderers import render


def render_tasks(tasks, out_dir, request=None, research_pack=None, content_by_chapter=None):
    from PIL import Image
    import xml.etree.ElementTree as ET
    request = request or {}
    cfg = options(request)
    from .theme import choose_theme
    if cfg["theme"] == "auto":
        cfg["theme"] = choose_theme(tasks, request)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    items, seen, count = [], set(), 0
    expanded = []
    for raw in tasks:
        parts = split_graph(raw, cfg)
        if len(parts) > 1 and len(expanded) + len(parts) > cfg["max_diagrams"]:
            raw = dict(raw, planning_error="insufficient budget for all graph parts; entire graph skipped")
            expanded.append(raw)
        else:
            expanded.extend(parts)
    for index, raw in enumerate(expanded):
        d = raw if isinstance(raw, dict) else {}
        item = {"diagram_id": d.get("id", f"invalid_{index}"), "title": d.get("title", ""),
                "type": d.get("type", "flowchart"), "chapter": d.get("chapter", ""),
                "chapter_id": d.get("chapter_id", ""), "section_id": d.get("section_id", ""),
                "anchor_text": d.get("anchor_text", ""), "purpose": d.get("purpose", ""),
                "source": d.get("source", {}), "status": "skipped", "attempts": 0,
                "split_from": d.get("split_from", ""), "split_index": d.get("split_index"),
                "split_total": d.get("split_total"), "split_note": d.get("split_note", ""),
                "image_path": "", "svg_path": "", "mermaid_path": ""}
        items.append(item)
        if not cfg["enabled"] or count >= cfg["max_diagrams"]:
            item["error"] = "disabled or diagram budget exhausted"
            continue
        try:
            d = dict(d)
            if d.get("planning_error"):
                raise ValueError(d["planning_error"])
            d.setdefault("type", "flowchart")
            d = validate_task(d, request, research_pack)
            d.setdefault("theme", cfg["theme"])
            if d["theme"] not in ("sage", "tech"):
                raise ValueError("diagram theme must be sage or tech")
            if content_by_chapter is not None:
                validate_content(d, content_by_chapter.get(d.get("chapter_id") or d.get("chapter"), ""))
            if d["id"] in seen:
                raise ValueError("duplicate diagram id")
            seen.add(d["id"])
            signature = json.dumps({k: d.get(k) for k in ("type", "nodes", "edges", "layers", "dataset_id", "chart", "labels", "series", "x_values")}, sort_keys=True, ensure_ascii=False)
            if signature in seen:
                raise ValueError("duplicate diagram information")
            seen.add(signature)
            item["source"] = d["source"]
        except Exception as exc:
            item["error"] = str(exc)
            continue
        count += 1
        for attempt in range(cfg["retries"]+1):
            item["attempts"] += 1
            try:
                for suffix in ("png", "svg", "mmd"):
                    (out_dir / f"{d['id']}.{suffix}").unlink(missing_ok=True)
                repair = dict(d)
                if attempt and repair["type"] in ("flowchart", "architecture"):
                    repair["layout"] = "TB" if repair.get("layout") == "LR" else "LR"
                engine, svg, png, mmd, notes = render(repair, out_dir, cfg)
                with Image.open(png) as image:
                    image.verify()
                if svg:
                    svg_root = ET.parse(svg).getroot()
                    item["gradient_mode"] = svg_root.get("data-sw-gradient-mode", "solid")
                    item["theme"] = svg_root.get("data-sw-theme", cfg["theme"])
                item.update(status="ok", renderer=engine, image_path=str(png),
                            svg_path=str(svg) if svg else "", mermaid_path=str(mmd), warnings=notes)
                if not svg:
                    item["warnings"].append("renderer did not provide SVG")
                item.pop("error", None)
                break
            except Exception as exc:
                item.update(status="failed", error=str(exc))
        if item["status"] != "ok":
            for suffix in ("png", "svg"):
                (out_dir / f"{d['id']}.{suffix}").unlink(missing_ok=True)
    manifest = {"version": 2, "generated_at": int(time.time()), "options": cfg, "items": items}
    (out_dir / "diagram_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def visualize_solution(markdown, tasks, request, research_pack, artifacts_dir, state_store=None):
    from inject_diagrams import inject_items, GENERATED, locate
    artifacts_dir = Path(artifacts_dir)
    lines = GENERATED.sub("", markdown).splitlines()
    approved, placement_errors = [], []
    for raw in tasks:
        try:
            if not isinstance(raw, dict):
                raise ValueError("task must be an object")
            locate(lines, raw)
            approved.append(raw)
        except Exception as exc:
            placement_errors.append({"diagram_id": raw.get("id", "invalid") if isinstance(raw, dict) else "invalid",
                                     "status": "skipped", "error": str(exc), "insertion_status": "skipped"})
    content_by_chapter = {}
    from inject_diagrams import MARKER
    chapter = ""
    for line in lines:
        match = MARKER.match(line)
        if match and match.group(1) == "chapter":
            chapter = match.group(2)
        if chapter and not line.startswith("<!--"):
            content_by_chapter[chapter] = content_by_chapter.get(chapter, "") + line + "\n"
    manifest = render_tasks(approved, artifacts_dir / "diagrams", request, research_pack, content_by_chapter)
    manifest["items"].extend(placement_errors)
    result = inject_items(markdown, manifest["items"], artifacts_dir / "solution.md")
    path = artifacts_dir / "diagrams" / "diagram_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if state_store:
        state_store.set_output("diagram_manifest", path)
        for item in manifest["items"]:
            if item["status"] != "ok" or item.get("insertion_status") == "skipped":
                state_store.warn(f"diagram {item['diagram_id']}: {item.get('error') or item.get('insertion_error')}")
    return result, manifest
