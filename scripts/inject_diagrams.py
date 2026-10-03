#!/usr/bin/env python3
"""Idempotent anchored injection; legacy CLI/chapter keys supported."""
import argparse
import json
import re
import sys
from pathlib import Path

CHAPTER_HEADING_PATTERNS = {
    "chapter1": r"^##\s*一[、\.]\s*需求理解",
    "chapter2": r"^##\s*二[、\.]\s*实施策略",
    "chapter3": r"^##\s*三[、\.]\s*运营方案",
}
MARKER = re.compile(r"^<!-- solution-(chapter|section):([^\s<>]+) -->$")
GENERATED = re.compile(r"<!-- solution-figure:[^\n]+ -->\n.*?<!-- /solution-figure -->\n?", re.S)


def _load_manifest(path):
    items = json.loads(path.read_text(encoding="utf-8-sig")).get("items", [])
    if not isinstance(items, list):
        raise ValueError("manifest items must be a list")
    return items


def _pick_diagrams(items):
    picked = {}
    for item in items:
        if item.get("status") == "ok":
            picked.setdefault(item.get("chapter_id") or item.get("chapter", ""), []).append(item)
    return picked


def locate(lines, item):
    chapter = item.get("chapter_id") or item.get("chapter", "")
    section = item.get("section_id", "")
    kind, target = ("section", section) if section else ("chapter", chapter)
    markers = [(i, m.group(1), m.group(2)) for i, line in enumerate(lines) if (m := MARKER.match(line))]
    starts = [i for i, k, value in markers if k == kind and value == target]
    if len(starts) == 1:
        start = starts[0]
        end = next((i for i, k, _ in markers if i > start and (kind == "section" or k == "chapter")), len(lines))
    elif not starts and not section and chapter in CHAPTER_HEADING_PATTERNS:
        starts = [i for i, line in enumerate(lines) if re.search(CHAPTER_HEADING_PATTERNS[chapter], line)]
        if len(starts) != 1:
            raise ValueError("legacy chapter heading missing/ambiguous")
        start = starts[0]
        end = next((i for i in range(start+1, len(lines)) if lines[i].startswith("## ")), len(lines))
    else:
        raise ValueError("stable chapter/section anchor missing/ambiguous")
    if section and chapter:
        parent = next((value for i, k, value in reversed(markers) if i < start and k == "chapter"), "")
        if parent != chapter:
            raise ValueError("section belongs to a different chapter")
    anchor = item.get("anchor_text", "").strip()
    if anchor:
        matches = [i for i in range(start+1, end) if anchor in lines[i] and not lines[i].startswith(("#", "<!--", "|", "!["))]
        if len(matches) != 1:
            raise ValueError("content anchor missing/ambiguous in target section")
        return matches[0]+1
    while end > start+1 and not lines[end-1].strip():
        end -= 1
    return end


def _build_image_block(item, md_dir):
    path = Path(item["image_path"])
    if not path.is_absolute():
        path = md_dir / path
    if not path.is_file():
        raise ValueError("rendered image missing")
    try:
        path = path.resolve().relative_to(md_dir.resolve())
    except ValueError:
        path = path.resolve()
    title = re.sub(r"[\r\n\[\]]", " ", item.get("title", "逻辑图"))
    block = [f"<!-- solution-figure:{item['diagram_id']} -->", f"![{title}]({path.as_posix()})"]
    source = item.get("source") or {}
    if source.get("reference"):
        names = {"verified": "已核实资料", "user_provided": "用户提供", "assumed": "假设数据（非实际成效）", "proposal": "方案设计"}
        label = names.get(source.get("kind"), "资料") + "；" + str(source["reference"])
        if item.get("split_note"):
            label += "；" + item["split_note"]
        block.append("<!-- solution-source:" + json.dumps(label, ensure_ascii=False).replace("-->", "--\\u003e") + " -->")
    block.extend(["<!-- /solution-figure -->", ""])
    return block


def inject_items(markdown, items, md_path):
    lines = GENERATED.sub("", markdown).splitlines()
    inserts, seen = {}, set()
    for item in items:
        if item.get("status") != "ok":
            continue
        try:
            if item["diagram_id"] in seen:
                raise ValueError("duplicate diagram id")
            seen.add(item["diagram_id"])
            at = locate(lines, item)
            block = _build_image_block(item, md_path.parent)
            inserts.setdefault(at, []).extend([""] + block)
            item["insertion_status"] = "inserted"
            item["insertion_position"] = at
        except (ValueError, KeyError, TypeError) as exc:
            item["insertion_status"] = "skipped"
            item["insertion_error"] = str(exc)
    for at in sorted(inserts, reverse=True):
        lines[at:at] = inserts[at]
    return "\n".join(lines).rstrip() + "\n"


def inject(markdown, chapter_images, md_path):
    items = []
    for value in chapter_images.values():
        items.extend(value if isinstance(value, list) else [value])
    return inject_items(markdown, items, md_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-md", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    try:
        out = Path(args.output_md)
        manifest_path = Path(args.manifest)
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        items = _load_manifest(manifest_path)
        markdown = Path(args.input_md).read_text(encoding="utf-8-sig")
        for item in items:
            if item.get("image_path") and not Path(item["image_path"]).is_absolute():
                item["image_path"] = str((Path(args.input_md).parent / item["image_path"]).resolve())
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(inject_items(markdown, items, out), encoding="utf-8")
        payload["items"] = items
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Inserted {sum(i.get('insertion_status') == 'inserted' for i in items)} figures: {out}")
        return 0
    except Exception as exc:
        print(f"Inject failed: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
