"""LLM transport (Adapter) for FREE providers – nothing else. Prompting, guardrails and fallbacks live in `detection.assistant`.

All providers expose an OpenAI-compatible /chat/completions endpoint:
  gemini  Google AI Studio free key   groq  Groq free key   ollama  local, no key, no network
  custom  ANY OpenAI-compatible service (OpenAI, OpenRouter, Together, Azure, vLLM, LM Studio …): set LLM_BASE_URL and LLM_MODEL (+ LLM_API_KEY)
"""
from __future__ import annotations

import time

import httpx

PROVIDERS = {"gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.5-flash-lite"),
             "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"), "ollama": ("http://localhost:11434/v1", "llama3.2"),
             "custom": (None, None)}   # custom: base URL and model must come from the settings


class LLMUnavailable(Exception):
    """No provider configured, or the call failed – callers fall back to the deterministic path."""


def provider_of(settings: dict) -> str:
    p = (settings.get("provider") or "none").lower()
    return p if p in PROVIDERS else "none"


def chat(messages: list[dict], settings: dict, transport: httpx.BaseTransport | None = None, max_tokens: int = 700) -> str:
    provider = provider_of(settings)
    if provider == "none":
        raise LLMUnavailable("no provider configured")
    base, model = PROVIDERS[provider]
    base_url, model = settings.get("base_url") or base, settings.get("model") or model
    if not base_url or not model:
        raise LLMUnavailable("custom provider needs LLM_BASE_URL and LLM_MODEL")
    body = {"model": model, "temperature": 0, "max_tokens": max_tokens, "messages": messages}
    headers = {"Authorization": f"Bearer {settings['api_key']}"} if settings.get("api_key") else {}
    try:
        with httpx.Client(timeout=25, transport=transport) as client:
            for pause in (3, 8, None):
                r = client.post(f"{base_url.rstrip('/')}/chat/completions", json=body, headers=headers)
                if r.status_code in (429, 503) and pause:   # free tiers rate-limit / briefly overload: wait and retry
                    time.sleep(pause)
                    continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:   # network, HTTP status, malformed body – all equivalent for the caller
        raise LLMUnavailable(f"{type(e).__name__}") from e
