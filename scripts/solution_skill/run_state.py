"""Run state tracking with checkpoint support."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RunState:
    status: str = "initialized"
    current_step: str = "bootstrap"
    run_mode: str = "standard"
    current_section: str = ""
    completed_sections: List[str] = field(default_factory=list)
    completed_chapters: List[str] = field(default_factory=list)
    failed_sections: List[str] = field(default_factory=list)
    diagram_status: str = "removed"
    docx_status: str = "pending"
    quality_status: str = "pending"
    llm_call_count: int = 0
    warnings: List[str] = field(default_factory=list)
    output_files: Dict[str, str] = field(default_factory=dict)
    error: str = ""
    last_token_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class RunStateStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path) if not isinstance(path, Path) else path
        self.state = self.load()

    def load(self) -> RunState:
        payload = _read_json(self.path, {})
        return RunState(
            status=payload.get("status", "initialized"),
            current_step=payload.get("current_step", "bootstrap"),
            run_mode=payload.get("run_mode", "standard"),
            current_section=payload.get("current_section", ""),
            completed_sections=payload.get("completed_sections", []) or [],
            completed_chapters=payload.get("completed_chapters", []) or [],
            failed_sections=payload.get("failed_sections", []) or [],
            diagram_status=payload.get("diagram_status", "removed"),
            docx_status=payload.get("docx_status", "pending"),
            quality_status=payload.get("quality_status", "pending"),
            llm_call_count=int(payload.get("llm_call_count", 0) or 0),
            warnings=payload.get("warnings", []) or [],
            output_files=payload.get("output_files", {}) or {},
            error=payload.get("error", ""),
            last_token_time=float(payload.get("last_token_time", 0.0) or 0.0),
        )

    def save(self) -> None:
        _write_json(self.path, self.state.to_dict())

    def mark_step(self, step: str, status: Optional[str] = None) -> None:
        self.state.current_step = step
        if status:
            self.state.status = status
        self.save()

    def set_current_section(self, section_id: str) -> None:
        self.state.current_section = section_id
        self.save()

    def complete_section(self, section_id: str) -> None:
        if section_id not in self.state.completed_sections:
            self.state.completed_sections.append(section_id)
        if section_id in self.state.failed_sections:
            self.state.failed_sections.remove(section_id)
        self.state.current_section = section_id
        self.save()

    def mark_chapter_complete(self, chapter_id: str) -> None:
        if chapter_id not in self.state.completed_chapters:
            self.state.completed_chapters.append(chapter_id)
        self.state.current_section = chapter_id
        self.save()

    def increment_llm_calls(self) -> None:
        self.state.llm_call_count += 1
        self.save()

    def warn(self, message: str) -> None:
        if message not in self.state.warnings:
            self.state.warnings.append(message)
            self.save()

    def set_output(self, key: str, path: Path) -> None:
        self.state.output_files[key] = str(path)
        self.save()

    def mark_last_token(self) -> None:
        self.state.last_token_time = time.time()
        self.save()
