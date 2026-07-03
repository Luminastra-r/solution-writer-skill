"""Solution Blueprint generation.

Produces a purpose-oriented outline where EVERY leaf section carries:
  - section_goal   : one sentence, "what question this section answers"
  - content_brief  : the concrete hooks / mechanisms / roles / metrics to deliver

This mirrors the human "内容概要" contract observed in 执行步骤示例.txt, so that
chapter writing can be graded against a per-section contract instead of a vague
chapter goal.

Also supports a "staged" (阶段递进) framework (合作初稿 -> 调研诊断正式方案 ->
数字化展望) in addition to the flat frameworks in config.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from solution_skill.config import (
    ChapterUnit,
    MAX_BLUEPRINT_CHARS,
    RunMode,
    TARGET_LENGTH,
    pick_default_outline,
)
from solution_skill.json_utils import repair_json
from solution_skill.text_utils import normalize_text, shorten
from solution_skill.research.research_pack_builder import build_research_context_text


def _blueprint_system_prompt() -> str:
    return "\n".join([
        "你是资深售前解决方案架构师，擅长把客户背景、战略与需求转化为一份"
        "“目的导向”的方案蓝图。",
        "你输出的蓝图必须让后续写作者仅凭蓝图就知道每一节要回答什么、要给出哪些"
        "可落地的抓手、机制、角色与指标。",
        "严格只输出 JSON，不要输出任何解释性文字或 markdown 代码块。",
    ])


def _blueprint_user_prompt(
    raw_input: str,
    research_context: str,
    customer_insight_text: str,
    request: Dict[str, Any],
    default_outline: List[Dict[str, Any]],
    staged_hint: str,
) -> str:
    target_length = int(request.get("target_length", TARGET_LENGTH))
    output_purpose = normalize_text(request.get("output_purpose", "")) or "正式售前解决方案"
    default_titles = "、".join(item["title"] for item in default_outline)
    return "\n".join([
        "请基于以下信息，生成一份解决方案蓝图（诊断 + 大纲 + 写作指导）。",
        "",
        "【用户原始需求】",
        raw_input,
        "",
        "【客户结构化洞察】（P1 深挖结果，若为空则依据下方研究上下文与需求推断）",
        customer_insight_text or "（暂无结构化客户洞察）",
        "",
        "【研究上下文】",
        research_context,
        "",
        f"【输出目的】{output_purpose}",
        f"【目标篇幅】约 {target_length} 字",
        f"【可参考的默认章节骨架】{default_titles}",
        staged_hint,
        "",
        "【硬性要求】",
        "1. diagnosis：先给出简明诊断，字段包含 strategic_alignment（本方案如何支撑"
        "客户战略/年度重点，务必显式对齐）、core_pain_points（核心痛点，措辞需委婉、"
        "往精细化管理/运营方向引导，禁止负面定性词）、key_risks、success_criteria。",
        "2. chapters：5-7 章。每章含 id、title、chapter_goal、suggested_words。",
        "3. 每章 sections：至少 2 个末级小节，每个小节必须含：",
        "   - id、title",
        "   - section_goal：一句话说明这一节要回答的核心问题",
        "   - content_brief：一段“内容概要”，列出本节要落地的抓手/机制/角色/指标/"
        "交付物，尽量具体（可含具体指标项与责任角色），这是写作契约。",
        "4. 若适合分阶段推进，chapter 之间应体现“先建立信任的初稿 → 调研诊断的正式"
        "方案 → 面向未来的展望”这种商务递进节奏。",
        "5. 输出 target_length（整数）与 writing_guidance（对全篇的写作风格提示，"
        "强调具体可落地、指标注明测量方法、正文为连贯段落而非提纲）。",
        "",
        "【输出 JSON 结构】",
        json.dumps({
            "title": "方案标题",
            "target_length": target_length,
            "diagnosis": {
                "strategic_alignment": "…",
                "core_pain_points": ["…"],
                "key_risks": ["…"],
                "success_criteria": ["…"],
            },
            "writing_guidance": "…",
            "chapters": [
                {
                    "id": "ch01",
                    "title": "章标题",
                    "chapter_goal": "本章目标",
                    "suggested_words": 2000,
                    "sections": [
                        {
                            "id": "ch01_s1",
                            "title": "小节标题",
                            "section_goal": "本节要回答的核心问题",
                            "content_brief": "本节内容概要：要落地的抓手/机制/角色/指标…",
                        }
                    ],
                }
            ],
        }, ensure_ascii=False),
    ])


def _staged_hint(request: Dict[str, Any]) -> str:
    """Decide whether to nudge the model toward a staged framework."""
    text = " ".join([
        normalize_text(request.get("solution_topic", "")),
        normalize_text(request.get("business_needs", "")),
        normalize_text(request.get("cleaned_input", "")),
        normalize_text(request.get("output_purpose", "")),
    ]).lower()
    staged_kw = ("外包", "运营", "分步", "分阶段", "试点", "初稿", "落地", "驻场", "供应商")
    if any(kw in text for kw in staged_kw):
        return ("【结构建议】本场景适合“分阶段递进”结构：可按“合作路径设计(初稿)"
                " → 调研诊断与正式方案 → 面向未来的展望”组织章节。")
    return "【结构建议】可按标准章节骨架组织，也可按业务逻辑自定义。"


def _fallback_blueprint(
    raw_input: str,
    request: Dict[str, Any],
    default_outline: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Local fallback blueprint when the LLM output cannot be parsed."""
    chapters = []
    for idx, item in enumerate(default_outline, start=1):
        cid = f"ch{idx:02d}"
        chapters.append({
            "id": cid,
            "title": item["title"],
            "chapter_goal": f"围绕“{item['title']}”，回答客户在该维度的核心关切。",
            "suggested_words": item.get("suggested_words", 2000),
            "sections": [
                {
                    "id": f"{cid}_s1",
                    "title": f"{item['title']}·核心要点",
                    "section_goal": f"说明{item['title']}的核心内容与依据。",
                    "content_brief": "结合用户需求与客户背景，给出具体做法、机制、"
                                     "责任角色与可测量指标，避免空话套话。",
                },
                {
                    "id": f"{cid}_s2",
                    "title": f"{item['title']}·落地举措",
                    "section_goal": f"说明{item['title']}如何落地执行。",
                    "content_brief": "给出可操作的动作、时间节点、交付物与验收标准。",
                },
            ],
        })
    return {
        "title": normalize_text(request.get("solution_topic", "")) or "解决方案",
        "target_length": int(request.get("target_length", TARGET_LENGTH)),
        "diagnosis": {
            "strategic_alignment": "在缺少充分外部信息时，方案默认对齐客户降本增效"
                                    "与精细化管理目标。",
            "core_pain_points": ["管理颗粒度不足，过程数据不易追溯"],
            "key_risks": ["实施过程中的组织协同与数据可得性"],
            "success_criteria": ["关键流程标准化", "核心指标可量化可追溯"],
        },
        "writing_guidance": "正文使用连贯段落，措施说明为什么与怎么做，指标注明测量方法。",
        "chapters": chapters,
    }


