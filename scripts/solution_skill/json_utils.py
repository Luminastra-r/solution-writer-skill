"""JSON parsing and local-first repair utilities."""
from __future__ import annotations

import ast
import json
import re
from typing import Any, List, Optional, TYPE_CHECKING

from solution_skill.text_utils import normalize_text, remove_reasoning

if TYPE_CHECKING:
    from solution_skill.llm_client import OpenAILLM
    from solution_skill.run_state import RunStateStore


def clean_json_text(text: str) -> str:
    cleaned = remove_reasoning(text)
    fenced = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", cleaned, re.S)
    return fenced.group(1).strip() if fenced else cleaned.strip()


def _extract_balanced_json(text: str) -> Optional[str]:
    if not text:
        return None
    start_positions = []
    for token in ("{", "["):
        pos = text.find(token)
        if pos >= 0:
            start_positions.append(pos)
    if not start_positions:
        return None
    start = min(start_positions)
    opening = text[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return text[start: idx + 1].strip()
    return None


def parse_llm_json(text: str) -> Optional[Any]:
    """Parse JSON from LLM output, trying multiple extraction strategies."""
    payload = clean_json_text(text)
    candidates: List[str] = []
    if payload:
        candidates.append(payload)
    balanced = _extract_balanced_json(payload)
    if balanced and balanced not in candidates:
        candidates.append(balanced)
    balanced_raw = _extract_balanced_json(remove_reasoning(text))
    if balanced_raw and balanced_raw not in candidates:
        candidates.append(balanced_raw)
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def local_json_repair(text: str) -> Optional[Any]:
    """Attempt local JSON repair without LLM. Returns parsed object or None.

    Strategy chain:
    1. Direct json.loads on cleaned text
    2. Extract balanced JSON then json.loads
    3. Fix common issues (trailing commas, control chars) then retry
    4. ast.literal_eval as last resort
    """
    cleaned = clean_json_text(text)

    # 1. Direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2. Balanced extraction
    balanced = _extract_balanced_json(cleaned)
    if balanced:
        try:
            return json.loads(balanced)
        except Exception:
            pass
    else:
        balanced = cleaned

    # 3. Fix common issues
    fixed = balanced
    # Remove trailing commas before } or ]
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    # Remove control characters (except \n, \r, \t)
    fixed = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", fixed)
    # Replace single quotes used as JSON delimiters (careful not to break content)
    # Only attempt if no double quotes found at structural positions
    if "'" in fixed and '"' not in fixed[:50]:
        fixed = fixed.replace("'", '"')
    try:
        return json.loads(fixed)
    except Exception:
        pass

    # 4. ast.literal_eval (handles Python dict/list syntax)
    try:
        result = ast.literal_eval(fixed)
        if isinstance(result, (dict, list)):
            return result
    except Exception:
        pass

    return None


def repair_json(
    text: str,
    llm: Optional["OpenAILLM"] = None,
    state_store: Optional["RunStateStore"] = None,
    step_key: str = "json_repair",
    temperature: float = 0.1,
    cooldown_seconds: int = 2,
    allow_llm: bool = False,
) -> Optional[Any]:
    """Full repair chain: local first, then optionally LLM.

    Args:
        allow_llm: Only True for high_quality mode. Default False.
    """
    # Try parse_llm_json first (existing logic)
    result = parse_llm_json(text)
    if result is not None:
        return result

    # Try local repair chain
    result = local_json_repair(text)
    if result is not None:
        return result

    # LLM repair only if explicitly allowed (high_quality mode)
    if allow_llm and llm is not None and state_store is not None:
        try:
            repaired = llm.generate(
                system_prompt="你是 JSON 修复助手。请把输入内容整理成可被 json.loads 解析的 JSON，并且只输出 JSON。",
                user_prompt="\n".join([
                    "请把下面内容整理成合法 JSON。",
                    "要求：",
                    "1. 只输出 JSON。",
                    "2. 不补充解释，不保留 markdown 代码块。",
                    "3. 尽量保持原有字段和层级结构。",
                    "",
                    "待整理内容：",
                    text,
                ]),
                state_store=state_store,
                step_key=f"{step_key}_json_repair",
                temperature=temperature,
                max_tokens=4000,
                cooldown_seconds=cooldown_seconds,
            )
            return parse_llm_json(repaired)
        except Exception:
            return None

    return None
