"""Centralized constants, enums, and dataclass definitions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Paths ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]  # solution-writer-skill/
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts"

# ── Pipeline defaults ──────────────────────────────────────────────────
COOLDOWN_SECONDS = 2
TEMPERATURE = 0.35
TARGET_LENGTH = 12000
MAX_WEB_RESULTS = 12
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_SECONDS = 3

# ── Content limits ─────────────────────────────────────────────────────
MAX_KNOWLEDGE_FILES = 12
MAX_KNOWLEDGE_SNIPPETS = 8
MAX_KNOWLEDGE_SNIPPET_CHARS = 900
MAX_RESEARCH_CONTEXT_CHARS = 4200
MAX_BLUEPRINT_CHARS = 5000

# ── Directory names ────────────────────────────────────────────────────
CHAPTERS_DIRNAME = "chapters"

# ── Regex ──────────────────────────────────────────────────────────────
REASONING_BLOCK_RE = re.compile(r"(?is)<think\b[^>]*>.*?</think>")
FENCE_RE = re.compile(r"(?is)^```(?:json|markdown|md)?\s*(.*?)\s*```$")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+")
META_LINE_PATTERNS = [
    re.compile(r"^\s*(?:以下|下面|现将|现把).*(?:正文|内容|方案|章节).*$"),
    re.compile(r"^\s*(?:说明|注)[:：].*$"),
    re.compile(r"^\s*(?:修订后|修复后|优化后).*$"),
    re.compile(r"^\s*(?:我将|我会|我已|已根据).*$"),
]


# ── Enums (string-based) ──────────────────────────────────────────────
class RunMode:
    FAST = "fast"
    STANDARD = "standard"
    HIGH_QUALITY = "high_quality"
    ALL = (FAST, STANDARD, HIGH_QUALITY)


class ResearchMode:
    HYBRID = "hybrid"
    KNOWLEDGE = "knowledge"
    WEB = "web"
    OFF = "off"
    ALL = (HYBRID, KNOWLEDGE, WEB, OFF)

    @staticmethod
    def resolve(value: str) -> str:
        """Map legacy 'auto' to 'hybrid'."""
        v = (value or "").strip().lower()
        if v in ("auto", ""):
            return ResearchMode.HYBRID
        if v in ResearchMode.ALL:
            return v
        return ResearchMode.HYBRID


# ── LLM call budget per run mode ──────────────────────────────────────
RUN_MODE_LLM_BUDGET: Dict[str, Dict[str, Any]] = {
    "fast": {
        "blueprint": 1, "chapters": "1/ch", "review": 0, "intake": 0,
        "customer_insight": 0, "review_rewrite_limit": 0,
    },
    "standard": {
        "blueprint": 1, "chapters": "1/ch", "review": 1, "intake": 0,
        "customer_insight": 1, "review_rewrite_limit": 0,
    },
    "high_quality": {
        "blueprint": 1, "chapters": "1/ch", "review": 1,
        "blueprint_review": 1, "batch_review": 1, "intake": 1,
        "customer_insight": 1, "review_rewrite_limit": 1,
    },
}


# ── Web search category limits ────────────────────────────────────────
WEB_CATEGORY_LIMITS: Dict[str, int] = {
    "customer_news": 6,
    "policy_context": 4,
    "procurement": 4,
    "industry_practice": 4,
}


# ── Dataclasses ────────────────────────────────────────────────────────
@dataclass
class ChapterUnit:
    id: str
    title: str
    index: int
    suggested_words: int
    chapter_goal: str = ""
    sections: List[Dict[str, Any]] = field(default_factory=list)
    must_cover: List[str] = field(default_factory=list)
    evidence_to_use: List[str] = field(default_factory=list)
    knowledge_to_use: List[str] = field(default_factory=list)


@dataclass
class RunConfig:
    run_mode: str = "standard"
    research_mode: str = "hybrid"
    max_web_results: int = MAX_WEB_RESULTS
    review_rewrite_limit: int = 0
    cooldown_seconds: int = COOLDOWN_SECONDS
    temperature: float = TEMPERATURE
    knowledge_root: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    target_length: int = TARGET_LENGTH


# ── Default outline frameworks ────────────────────────────────────────
DEFAULT_OUTLINE_GENERIC = [
    {"title": "项目背景与客户需求理解", "suggested_words": 2000},
    {"title": "业务现状、痛点与建设必要性", "suggested_words": 2000},
    {"title": "总体解决方案设计", "suggested_words": 2500},
    {"title": "重点业务场景与能力建设方案", "suggested_words": 2500},
    {"title": "运营服务机制与实施保障", "suggested_words": 2000},
    {"title": "合作模式、预期成效与未来展望", "suggested_words": 1500},
]

DEFAULT_OUTLINE_GOVERNMENT = [
    {"title": "政策背景与区域业务环境", "suggested_words": 2000},
    {"title": "客户单位业务现状与需求分析", "suggested_words": 2000},
    {"title": "建设目标与总体思路", "suggested_words": 2000},
    {"title": "解决方案设计", "suggested_words": 2500},
    {"title": "运营组织与服务保障机制", "suggested_words": 2000},
    {"title": "实施路径、成效评估与合作展望", "suggested_words": 1500},
]

DEFAULT_OUTLINE_ENTERPRISE = [
    {"title": "行业趋势与客户经营背景", "suggested_words": 2000},
    {"title": "当前业务挑战与需求分析", "suggested_words": 2000},
    {"title": "解决方案总体设计", "suggested_words": 2500},
    {"title": "核心功能与服务场景", "suggested_words": 2500},
    {"title": "交付运营机制与管理保障", "suggested_words": 2000},
    {"title": "合作价值与后续拓展", "suggested_words": 1500},
]


# Staged / phased framework (合作初稿 → 调研诊断正式方案 → 面向未来的展望)
# Mirrors the商务递进 rhythm observed in 执行步骤示例.txt.
DEFAULT_OUTLINE_STAGED = [
    {"title": "合作背景与整体思路", "suggested_words": 2000},
    {"title": "第一环节：合作路径设计（初稿）", "suggested_words": 2500},
    {"title": "落地策略与实施路径", "suggested_words": 2500},
    {"title": "第二环节：调研诊断与成效汇报（正式方案）", "suggested_words": 2500},
    {"title": "分步推进计划与里程碑", "suggested_words": 2000},
    {"title": "面向未来的数字化展望", "suggested_words": 1500},
]


def pick_default_outline(org_type: str, staged: bool = False) -> List[Dict[str, Any]]:
    """Select default outline framework based on organization type.

    When staged=True, return the phased (阶段递进) framework instead of the flat one.
    """
    if staged:
        return DEFAULT_OUTLINE_STAGED
    t = (org_type or "").strip().lower()
    gov_keywords = ("政府", "政务", "行政", "监管", "执法", "公共", "事业", "园区")
    ent_keywords = ("企业", "公司", "集团", "银行", "保险", "金融", "国企", "央企")
    if any(kw in t for kw in gov_keywords):
        return DEFAULT_OUTLINE_GOVERNMENT
    if any(kw in t for kw in ent_keywords):
        return DEFAULT_OUTLINE_ENTERPRISE
    return DEFAULT_OUTLINE_GENERIC