def generate_blueprint(
    raw_input: str,
    research_pack: Dict[str, Any],
    request: Dict[str, Any],
    llm,
    state_store,
    artifacts_dir: Path,
) -> Dict[str, Any]:
    """Generate the solution blueprint (1 LLM call, with local fallback)."""
    state_store.mark_step("blueprint", "running")

    research_context = build_research_context_text(research_pack)
    customer_insight = research_pack.get("customer_context", {}).get("customer_insight", {})
    customer_insight_text = ""
    if isinstance(customer_insight, dict) and any(customer_insight.values()):
        customer_insight_text = json.dumps(customer_insight, ensure_ascii=False, indent=2)

    org_type = normalize_text(request.get("organization_type", ""))
    staged = "分阶段" in _staged_hint(request) or "分阶段递进" in _staged_hint(request)
    default_outline = pick_default_outline(org_type, staged=staged)

    system_prompt = _blueprint_system_prompt()
    user_prompt = _blueprint_user_prompt(
        raw_input, research_context, customer_insight_text,
        request, default_outline, _staged_hint(request),
    )

    blueprint: Optional[Dict[str, Any]] = None
    try:
        text = llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            state_store=state_store,
            step_key="blueprint",
            temperature=request.get("temperature", 0.35),
            max_tokens=4096,
            cooldown_seconds=request.get("cooldown_seconds", 2),
        )
        allow_llm = request.get("run_mode") == RunMode.HIGH_QUALITY
        parsed = repair_json(text, llm=llm, state_store=state_store,
                             step_key="blueprint", allow_llm=allow_llm)
        if isinstance(parsed, dict) and parsed.get("chapters"):
            blueprint = parsed
    except Exception as exc:
        state_store.warn(f"blueprint generation failed: {exc}")

    if blueprint is None:
        state_store.warn("blueprint fallback to local default outline")
        blueprint = _fallback_blueprint(raw_input, request, default_outline)

    blueprint.setdefault("target_length", int(request.get("target_length", TARGET_LENGTH)))
    _normalize_blueprint_ids(blueprint)

    bp_path = artifacts_dir / "solution_blueprint.json"
    bp_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")
    state_store.set_output("solution_blueprint", bp_path)
    return blueprint


