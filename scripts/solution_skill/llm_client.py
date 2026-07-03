"""OpenAI-compatible streaming LLM client."""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from solution_skill.config import LLM_MAX_RETRIES, LLM_RETRY_BASE_SECONDS
from solution_skill.text_utils import normalize_text

if TYPE_CHECKING:
    from solution_skill.run_state import RunStateStore

try:
    from openai import OpenAI as _OpenAI
except Exception:
    _OpenAI = None


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class OpenAILLM:
    """Wrapper around the openai Python client with streaming + retry."""

    def __init__(self, model: str, base_url: str = "", api_key: str = "") -> None:
        if _OpenAI is None:
            raise RuntimeError("openai package is not available.")
        resolved_key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not resolved_key:
            raise RuntimeError("OPENAI_API_KEY is required.")
        kwargs: Dict[str, Any] = {"api_key": resolved_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = _OpenAI(**kwargs)
        self.model = model

    def _extract_chunk_text(self, chunk: Any) -> str:
        choices = getattr(chunk, "choices", None)
        if choices:
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None) if delta is not None else None
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: List[str] = []
                for item in content:
                    text = getattr(item, "text", None)
                    if text:
                        parts.append(text)
                    elif isinstance(item, dict) and item.get("text"):
                        parts.append(str(item["text"]))
                return "".join(parts)
        if isinstance(chunk, dict):
            choices = chunk.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str):
                    return content
        return ""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        state_store: "RunStateStore",
        step_key: str,
        temperature: float = 0.35,
        max_tokens: int = 4096,
        cooldown_seconds: int = 2,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        last_error: Optional[Exception] = None
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                parts: List[str] = []
                for chunk in stream:
                    piece = self._extract_chunk_text(chunk)
                    if piece:
                        parts.append(piece)
                        state_store.mark_last_token()
                text = "".join(parts).strip()
                if not text:
                    state_store.warn(f"{step_key} stream returned no content; fallback to non-stream.")
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=False,
                    )
                    choice = response.choices[0]
                    message = getattr(choice, "message", None)
                    text = normalize_text(getattr(message, "content", ""))
                    state_store.mark_last_token()
                if not text:
                    raise RuntimeError("empty response")
                self.cooldown(state_store, cooldown_seconds)
                state_store.increment_llm_calls()
                return text.strip()
            except Exception as exc:
                last_error = exc
                state_store.warn(f"{step_key} attempt {attempt} failed: {exc}")
                if attempt >= LLM_MAX_RETRIES:
                    break
                wait_seconds = LLM_RETRY_BASE_SECONDS * attempt
                log(f"{step_key} 调用失败，{wait_seconds}s 后重试 ({attempt}/{LLM_MAX_RETRIES}): {exc}")
                time.sleep(wait_seconds)
        raise RuntimeError(f"{step_key} generation failed after {LLM_MAX_RETRIES} attempts: {last_error}")

    def cooldown(self, state_store: "RunStateStore", seconds: int) -> None:
        last = float(state_store.state.last_token_time or 0.0)
        while last > 0:
            remaining = seconds - (time.time() - last)
            if remaining <= 0:
                return
            time.sleep(min(1.0, remaining))
