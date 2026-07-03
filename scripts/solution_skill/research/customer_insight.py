"""Customer background deep-dive (P1).

Mirrors the human step in 执行步骤示例.txt where the analyst *separately* uses an
LLM to research the customer's strategy, annual priorities, org structure and
reporting lines, implicit group expectations, and the appropriate tone/wording.

This turns raw retrieval fragments into a structured 《客户洞察》 that becomes the
foundation for both the blueprint diagnosis and every chapter's writing.

Cost: 1 LLM call. Triggered when a customer is identifiable AND external research
is available (to avoid spending a call on empty context). Best-effort: on any
failure it degrades gracefully and the pipeline continues.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from solution_skill.json_utils import repair_json
from solution_skill.text_utils import normalize_text, shorten


_EMPTY_INSIGHT: Dict[str, Any] = {
    "strategic_positioning": "",
    "annual_priorities": [],
    "org_and_reporting": "",
    "implicit_expectations": [],
    "culture_tone": "",
    "alignment_hooks": [],
}


def _should_run(request: Dict[str, Any], research_pack: Dict[str, Any]) -> bool:
    """Only spend an LLM call when it can plausibly produce insight."""
    # fast mode skips the deep-dive to keep the call budget minimal.
    if normalize_text(request.get("run_mode", "")) == "fast":
        return False
    has_customer = bool(
        normalize_text(request.get("customer_name", ""))
        or normalize_text(request.get("organization_type", ""))
    )
    has_web = bool(research_pack.get("web_items"))
    has_knowledge = research_pack.get("knowledge_mode") == "local"
    # Even without external hits, a rich raw_input about a named customer is worth it.
    rich_input = len(normalize_text(request.get("cleaned_input", ""))) > 60
    return has_customer and (has_web or has_knowledge or rich_input)


def _build_context_text(research_pack: Dict[str, Any]) -> str:
    lines = []
    for item in research_pack.get("web_items", [])[:12]:
        lines.append(f"- [web] {normalize_text(item.get('title', ''))}："
                     f"{shorten(item.get('snippet', ''), 240)}")
    for item in research_pack.get("knowledge_items", [])[:8]:
        lines.append(f"- [知识库] {normalize_text(item.get('title', ''))}："
                     f"{shorten(item.get('snippet', ''), 240)}")
    return "\n".join(lines) if lines else "（无外部检索命中，请基于用户输入合理推断，"\
                                          "并对不确定处标注“需确认”。）"


def build_customer_insight(
    raw_input: str,
    request: Dict[str, Any],
    research_pack: Dict[str, Any],
    llm,
    state_store,
    artifacts_dir: Path,
) -> Dict[str, Any]:
    """Deep-dive the customer background into a structured insight dict.

    Always returns a dict shaped like _EMPTY_INSIGHT (possibly empty), and also
    writes it back into research_pack['customer_context']['customer_insight'].
    """
    insight = dict(_EMPTY_INSIGHT)

    if llm is None or not _should_run(request, research_pack):
        state_store.warn("customer insight skipped (no customer / insufficient context)")
        _attach(research_pack, insight, artifacts_dir, state_store)
        return insight

    state_store.mark_step("customer_insight", "running")
    context_text = _build_context_text(research_pack)
    customer_name = (normalize_text(request.get("customer_name", ""))
                     or normalize_text(request.get("organization_type", "")))

    system_prompt = "\n".join([
        "你是资深商业分析师与售前顾问。你的任务是把零散的检索片段与用户需求，"
        "提炼为一份结构化《客户洞察》，作为后续方案“往战略靠、往痛点打”的依据。",
        "要求：",
        "1. 把客户的公开战略、年度重点工作、组织架构与汇报关系、集团/上级的隐性期许"
        "梳理清楚；",
        "2. 明确本次需求应如何与客户战略/文化对齐（alignment_hooks）；",
        "3. 给出后续行文的措辞基调（culture_tone），尤其是涉及客户内部管理问题时应"
        "如何委婉、建设性地表达；",
        "4. 对不确定的信息，用“（推测）/（需确认）”标注，不要编造精确数字；",
        "5. 严格只输出 JSON，不要输出解释或 markdown 代码块。",
    ])
    user_prompt = "\n".join([
        f"客户：{customer_name}",
        "",
        "【用户原始需求】",
        shorten(raw_input, 1500),
        "",
        "【检索到的客户相关信息】",
        context_text,
        "",
        "请输出如下结构的 JSON：",
        json.dumps({
            "strategic_positioning": "客户战略定位（如轻资产重运营、AI+IP 转型等）",
            "annual_priorities": ["年度重点工作1", "年度重点工作2"],
            "org_and_reporting": "组织架构与汇报关系，含可能的信息过滤/管理风险点",
            "implicit_expectations": ["集团/上级的隐性期许，如验证某战略落地"],
            "culture_tone": "行文措辞基调与禁忌（如痛点须委婉、往精细化运营方向走）",
            "alignment_hooks": ["本次需求与客户战略对齐的抓手1", "抓手2"],
        }, ensure_ascii=False),
    ])

    try:
        text = llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            state_store=state_store,
            step_key="customer_insight",
            temperature=0.3,
            max_tokens=2000,
            cooldown_seconds=request.get("cooldown_seconds", 2),
        )
        parsed = repair_json(text)
        if isinstance(parsed, dict):
            for key in _EMPTY_INSIGHT:
                if parsed.get(key):
                    insight[key] = parsed[key]
    except Exception as exc:
        state_store.warn(f"customer insight failed: {exc}")

    _attach(research_pack, insight, artifacts_dir, state_store)
    return insight


def _attach(
    research_pack: Dict[str, Any],
    insight: Dict[str, Any],
    artifacts_dir: Path,
    state_store,
) -> None:
    """Write insight back into the research pack + persist a standalone artifact."""
    cc = research_pack.setdefault("customer_context", {})
    cc["customer_insight"] = insight
    # Also surface the richer fields into the flat context for backward compat.
    if insight.get("strategic_positioning"):
        cc.setdefault("recent_strategies", [])
        if insight["strategic_positioning"] not in cc["recent_strategies"]:
            cc["recent_strategies"].append(insight["strategic_positioning"])

    path = artifacts_dir / "customer_insight.json"
    path.write_text(json.dumps(insight, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        state_store.set_output("customer_insight", path)
    except Exception:
        pass
    # Persist the mutated research pack so the artifact stays in sync.
    pack_path = artifacts_dir / "research_pack.json"
    try:
        pack_path.write_text(
            json.dumps(research_pack, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