def _normalize_blueprint_ids(blueprint: Dict[str, Any]) -> None:
    """Ensure chapters/sections have stable ids and required contract fields."""
    for c_idx, chapter in enumerate(blueprint.get("chapters", []), start=1):
        if not chapter.get("id"):
            chapter["id"] = f"ch{c_idx:02d}"
        chapter.setdefault("chapter_goal", "")
        chapter.setdefault("suggested_words", 2000)
        sections = chapter.get("sections") or []
        for s_idx, section in enumerate(sections, start=1):
            if not section.get("id"):
                section["id"] = f"{chapter['id']}_s{s_idx}"
            section.setdefault("section_goal", "")
            section.setdefault("content_brief", "")


def flatten_chapters(blueprint: Dict[str, Any]) -> List[ChapterUnit]:
    """Convert blueprint chapters into ChapterUnit dataclasses for the writer."""
    units: List[ChapterUnit] = []
    for idx, chapter in enumerate(blueprint.get("chapters", []), start=1):
        units.append(ChapterUnit(
            id=chapter.get("id", f"ch{idx:02d}"),
            title=normalize_text(chapter.get("title", f"第{idx}章")),
            index=idx,
            suggested_words=int(chapter.get("suggested_words", 2000) or 2000),
            chapter_goal=normalize_text(chapter.get("chapter_goal", "")),
            sections=chapter.get("sections", []) or [],
            must_cover=chapter.get("must_cover", []) or [],
        ))
    return units


def review_blueprint(blueprint, raw_input, llm, state_store, request) -> Dict[str, Any]:
    """Light blueprint review (high_quality only). Best-effort, non-blocking."""
    try:
        summary = shorten(json.dumps(blueprint, ensure_ascii=False), MAX_BLUEPRINT_CHARS)
        text = llm.generate(
            system_prompt="你是方案评审专家。请评估大纲是否覆盖需求、诊断、策略、"
                          "实施、保障、成效，是否存在空泛标题。只输出 JSON。",
            user_prompt="\n".join([
                "请审查以下方案蓝图，输出 JSON：",
                '{"pass": true/false, "issues": ["…"], "suggestions": ["…"]}',
                "",
                "蓝图：",
                summary,
            ]),
            state_store=state_store,
            step_key="blueprint_review",
            temperature=0.2,
            max_tokens=1200,
            cooldown_seconds=request.get("cooldown_seconds", 2),
        )
        result = repair_json(text) or {}
        return result if isinstance(result, dict) else {}
    except Exception as exc:
        state_store.warn(f"blueprint review failed: {exc}")
        return {}
