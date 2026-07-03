"""Lightweight knowledge index with BM25-like scoring and category boost."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from solution_skill.config import (
    MAX_KNOWLEDGE_FILES,
    MAX_KNOWLEDGE_SNIPPETS,
    MAX_KNOWLEDGE_SNIPPET_CHARS,
)
from solution_skill.text_utils import load_text_file, normalize_text, shorten

# Category boost weights for relevance scoring
CATEGORY_BOOST: Dict[str, float] = {
    "product": 2.0,
    "case_study": 1.8,
    "operations": 1.6,
    "company": 1.5,
    "industry": 1.3,
    "regulation": 1.2,
    "template": 1.1,
    "general": 1.0,
}

# Directory name → category mapping
_DIR_CATEGORY_MAP: Dict[str, str] = {
    "products": "product",
    "product": "product",
    "产品": "product",
    "cases": "case_study",
    "case": "case_study",
    "案例": "case_study",
    "operations": "operations",
    "operation": "operations",
    "运营": "operations",
    "policies": "regulation",
    "policy": "regulation",
    "政策": "regulation",
    "templates": "template",
    "template": "template",
    "模板": "template",
    "company": "company",
    "公司": "company",
    "资质": "company",
}

# Filename keyword → category mapping
_NAME_CATEGORY_KEYWORDS: List[Tuple[str, str]] = [
    ("产品", "product"),
    ("案例", "case_study"),
    ("运营", "operations"),
    ("服务", "operations"),
    ("公司", "company"),
    ("资质", "company"),
    ("政策", "regulation"),
    ("制度", "regulation"),
    ("模板", "template"),
    ("方案", "template"),
]


@dataclass
class KnowledgeDocument:
    path: Path
    category: str
    title: str
    body: str
    terms: List[str] = field(default_factory=list)


def infer_category(path: Path) -> str:
    """Infer document category from directory structure and filename."""
    # Check parent directory names
    parts = [p.lower() for p in path.parts]
    for part in parts:
        if part in _DIR_CATEGORY_MAP:
            return _DIR_CATEGORY_MAP[part]

    # Check filename keywords
    name = path.stem.lower()
    for keyword, category in _NAME_CATEGORY_KEYWORDS:
        if keyword in name:
            return category

    return "general"


def tokenize(text: str) -> List[str]:
    """Chinese + English tokenization for BM25 indexing."""
    lowered = normalize_text(text).lower()
    # Extract Chinese character sequences (2+ chars) and English/number tokens (3+ chars)
    terms = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{3,}", lowered)
    # Deduplicate while preserving order
    seen: set = set()
    result: List[str] = []
    for term in terms:
        if term not in seen:
            seen.add(term)
            result.append(term)
    return result[:48]


def build_index(knowledge_root: Path) -> List[KnowledgeDocument]:
    """Scan knowledge directory and build document index."""
    if not knowledge_root.exists():
        return []

    candidates: List[Path] = []
    for ext in ("*.md", "*.txt", "*.json", "*.csv"):
        candidates.extend(knowledge_root.rglob(ext))

    documents: List[KnowledgeDocument] = []
    for path in candidates:
        text = load_text_file(path)
        if not text.strip():
            continue
        category = infer_category(path)
        title = path.stem
        # Use first non-empty line as title if available
        first_line = ""
        for line in text.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped:
                first_line = stripped[:80]
                break
        if first_line:
            title = first_line

        terms = tokenize(text[:12000])
        if not terms:
            continue

        documents.append(KnowledgeDocument(
            path=path,
            category=category,
            title=title,
            body=text,
            terms=terms,
        ))

    return documents


def score_bm25(
    query_terms: List[str],
    documents: List[KnowledgeDocument],
    k1: float = 1.5,
    b: float = 0.75,
) -> List[Tuple[float, KnowledgeDocument]]:
    """BM25-like scoring with category boost.

    score(D, Q) = SUM_qi: IDF(qi) * (tf(qi,D) * (k1+1)) / (tf(qi,D) + k1*(1 - b + b*|D|/avgdl))
    IDF(qi) = ln((N - n(qi) + 0.5) / (n(qi) + 0.5) + 1)
    """
    if not documents or not query_terms:
        return []

    n_docs = len(documents)
    avg_dl = sum(len(doc.terms) for doc in documents) / n_docs if n_docs > 0 else 1.0

    # Compute document frequency for each query term
    df: Dict[str, int] = {}
    for term in query_terms:
        count = sum(1 for doc in documents if term in doc.terms)
        df[term] = count

    scored: List[Tuple[float, KnowledgeDocument]] = []
    for doc in documents:
        score = 0.0
        dl = len(doc.terms)
        term_counts: Dict[str, int] = {}
        for t in doc.terms:
            term_counts[t] = term_counts.get(t, 0) + 1

        for qt in query_terms:
            if qt not in term_counts:
                continue
            tf = term_counts[qt]
            n_qi = df.get(qt, 0)
            # IDF
            idf = math.log((n_docs - n_qi + 0.5) / (n_qi + 0.5) + 1.0)
            # BM25 TF component
            tf_component = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
            score += idf * tf_component

        # Apply category boost
        boost = CATEGORY_BOOST.get(doc.category, 1.0)
        score *= boost

        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def search_knowledge(
    knowledge_root: Path,
    raw_input: str,
    max_snippets: int = MAX_KNOWLEDGE_SNIPPETS,
    max_snippet_chars: int = MAX_KNOWLEDGE_SNIPPET_CHARS,
) -> Dict[str, Any]:
    """Main entry: search knowledge base and return structured results.

    Returns dict with mode, items list.
    """
    if not knowledge_root.exists():
        return {"knowledge_root": str(knowledge_root), "mode": "missing", "items": []}

    documents = build_index(knowledge_root)
    if not documents:
        return {"knowledge_root": str(knowledge_root), "mode": "empty", "items": []}

    query_terms = tokenize(raw_input)
    if not query_terms:
        return {"knowledge_root": str(knowledge_root), "mode": "empty", "items": []}

    scored = score_bm25(query_terms, documents)

    items: List[Dict[str, Any]] = []
    for score, doc in scored[:max_snippets]:
        snippet = shorten(doc.body, max_snippet_chars)
        items.append({
            "path": str(doc.path),
            "category": doc.category,
            "title": doc.title,
            "score": round(score, 3),
            "snippet": snippet,
        })

    mode = "local" if items else "empty"
    return {"knowledge_root": str(knowledge_root), "mode": mode, "items": items}
