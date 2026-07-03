"""Web search via DuckDuckGo HTML, with customer-aware query generation."""
from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import quote_plus

import requests

from solution_skill.config import MAX_WEB_RESULTS, WEB_CATEGORY_LIMITS
from solution_skill.text_utils import normalize_text, shorten, strip_trigger_prefix


def build_web_queries(raw_input: str, request: Dict) -> List[str]:
    """Generate targeted search queries based on customer info, not just raw_input."""
    customer = normalize_text(request.get("customer_name", ""))
    region = normalize_text(request.get("region", ""))
    topic = normalize_text(request.get("solution_topic", ""))
    needs = normalize_text(request.get("business_needs", ""))

    base = strip_trigger_prefix(raw_input)
    compact = shorten(base, 120)

    queries: List[str] = []

    if customer:
        # Customer-specific queries (highest priority)
        queries.append(f"{customer} 年度工作会议 重点工作")
        queries.append(f"{customer} 年度总结 工作要点")
        if region:
            queries.append(f"{customer} {region} 数字化 政务服务")
            queries.append(f"{region} 优化营商环境 {topic or '数字化'}")
        if topic:
            queries.append(f"{customer} {topic}")
            queries.append(f"{customer} 采购 {topic}")
    else:
        # Fallback: use raw_input keywords
        queries.append(f"{compact} 年度战略 重点工作 目标")
        queries.append(f"{compact} 区域 客群 特点 市场压力")

    # Policy / industry context
    if topic:
        queries.append(f"{topic} 行业 痛点 案例 对标")
        queries.append(f"{topic} 监管 合规 最新政策")
    if region:
        queries.append(f"{region} {topic or '数字化'} 政策文件 规划")

    # Procurement
    if customer and topic:
        queries.append(f"{customer} {topic} 采购 招标")

    return queries[:10]  # cap at 10 queries


def search_duckduckgo(query: str, max_results: int) -> List[Dict[str, str]]:
    """Search DuckDuckGo HTML and extract results."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    text = response.text
    pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<link>[^"]+)"[^>]*>(?P<title>.*?)</a>'
        r".*?"
        r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
        re.S,
    )
    results: List[Dict[str, str]] = []
    for match in pattern.finditer(text):
        title = re.sub(r"<.*?>", "", match.group("title")).strip()
        snippet = re.sub(r"<.*?>", "", match.group("snippet")).strip()
        link = match.group("link").strip()
        if title and link:
            results.append({
                "title": title,
                "snippet": snippet,
                "link": link,
                "query": query,
            })
        if len(results) >= max_results:
            break
    return results


def deduplicate_results(results: List[Dict[str, str]], max_results: int) -> List[Dict[str, str]]:
    """Remove duplicate results by link."""
    deduped: List[Dict[str, str]] = []
    seen_links: set = set()
    for item in results:
        link = item.get("link", "")
        if link and link not in seen_links:
            deduped.append(item)
            seen_links.add(link)
        if len(deduped) >= max_results:
            break
    return deduped


def run_web_search(
    raw_input: str,
    request: Dict,
    max_web_results: int = MAX_WEB_RESULTS,
    state_store=None,
) -> List[Dict[str, str]]:
    """Execute web search with targeted queries and deduplication.

    Returns list of result dicts with title, snippet, link, query.
    """
    queries = build_web_queries(raw_input, request)
    all_results: List[Dict[str, str]] = []
    per_query_limit = max(3, max_web_results // max(len(queries), 1))

    for query in queries:
        try:
            results = search_duckduckgo(query, per_query_limit)
            all_results.extend(results)
        except Exception as exc:
            if state_store:
                state_store.warn(f"web search failed for '{query}': {exc}")

    return deduplicate_results(all_results, max_web_results)
