"""Shared OpenAI-Chat-Completions-compatible HTTP client.

Generic OpenAI-Chat-Completions-compatible HTTP call (one POST, JSON body,
Bearer auth) so any compatible endpoint works: OpenAI, OpenRouter, Groq,
Together, self-hosted Ollama/vLLM, DeepSeek — no provider SDK, no new
dependency.
"""

from __future__ import annotations

import json
from typing import Mapping

import requests

LLM_TIMEOUT = 60  # completions run far longer than the DEFAULT_TIMEOUT GETs

# Reasoning-capable models (DeepSeek reasoner/R1-style, o1-style, etc.) spend
# part of this same budget on a hidden chain-of-thought before ever emitting
# visible content — a low cap can exhaust itself entirely on reasoning and
# come back with finish_reason="length" and an empty `content`. 2000 leaves
# headroom for that without meaningfully changing cost for plain chat models.
MAX_RESPONSE_TOKENS = 2000


def resolve_endpoint(env: Mapping[str, str]) -> tuple[str, str]:
    # `or default`, not `.get(key, default)`: GitHub Actions sets the env var
    # to an empty string (not absent) when a referenced `vars.X` doesn't
    # exist in the repo, and `.get` only falls back on a missing key.
    base_url = (env.get("LLM_BASE_URL") or "https://api.openai.com/v1").strip()
    model = (env.get("LLM_MODEL") or "gpt-4o-mini").strip()
    return base_url, model


def resolve_extra_body(env: Mapping[str, str]) -> dict:
    """Optional provider-specific request-body keys from LLM_EXTRA_BODY.

    e.g. '{"thinking": {"type": "disabled"}}' turns off DeepSeek-V4
    thinking mode. Must be a JSON object; empty or invalid values are
    ignored (a broken Variable must never fail the build). Core keys
    (model/messages/max_tokens/response_format) always win over these.
    """
    raw = (env.get("LLM_EXTRA_BODY") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        print("[llm] LLM_EXTRA_BODY ignored: not a JSON object")
        return {}
    return parsed


def post_chat(base_url: str, api_key: str, model: str, messages: list[dict],
              session: requests.Session, *, json_mode: bool = False,
              max_tokens: int = MAX_RESPONSE_TOKENS,
              extra_body: dict | None = None) -> str:
    body = {**(extra_body or {}), "model": model, "messages": messages,
            "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    resp = session.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json=body,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    choice = resp.json()["choices"][0]
    content = (choice.get("message") or {}).get("content") or ""
    if not content.strip():
        # Surfaces as a clear ValueError instead of a downstream
        # JSONDecodeError("Expecting value: line 1 column 1 (char 0)") when
        # extract_json is handed "" — see MAX_RESPONSE_TOKENS comment for
        # the usual cause (reasoning models truncated before real content).
        finish_reason = choice.get("finish_reason", "?")
        raise ValueError(f"empty completion content (finish_reason={finish_reason})")
    return content


def extract_json(content: str) -> dict:
    # Defensive unwrap: some OpenAI-compatible providers accept
    # response_format but still wrap output in a ```json fence or add a
    # leading/trailing sentence.
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return json.loads(text)
