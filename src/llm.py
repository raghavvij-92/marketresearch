"""
Minimal multi-provider LLM client (Gemini / OpenAI-compatible / Anthropic)
implemented over plain REST so the project stays dependency-light.

The first provider with a configured API key is used (or LLM_PROVIDER pins
one). Calls retry with exponential backoff on transient failures.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from src.config import Config

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self.provider = config.resolved_llm_provider()

    @property
    def available(self) -> bool:
        return self.provider is not None

    @property
    def model_name(self) -> str:
        return {
            "gemini": self.config.gemini_model,
            "openai": self.config.openai_model,
            "anthropic": self.config.anthropic_model,
            None: "rule-based (no LLM key configured)",
        }[self.provider]

    def generate(self, prompt: str, system: str = "") -> str:
        """Return the model's text response; raises LLMError after all retries fail."""
        if not self.available:
            raise LLMError("no LLM API key configured")

        last_error: Optional[Exception] = None
        for attempt in range(1, self.config.llm_max_retries + 1):
            try:
                if self.provider == "gemini":
                    return self._call_gemini(prompt, system)
                if self.provider == "openai":
                    return self._call_openai(prompt, system)
                return self._call_anthropic(prompt, system)
            except Exception as exc:
                last_error = exc
                wait = 2**attempt
                logger.warning(
                    "LLM call attempt %d/%d failed (%s); retrying in %ds",
                    attempt,
                    self.config.llm_max_retries,
                    exc,
                    wait,
                )
                if attempt < self.config.llm_max_retries:
                    time.sleep(wait)
        raise LLMError(f"LLM call failed after retries: {last_error}")

    # ------------------------------------------------------------------ gemini
    def _call_gemini(self, prompt: str, system: str) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.config.gemini_model}:generateContent"
        )
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.config.llm_temperature,
                "maxOutputTokens": self.config.llm_max_tokens,
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        resp = requests.post(
            url,
            params={"key": self.config.gemini_api_key},
            json=body,
            timeout=self.config.llm_timeout,
        )
        _raise_for_status(resp)
        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected Gemini response shape: {data}") from exc

    # ------------------------------------------------------------------ openai
    def _call_openai(self, prompt: str, system: str) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            f"{self.config.openai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.config.openai_api_key}"},
            json={
                "model": self.config.openai_model,
                "messages": messages,
                "temperature": self.config.llm_temperature,
                "max_tokens": self.config.llm_max_tokens,
            },
            timeout=self.config.llm_timeout,
        )
        _raise_for_status(resp)
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected OpenAI response shape: {data}") from exc

    # --------------------------------------------------------------- anthropic
    def _call_anthropic(self, prompt: str, system: str) -> str:
        body = {
            "model": self.config.anthropic_model,
            "max_tokens": self.config.llm_max_tokens,
            "temperature": self.config.llm_temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.config.anthropic_api_key,
                "anthropic-version": "2023-06-01",
            },
            json=body,
            timeout=self.config.llm_timeout,
        )
        _raise_for_status(resp)
        data = resp.json()
        try:
            return "".join(
                block.get("text", "") for block in data["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise LLMError(f"unexpected Anthropic response shape: {data}") from exc


def _raise_for_status(resp: requests.Response) -> None:
    if resp.status_code != 200:
        raise LLMError(f"HTTP {resp.status_code}: {resp.text[:500]}")
