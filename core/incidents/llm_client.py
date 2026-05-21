"""Anthropic and OpenAI LLM clients for incident pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from core.incidents.config import llm_model, llm_provider

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if match:
            return json.loads(match.group(0))
        raise


def complete_text(system: str, user: str, *, max_tokens: int = 2048) -> str:
    provider = llm_provider()
    model = llm_model()
    if provider == "openai":
        return _openai_complete(system, user, model=model, max_tokens=max_tokens)
    if provider == "anthropic":
        return _anthropic_complete(system, user, model=model, max_tokens=max_tokens)
    raise ValueError(f"Unsupported INCIDENT_LLM_PROVIDER: {provider!r}")


def complete_json(system: str, user: str, *, max_tokens: int = 1024) -> dict[str, Any]:
    raw = complete_text(system, user, max_tokens=max_tokens)
    return _extract_json(raw)


def _anthropic_complete(
    system: str, user: str, *, model: str, max_tokens: int
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("Install anthropic: pip install anthropic") from exc

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = []
    for block in message.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts).strip()


def _openai_complete(system: str, user: str, *, model: str, max_tokens: int) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install openai: pip install openai") from exc

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    choice = response.choices[0].message.content
    return (choice or "").strip()
