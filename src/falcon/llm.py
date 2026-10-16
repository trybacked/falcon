from __future__ import annotations

import json
import os
from typing import Any, Protocol, cast

import httpx

from falcon.config import LlmConfig


class TextCompletion(Protocol):
    def complete(self, prompt: str) -> str: ...


class OpenAIClient:
    def __init__(self, cfg: LlmConfig, api_key: str, client: httpx.Client | None = None) -> None:
        self._cfg = cfg
        self._key = api_key
        self._http = client or httpx.Client(timeout=cfg.timeout_s)

    def complete(self, prompt: str) -> str:
        r = self._http.post(
            f"{self._cfg.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self._key}"},
            json={
                "model": self._cfg.model,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        payload = r.json()
        content = payload["choices"][0]["message"]["content"]
        return str(content)


def build_client(cfg: LlmConfig) -> OpenAIClient:
    key = os.environ.get(cfg.api_key_env) or os.environ.get("VERCEL_OIDC_TOKEN", "")
    if not key:
        raise RuntimeError(f"set {cfg.api_key_env} or VERCEL_OIDC_TOKEN")
    return OpenAIClient(cfg, key)


def extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM response contains no JSON object")
    return cast(dict[str, Any], json.loads(text[start : end + 1]))
