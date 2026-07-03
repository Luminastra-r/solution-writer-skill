"""Light final quality review based on summaries (1 LLM call)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from solution_skill.json_utils import repair_json
from solution_skill.text_utils import normalize_text, shorten


def _build_review_summary(
    blueprint: Dict[str, Any],
    chapter_texts: Dict[str, str],
    chapters: List[Any],
) -> str:
    lines: List[str] = []
    diagnosis = blueprint.get("diagnosis", {})
    lines.append("【诊断】战略对齐：" + normalize_text(diagnosis.get("strategic_alignment", "")))
    lines.append("【诊断】核心痛点：" + normalize_text(diagnosis.get("core_pain_points", "")))
    lines.append("")
    for chapter in chapters:
        body = chapter_texts.get(chapter.id, "")
        lines.append(f"第{chapter.index}章 {chapter.title}（{len(body)}字）：{shorten(body, 260)}")
    return "\n".join(lines)


def run_quality_review(
    raw_input: str,
    blueprint: Dict[str, Any],
    chapter_texts: Dict[str, str],
    chapters: List[Any],
    llm,
    request: Dict[str, Any],
    state_store,
    artifacts_dir: Path,
) -> Dict[str, Any]:
    """Produce quality_suggestions.json / .txt. Non-blocking terminal advice."""
    summary = _build_review_summary(blueprint, chapter_texts, chapters)

    system_prompt = "\n".join([
        "你是解决方案终审专家。请基于全篇摘要给出可执行的改进建议，重点检查：",
        "1. 是否显式对齐客户战略与年度重点；",
        "2. 各章是否兑现了大纲承诺（目标+内容概要）；",
        "3. 是否存在空话套话、指标缺测量方法、表格喧宾夺主；",
        "4. 章节衔接是否连贯、是否重复。",
        "只输出 JSON。",
    ])
    user_prompt = "\n".join([
        "请审查以下方案摘要，输出 JSON：",
        '{"overall": "总体评价", "strengths": ["…"], "issues": ["…"], "action_items": ["…"]}',
        "",
        "方案摘要：",
        summary,
    ])

    result: Dict[str, Any] = {}
    try:
        text = llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            state_store=state_store,
            step_key="quality_review",
            temperature=0.2,
            max_tokens=1500,
            cooldown_seconds=request.get("cooldown_seconds", 2),
        )
        parsed = repair_json(text)
        if isinstance(parsed, dict):
            result = parsed
    except Exception as exc:
        state_store.warn(f"quality review LLM failed: {exc}")

    json_path = artifacts_dir / "quality_suggestions.json"
    txt_path = artifacts_dir / "quality_suggestions.txt"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    txt_lines: List[str] = ["方案终审建议", "=" * 40, ""]
    if result.get("overall"):
        txt_lines += ["总体评价：", normalize_text(result["overall"]), ""]
    for key, label in (("strengths", "亮点"), ("issues", "问题"), ("action_items", "改进项")):
        items = result.get(key) or []
        if items:
            txt_lines.append(f"{label}：")
            txt_lines += [f"  - {normalize_text(x)}" for x in items]
            txt_lines.append("")
    if not result:
        txt_lines.append("（终审未产生结构化建议，请人工复核。）")
    txt_path.write_text("\n".join(txt_lines), encoding="utf-8")

    state_store.set_output("quality_suggestions", txt_path)
    state_store.state.quality_status = "completed"
    state_store.save()
    return result
