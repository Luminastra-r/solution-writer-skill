"""Input parsing, normalization, and completeness assessment."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from solution_skill.config import (
    COOLDOWN_SECONDS,
    MAX_WEB_RESULTS,
    REPO_ROOT,
    ResearchMode,
    RunMode,
    TEMPERATURE,
    TARGET_LENGTH,
)
from solution_skill.text_utils import normalize_text, strip_trigger_prefix


def parse_input(payload: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    """Parse input JSON + CLI args into normalized request.

    Compatible with old raw_input / initial_user_input fields.
    Maps research_mode 'auto' → 'hybrid'.
    """
    delivery = payload.get("delivery") or {}

    # Extract raw_input (support old field names)
    raw_input = normalize_text(
        payload.get("raw_input") or payload.get("initial_user_input") or ""
    )

    # Strip trigger prefix
    cleaned_input = strip_trigger_prefix(raw_input)

    # Extract structured fields from the request
    customer_name = normalize_text(
        payload.get("customer_name") or payload.get("customer") or delivery.get("customer") or ""
    )
    project_name = normalize_text(
        payload.get("project_name") or payload.get("project") or delivery.get("project") or ""
    )
    region = normalize_text(payload.get("region", ""))
    organization_type = normalize_text(payload.get("organization_type", ""))
    solution_topic = normalize_text(payload.get("solution_topic", ""))
    business_needs = normalize_text(payload.get("business_needs", ""))
    output_purpose = normalize_text(payload.get("output_purpose", ""))
    writing_style = normalize_text(payload.get("writing_style", "")) or "正式商务解决方案风格"

    # Infer missing fields from raw_input if possible
    if not solution_topic and cleaned_input:
        solution_topic = cleaned_input[:100]

    # Knowledge root
    knowledge_root = normalize_text(payload.get("knowledge_root", ""))
    if args.knowledge_root:
        knowledge_root = args.knowledge_root
    if not knowledge_root:
        knowledge_root = str(REPO_ROOT / "knowledge")

    # Research mode: resolve legacy 'auto' → 'hybrid'
    research_mode = normalize_text(payload.get("research_mode", "")) or "auto"
    if args.research_mode:
        research_mode = args.research_mode
    research_mode = ResearchMode.resolve(research_mode)

    # Run mode
    run_mode = getattr(args, "run_mode", None) or RunMode.STANDARD

    # Numeric params
    cooldown = int(payload.get("cooldown_seconds", COOLDOWN_SECONDS) or COOLDOWN_SECONDS)
    temperature = float(payload.get("temperature", TEMPERATURE) or TEMPERATURE)
    max_web = int(payload.get("max_web_results", MAX_WEB_RESULTS) or MAX_WEB_RESULTS)
    target_length = int(payload.get("target_length", TARGET_LENGTH) or TARGET_LENGTH)
    review_rewrite_limit = int(payload.get("review_rewrite_limit", 0))

    # CLI overrides
    if args.max_web_results:
        max_web = args.max_web_results
    if args.review_rewrite_limit is not None:
        review_rewrite_limit = args.review_rewrite_limit

    # Apply run_mode defaults for review_rewrite_limit
    if run_mode == RunMode.FAST:
        review_rewrite_limit = 0
    elif run_mode == RunMode.STANDARD and review_rewrite_limit > 0:
        review_rewrite_limit = 0  # standard: no auto rewrite

    # Output docx
    output_docx = normalize_text(payload.get("output_docx") or delivery.get("output_docx", ""))

    # Use knowledge / use web flags
    use_knowledge = payload.get("use_knowledge", research_mode in ("hybrid", "knowledge"))
    use_web = payload.get("use_web", research_mode in ("hybrid", "web"))

    return {
        "raw_input": raw_input,
        "cleaned_input": cleaned_input,
        "customer_name": customer_name,
        "project_name": project_name,
        "region": region,
        "organization_type": organization_type,
        "solution_topic": solution_topic,
        "business_needs": business_needs,
        "output_purpose": output_purpose,
        "target_length": target_length,
        "use_knowledge": use_knowledge,
        "use_web": use_web,
        "writing_style": writing_style,
        "output_docx": output_docx,
        "knowledge_root": knowledge_root,
        "research_mode": research_mode,
        "run_mode": run_mode,
        "cooldown_seconds": cooldown,
        "temperature": temperature,
        "max_web_results": max_web,
        "review_rewrite_limit": review_rewrite_limit,
    }


def assess_completeness(request: Dict[str, Any]) -> Dict[str, Any]:
    """Local completeness check (no LLM). Checks key fields.

    Returns a richer assessment so the caller can list the *main* missing points
    and let the user supplement in a single round (fill what they can — missing
    items never block generation).

    Returns:
        {"score": int, "missing": [...descriptions...],
         "missing_keys": [...field keys...], "present": [...],
         "sparse": bool, "prompts": {key: guiding question}}
    """
    key_fields = {
        "customer_name": "客户单位名称或客户类型",
        "region": "客户所在城市/区域",
        "solution_topic": "方案主要围绕什么业务、采购内容或场景",
        "business_needs": "已知痛点、需求或客户关注点",
    }
    # Guiding questions shown to the user for a one-round supplement.
    field_prompts = {
        "customer_name": "客户是谁？（单位全称或客户类型，如某集团/某银行分行/某园区）",
        "region": "客户所在城市或区域？（用于结合区域政策与市场背景）",
        "solution_topic": "本次方案要解决什么？（核心业务、采购内容或场景，一两句即可）",
        "business_needs": "已知的痛点、目标或客户特别关注的点？（有多少写多少）",
    }

    present: List[str] = []
    missing: List[str] = []
    missing_keys: List[str] = []

    for field_key, description in key_fields.items():
        value = normalize_text(request.get(field_key, ""))
        # Also check if it's mentioned in raw_input/cleaned_input
        if not value:
            raw = normalize_text(request.get("cleaned_input", ""))
            # Simple heuristic: if the field keyword appears in raw input, consider it present
            if field_key == "customer_name" and any(
                kw in raw for kw in ("客户", "单位", "公司", "银行", "分行", "局", "厅", "委")
            ):
                present.append(field_key)
                continue
            if field_key == "region" and any(
                kw in raw for kw in ("省", "市", "区", "北京", "上海", "广州", "深圳", "杭州")
            ):
                present.append(field_key)
                continue
            if field_key == "solution_topic" and len(raw) > 20:
                present.append(field_key)
                continue
            if field_key == "business_needs" and any(
                kw in raw for kw in ("问题", "痛点", "需求", "希望", "目标", "优化", "提升")
            ):
                present.append(field_key)
                continue
            missing.append(description)
            missing_keys.append(field_key)
        else:
            present.append(field_key)

    score = len(present)
    sparse = len(missing) >= 2

    return {
        "score": score,
        "missing": missing,
        "missing_keys": missing_keys,
        "present": present,
        "sparse": sparse,
        "prompts": {k: field_prompts[k] for k in missing_keys},
    }


def generate_clarification(
    assessment: Dict[str, Any],
    artifacts_dir: Path,
) -> Dict[str, Any]:
    """Generate a one-round supplement request when input is sparse.

    Lists the main missing points as guiding questions. Explicitly tells the user
    to fill in whatever they can in a single round — missing items will NOT block
    generation; the pipeline continues in generic mode either way.
    """
    prompts = assessment.get("prompts", {})
    missing = assessment.get("missing", [])

    questions: List[str] = []
    source = prompts.values() if prompts else missing
    for i, item in enumerate(source, start=1):
        questions.append(f"{i}. {item}")

    intro = (
        "为了让方案更贴合实际、质量更高，建议补充以下信息（有多少写多少，"
        "一轮补充即可，缺失的部分不会阻塞生成）：\n"
    )
    tail = (
        "\n\n说明：以上信息用于深挖客户背景与对齐战略。"
        "您可以只回答其中几项；直接回复补充内容，或输入“继续”即以现有信息生成方案。\n"
    )
    md_content = intro + "\n".join(questions) + tail

    payload = {
        "sparse": True,
        "one_round_supplement": True,
        "questions": questions,
        "missing_keys": assessment.get("missing_keys", []),
        "introduction": intro,
        "full_text": md_content,
    }

    # Save artifacts
    json_path = artifacts_dir / "clarification_questions.json"
    md_path = artifacts_dir / "clarification_questions.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(md_content, encoding="utf-8")

    return payload


def maybe_enrich_input(
    request: Dict[str, Any],
    assessment: Dict[str, Any],
    llm=None,
    state_store=None,
) -> Dict[str, Any]:
    """Optionally enrich input using 1 LLM call (high_quality mode only).

    If run_mode is not high_quality or completeness is adequate, return as-is.
    """
    if request.get("run_mode") != RunMode.HIGH_QUALITY:
        return request
    if assessment.get("score", 0) >= 3:
        return request
    if llm is None or state_store is None:
        return request

    # Use 1 LLM call to infer missing fields from raw_input
    try:
        text = llm.generate(
            system_prompt="你是需求分析助手。请从用户输入中提取结构化信息，只输出 JSON。",
            user_prompt="\n".join([
                "请从以下用户输入中提取：customer_name（客户名称）、region（区域）、",
                "organization_type（客户类型，如政府/银行/国企/企业）、solution_topic（方案主题）、",
                "business_needs（业务需求/痛点）。",
                "只输出 JSON，不确定的字段填空字符串。",
                "",
                "用户输入：",
                request.get("cleaned_input", request.get("raw_input", "")),
            ]),
            state_store=state_store,
            step_key="intake_enrich",
            temperature=0.1,
            max_tokens=800,
            cooldown_seconds=request.get("cooldown_seconds", 2),
        )
        from solution_skill.json_utils import parse_llm_json
        enriched = parse_llm_json(text)
        if isinstance(enriched, dict):
            for key in ("customer_name", "region", "organization_type", "solution_topic", "business_needs"):
                if not request.get(key) and enriched.get(key):
                    request[key] = normalize_text(enriched[key])
    except Exception:
        pass  # enrichment is best-effort

    return request
