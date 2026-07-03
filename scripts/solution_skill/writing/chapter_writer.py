"""Chapter writing. One LLM call per chapter.

Enforces the per-section contract from the blueprint:
  - each section_goal must be answered
  - each content_brief must be fulfilled item by item
  - strategy alignment + tactful wording (P3)
  - plain coherent prose, tables only as support (writing-guidelines.md)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from solution_skill.config import TARGET_LENGTH
from solution_skill.text_utils import clean_chapter_body, normalize_text, shorten
from solution_skill.research.research_pack_builder import build_research_context_text


def _system_prompt() -> str:
    return "\n".join([
        "你是资深售前方案撰写专家。你会严格按照给定的“本章大纲契约”撰写正文，"
        "逐条兑现每个小节的写作要求。",
        "写作硬性规范：",
        "1. 正文使用连贯的中文段落，不使用 markdown 加粗/斜体/无序或有序列表符号；"
        "仅表格可用 markdown 表格语法。",
        "2. 每个措施都要说明“为什么”和“怎么做”，给出动作、机制、路径、角色、指标；"
        "量化指标必须注明测量方法与数据来源。",
        "3. 禁止空话套话（如“提高认识、加强领导、狠抓落实”）。",
        "4. 显式说明本章举措如何支撑客户的战略与年度重点。",
        "5. 涉及客户内部管理问题时，措辞委婉、建设性，往精细化运营管理方向引导，"
        "不使用负面定性词。",
        "6. 表格只能作为辅助说明，正文描述必须充分，表格不得超过本章篇幅的一半。",
    ])


def _sections_contract_text(sections: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for i, sec in enumerate(sections, start=1):
        title = normalize_text(sec.get("title", f"小节{i}"))
        goal = normalize_text(sec.get("section_goal", ""))
        brief = normalize_text(sec.get("content_brief", ""))
        lines.append(f"{i}. 小节标题：{title}")
        if goal:
            lines.append(f"   本节要回答：{goal}")
        if brief:
            lines.append(f"   内容概要（必须逐条兑现）：{brief}")
    return "\n".join(lines) if lines else "（本章无细分小节，请围绕章节目标自行组织 2-3 个小节）"


def _user_prompt(
    raw_input: str,
    blueprint: Dict[str, Any],
    research_pack: Dict[str, Any],
    chapter,
    completed_chapters: List[Dict[str, str]],
    request: Dict[str, Any],
) -> str:
    diagnosis = blueprint.get("diagnosis", {})
    writing_guidance = normalize_text(blueprint.get("writing_guidance", ""))
    research_context = build_research_context_text(research_pack)
    customer_insight = research_pack.get("customer_context", {}).get("customer_insight", {})
    insight_text = ""
    if isinstance(customer_insight, dict) and any(customer_insight.values()):
        insight_text = json.dumps(customer_insight, ensure_ascii=False, indent=2)

    prior = ""
    if completed_chapters:
        prior_lines = [
            f"- {c['title']}：{shorten(c.get('body', ''), 220)}"
            for c in completed_chapters[-3:]
        ]
        prior = "【已完成章节摘要（保持衔接、避免重复）】\n" + "\n".join(prior_lines)

    min_words = int(chapter.suggested_words or 2000)
    return "\n".join([
        f"请撰写第{chapter.index}章：{chapter.title}",
        f"本章目标：{chapter.chapter_goal}",
        f"本章建议字数：不少于 {min_words} 字。",
        "",
        "【本章大纲契约】（必须逐个小节按“内容概要”兑现，用二级/三级标题组织）",
        _sections_contract_text(chapter.sections),
        "",
        "【方案诊断（全篇一致）】",
        f"战略对齐：{normalize_text(diagnosis.get('strategic_alignment', ''))}",
        f"核心痛点：{normalize_text(diagnosis.get('core_pain_points', ''))}",
        f"成功标准：{normalize_text(diagnosis.get('success_criteria', ''))}",
        "",
        "【客户结构化洞察】",
        insight_text or "（暂无，请依据用户需求与研究上下文合理推断）",
        "",
        "【研究上下文】",
        research_context,
        "",
        "【用户原始需求】",
        shorten(raw_input, 1200),
        "",
        prior,
        "",
        f"【全篇写作指导】{writing_guidance}",
        "",
        "请直接输出本章正文（以“## " + chapter.title + "”作为章标题开头），"
        "不要输出任何前言、说明或“以下是正文”之类的话。",
    ])


def write_chapter(
    raw_input: str,
    blueprint: Dict[str, Any],
    research_pack: Dict[str, Any],
    chapter,
    completed_chapters: List[Dict[str, str]],
    llm,
    request: Dict[str, Any],
    state_store,
    chapters_dir: Path,
) -> Tuple[str, Dict[str, Any]]:
    """Write a single chapter. Returns (body, meta)."""
    state_store.set_current_section(chapter.id)
    system_prompt = _system_prompt()
    user_prompt = _user_prompt(
        raw_input, blueprint, research_pack, chapter,
        completed_chapters, request,
    )

    status = "ok"
    try:
        text = llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            state_store=state_store,
            step_key=f"chapter_{chapter.id}",
            temperature=request.get("temperature", 0.35),
            max_tokens=8192,
            cooldown_seconds=request.get("cooldown_seconds", 2),
        )
        body = clean_chapter_body(text, chapter.title)
    except Exception as exc:
        state_store.warn(f"chapter {chapter.id} failed: {exc}")
        body = f"## {chapter.title}\n\n（本章生成失败：{exc}）\n"
        status = "failed"

    if not body.strip():
        body = f"## {chapter.title}\n\n（本章内容为空）\n"
        status = "empty"

    chapter_path = chapters_dir / f"chapter_{chapter.index:02d}.md"
    chapter_path.write_text(body, encoding="utf-8")

    meta = {
        "id": chapter.id,
        "title": chapter.title,
        "word_count": len(body),
        "status": status,
        "path": str(chapter_path),
    }
    return body, meta
