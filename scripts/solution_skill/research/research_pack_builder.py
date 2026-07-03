"""Build the unified research pack combining web + knowledge sources."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from solution_skill.config import MAX_RESEARCH_CONTEXT_CHARS, ResearchMode
from solution_skill.text_utils import normalize_text, shorten
from solution_skill.research.web_search import run_web_search
from solution_skill.research.knowledge_index import search_knowledge


def build_research_pack(
    raw_input: str,
    request: Dict[str, Any],
    artifacts_dir: Path,
    state_store,
) -> Dict[str, Any]:
    """Build research_pack.json combining web + knowledge based on research_mode.

    research_mode behavior:
    - hybrid (default): web + knowledge in parallel, both used
    - knowledge: only local knowledge
    - web: only web search
    - off: no external research
    """
    mode = ResearchMode.resolve(request.get("research_mode", "hybrid"))
    knowledge_root = Path(request.get("knowledge_root", "") or "").resolve()
    max_web = int(request.get("max_web_results", 12))

    knowledge_result: Dict[str, Any] = {"mode": "skipped", "items": []}
    web_results: List[Dict[str, str]] = []
    web_status = "skipped"

    # Knowledge search
    if mode in (ResearchMode.HYBRID, ResearchMode.KNOWLEDGE):
        knowledge_result = search_knowledge(knowledge_root, raw_input)

    # Web search
    if mode in (ResearchMode.HYBRID, ResearchMode.WEB):
        try:
            web_results = run_web_search(raw_input, request, max_web, state_store)
            web_status = "ok" if web_results else "empty"
        except Exception as exc:
            state_store.warn(f"web search failed: {exc}")
            web_status = "failed"

    # Build source notes
    source_notes: List[Dict[str, Any]] = []
    for item in knowledge_result.get("items", []):
        source_notes.append({
            "type": "knowledge",
            "title": item.get("title", ""),
            "url_or_file": item.get("path", ""),
            "category": item.get("category", ""),
            "summary": shorten(item.get("snippet", ""), 300),
            "relevance": f"score={item.get('score', 0)}",
        })
    for item in web_results:
        source_notes.append({
            "type": "web",
            "title": item.get("title", ""),
            "url_or_file": item.get("link", ""),
            "date": "",
            "summary": shorten(item.get("snippet", ""), 300),
            "relevance": item.get("query", ""),
        })

    # Build structured context sections
    customer_context = _build_customer_context(request, web_results)
    business_context = _build_business_context(request)
    provider_capabilities = _build_provider_capabilities(knowledge_result)

    # Determine overall sufficiency
    has_web = bool(web_results)
    has_knowledge = knowledge_result.get("mode") == "local"
    external_insufficient = not has_web and not has_knowledge

    pack = {
        "mode": mode,
        "web_status": web_status,
        "knowledge_mode": knowledge_result.get("mode", "skipped"),
        "external_context_insufficient": external_insufficient,
        "customer_context": customer_context,
        "business_context": business_context,
        "provider_capabilities": provider_capabilities,
        "knowledge_items": knowledge_result.get("items", []),
        "web_items": web_results,
        "source_notes": source_notes,
    }

    # Save to artifacts
    pack_path = artifacts_dir / "research_pack.json"
    pack_path.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    state_store.set_output("research_pack", pack_path)

    return pack


def build_research_context_text(pack: Dict[str, Any]) -> str:
    """Generate prompt-ready research context text from the pack."""
    lines: List[str] = []

    # Knowledge items
    knowledge_items = pack.get("knowledge_items", [])
    if knowledge_items:
        lines.append("【本地知识库参考】")
        for item in knowledge_items:
            cat = item.get("category", "general")
            lines.append(f"- [{cat}] {item.get('title', '')}: {shorten(item.get('snippet', ''), 300)}")

    # Web items
    web_items = pack.get("web_items", [])
    if web_items:
        lines.append("【网络补充参考】")
        for item in web_items:
            lines.append(f"- {item.get('title', '')} | {shorten(item.get('snippet', ''), 200)} | {item.get('link', '')}")

    if pack.get("external_context_insufficient"):
        lines.append("【注意】外部研究上下文不足，请基于用户输入合理推断。")

    return shorten("\n".join(lines), MAX_RESEARCH_CONTEXT_CHARS) if lines else "暂无知识库或网络补充参考。"


def _build_customer_context(request: Dict[str, Any], web_results: List[Dict[str, str]]) -> Dict[str, Any]:
    """Extract customer context from request + web results."""
    return {
        "customer_name": normalize_text(request.get("customer_name", "")),
        "region": normalize_text(request.get("region", "")),
        "organization_type": normalize_text(request.get("organization_type", "")),
        "recent_strategies": [],
        "recent_meetings": [],
        "public_pain_points": [],
        "policy_drivers": [],
        "web_search_count": len(web_results),
    }


def _build_business_context(request: Dict[str, Any]) -> Dict[str, Any]:
    """Extract business context from request."""
    return {
        "target_business": normalize_text(request.get("solution_topic", "")),
        "business_needs": normalize_text(request.get("business_needs", "")),
        "key_processes": [],
        "known_pain_points": [],
        "procurement_focus": [],
    }


def _build_provider_capabilities(knowledge_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract provider capabilities from knowledge items."""
    items = knowledge_result.get("items", [])
    products: List[str] = []
    operations: List[str] = []
    cases: List[str] = []

    for item in items:
        cat = item.get("category", "general")
        title = item.get("title", "")
        if cat == "product":
            products.append(title)
        elif cat == "operations":
            operations.append(title)
        elif cat == "case_study":
            cases.append(title)

    return {
        "products": products[:6],
        "operations": operations[:4],
        "cases": cases[:4],
        "advantages": [],
        "knowledge_available": knowledge_result.get("mode") == "local",
    }
