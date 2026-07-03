"""Text processing utilities extracted from orchestrate_solution.py."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List

from solution_skill.config import (
    HEADING_RE,
    META_LINE_PATTERNS,
    REASONING_BLOCK_RE,
    FENCE_RE,
)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "；".join(normalize_text(item) for item in value if normalize_text(item))
    if isinstance(value, dict):
        parts: List[str] = []
        for key, item in value.items():
            item_text = normalize_text(item)
            if item_text:
                parts.append(f"{key}：{item_text}")
        return "；".join(parts)
    return str(value).strip()


def slugify(text: str) -> str:
    compact = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", normalize_text(text))
    return compact.strip("_") or "item"


def shorten(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", normalize_text(text))
    return compact if len(compact) <= max_chars else compact[: max_chars - 1] + "…"


def strip_trigger_prefix(raw_input: str) -> str:
    return re.sub(r"^\s*/?写解决方案\s*", "", normalize_text(raw_input)).strip()


def request_title(raw_input: str) -> str:
    plain = strip_trigger_prefix(raw_input)
    compact = re.sub(r"\s+", " ", plain)
    return compact[:32].strip() or "解决方案"


def remove_reasoning(text: str) -> str:
    cleaned = normalize_text(text).replace("\r\n", "\n").replace("\r", "\n")
    cleaned = REASONING_BLOCK_RE.sub("", cleaned)
    fenced = FENCE_RE.match(cleaned.strip())
    if fenced:
        cleaned = fenced.group(1)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def clean_chapter_body(text: str, chapter_title: str) -> str:
    """Clean chapter body: remove reasoning, meta lines, duplicate chapter heading."""
    cleaned = remove_reasoning(text)
    lines = [line.rstrip() for line in cleaned.splitlines()]
    # Strip leading blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    # Strip meta prefix lines
    while lines and any(pattern.match(lines[0]) for pattern in META_LINE_PATTERNS):
        lines.pop(0)
    # Strip duplicate chapter-level heading (## level)
    while lines and HEADING_RE.match(lines[0]):
        current = re.sub(r"^\s*#{1,6}\s+", "", lines[0]).strip()
        if chapter_title and chapter_title in current:
            lines.pop(0)
            continue
        break
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines).strip())
    return result + "\n" if result else ""


def clean_plain_text(text: str) -> str:
    cleaned = remove_reasoning(text)
    cleaned = re.sub(r"^\s*#{1,6}\s+", "", cleaned, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def load_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""


def extract_keywords(text: str) -> List[str]:
    lowered = normalize_text(text).lower()
    terms = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{3,}", lowered)
    seen: List[str] = []
    for term in terms:
        if term not in seen:
            seen.append(term)
    return seen[:24]


def score_text_match(text: str, keywords: List[str]) -> int:
    lowered = normalize_text(text).lower()
    score = 0
    for keyword in keywords:
        if keyword and keyword in lowered:
            score += min(3, lowered.count(keyword))
    return score
