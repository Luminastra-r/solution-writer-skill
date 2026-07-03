"""Merge chapters into a single solution markdown document."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from solution_skill.text_utils import normalize_text


def build_solution_markdown(
    blueprint: Dict[str, Any],
    chapters: List[Any],
    chapter_texts: Dict[str, str],
) -> str:
    """Assemble the final markdown from blueprint title + chapter bodies."""
    title = normalize_text(blueprint.get("title", "")) or "解决方案"
    parts: List[str] = [f"# {title}\n"]

    for chapter in chapters:
        body = (chapter_texts.get(chapter.id, "") or "").strip()
        if not body:
            body = f"## {chapter.title}\n\n（本章内容缺失）"
        # Ensure the chapter body starts with a heading
        if not body.lstrip().startswith("#"):
            body = f"## {chapter.title}\n\n{body}"
        parts.append(body.strip() + "\n")

    return "\n".join(parts).strip() + "\n"


def save_solution_markdown(solution_md: str, artifacts_dir: Path) -> Path:
    path = artifacts_dir / "solution.md"
    path.write_text(solution_md, encoding="utf-8")
    return path
