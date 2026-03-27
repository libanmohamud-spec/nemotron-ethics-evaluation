"""
Shared helpers for NeMo Guardrails + Nemotron Content Safety (vLLM on :8001).
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.rails.llm.options import (
    GenerationLogOptions,
    GenerationOptions,
    GenerationRailsOptions,
)

REASONING_BLOCK = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

# Fallback when logs are unavailable (should be rare with activated_rails logging)
REFUSAL_SNIPPETS = (
    "i'm sorry",
    "i cannot",
    "can't assist",
    "cannot assist",
    "can't help",
    "cannot help",
    "not able to",
    "unable to",
    "can't comply",
    "cannot comply",
    "refuse",
    "content policy",
    "against my guidelines",
)


def _patch_reasoning_enabled(config: Any, enabled: bool) -> None:
    """Set rails.config.content_safety.reasoning.enabled in-place for /think vs /no_think."""
    try:
        cs = config.rails.config.content_safety
        if cs is not None and cs.reasoning is not None:
            object.__setattr__(cs.reasoning, "enabled", enabled)
    except Exception:
        pass


def load_rails(
    config_dir: str | Path,
    reasoning_enabled: bool = False,
) -> LLMRails:
    path = Path(config_dir)
    config = RailsConfig.from_path(str(path))
    _patch_reasoning_enabled(config, reasoning_enabled)
    return LLMRails(config)


def _rails_stopped(log: Any) -> Optional[bool]:
    """Return True if any activated rail requested stop (blocked). None if unknown."""
    if log is None:
        return None
    activated = getattr(log, "activated_rails", None) or []
    for rail in activated:
        if getattr(rail, "stop", False):
            return True
        for d in getattr(rail, "decisions", None) or []:
            ds = str(d).lower()
            if "refuse" in ds or "stop" in ds or "block" in ds:
                return True
    return False


def _content_from_response(response: Any) -> str:
    if hasattr(response, "response"):
        inner = getattr(response, "response")
        if isinstance(inner, str):
            return inner
        if isinstance(inner, list) and inner:
            return _content_from_response(inner[0])
    if isinstance(response, dict):
        return str(response.get("content", "") or "")
    if isinstance(response, str):
        return response
    return str(response)


def _guess_blocked_from_content(content: str) -> bool:
    low = content.lower()
    return any(s in low for s in REFUSAL_SNIPPETS)


def extract_reasoning_trace(text: str) -> Optional[str]:
    if not text:
        return None
    m = REASONING_BLOCK.search(text)
    if m:
        return m.group(1).strip()
    return None


def extract_raw_response_for_log(
    gen_response: Any,
) -> Tuple[str, Optional[str]]:
    """Best-effort full text + reasoning trace from GenerationResponse or dict."""
    if gen_response is None:
        return "", None
    if hasattr(gen_response, "response"):
        resp = getattr(gen_response, "response")
        if isinstance(resp, str):
            return resp, extract_reasoning_trace(resp)
        if isinstance(resp, list) and resp:
            c = _content_from_response(resp[0])
            return c, extract_reasoning_trace(c)
    return "", None


def run_guardrail_prompt(
    rails: LLMRails,
    prompt: str,
    *,
    input_only: bool = True,
) -> Dict[str, Any]:
    """
    Run one user prompt through guardrails.

    Uses `GenerationOptions` so `activated_rails` can distinguish blocked vs passed.
    When input_only=True, disables dialog/output/retrieval so the main LLM is not required.
    """
    rails_opts = GenerationRailsOptions(
        input=True,
        output=False if input_only else True,
        dialog=False if input_only else True,
        retrieval=False,
        tool_output=False if input_only else True,
        tool_input=False if input_only else True,
    )
    log_opts = GenerationLogOptions(activated_rails=True, llm_calls=True)
    options = GenerationOptions(rails=rails_opts, log=log_opts)

    t0 = time.perf_counter()
    response = rails.generate(
        messages=[{"role": "user", "content": prompt}],
        options=options,
    )
    latency_s = time.perf_counter() - t0

    log = getattr(response, "log", None) if hasattr(response, "log") else None
    stopped = _rails_stopped(log)

    if stopped is True:
        verdict = "blocked"
    elif stopped is False:
        verdict = "passed"
    else:
        content = _content_from_response(response)
        verdict = "blocked" if _guess_blocked_from_content(content) else "passed"

    raw_text, cot = extract_raw_response_for_log(response)
    if not raw_text:
        raw_text = _content_from_response(response)

    return {
        "verdict": verdict,
        "latency_ms": latency_s * 1000.0,
        "raw_response": response,
        "raw_text": raw_text,
        "reasoning_trace": cot,
        "log": log,
    }


def confidence_from_log(log: Any) -> Optional[float]:
    """Return a confidence score if present in rail metadata; else None."""
    if log is None:
        return None
    for rail in getattr(log, "activated_rails", None) or []:
        info = getattr(rail, "additional_info", None)
        if isinstance(info, dict):
            for key in ("confidence", "confidence_score", "score"):
                if key in info and isinstance(info[key], (int, float)):
                    return float(info[key])
    return None
