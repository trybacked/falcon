"""One-off distill JSON benchmark against Vercel AI Gateway (reads AI_GATEWAY_API_KEY from env)."""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace

import httpx

from falcon.config import load_config
from falcon.distill import distill_prompt, extract_json
from falcon.llm import OpenAIClient
from falcon.models import ActionStep

MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4.5",
    "anthropic/claude-sonnet-4.6",
    "deepseek/deepseek-v4-flash",
    "zai/glm-5.3",
]


def _load_prompt(session: str, n_steps: int) -> str:
    path = os.path.join("sessions", session, "analysis.json")
    steps = [ActionStep(**s) for s in json.loads(open(path, encoding="utf-8").read())]
    return distill_prompt(steps[:n_steps], "it")


def _pricing_index() -> dict[str, dict[str, str]]:
    data = httpx.get("https://ai-gateway.vercel.sh/v1/models", timeout=60).json()["data"]
    return {m["id"]: m.get("pricing") or {} for m in data}


def _cost_usd(pricing: dict[str, str], in_tok: int, out_tok: int) -> float:
    pin = float(pricing.get("input") or 0)
    pout = float(pricing.get("output") or 0)
    return in_tok * pin + out_tok * pout


def main() -> int:
    key = os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("VERCEL_OIDC_TOKEN")
    if not key:
        print("set AI_GATEWAY_API_KEY", file=sys.stderr)
        return 1

    session = os.environ.get("BENCH_SESSION", "demo")
    n_steps = int(os.environ.get("BENCH_STEPS", "8"))
    prompt = _load_prompt(session, n_steps)
    pricing_by_model = _pricing_index()
    base = load_config(None).llm

    rows: list[dict[str, object]] = []
    for model in MODELS:
        cfg = replace(base, model=model, timeout_s=240.0)
        client = OpenAIClient(cfg, key, client=httpx.Client(timeout=cfg.timeout_s))
        t0 = time.perf_counter()
        row: dict[str, object] = {"model": model}
        try:
            r = client._http.post(
                f"{cfg.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            row["time_s"] = round(time.perf_counter() - t0, 2)
            row["http"] = r.status_code
            if not r.is_success:
                row["ok"] = False
                row["error"] = r.text[:300]
                rows.append(row)
                continue
            payload = r.json()
            usage = payload.get("usage") or {}
            in_tok = int(usage.get("prompt_tokens") or 0)
            out_tok = int(usage.get("completion_tokens") or 0)
            content = str(payload["choices"][0]["message"]["content"])
            data = extract_json(content)
            pricing = pricing_by_model.get(model, {})
            cost = _cost_usd(pricing, in_tok, out_tok)
            row.update(
                {
                    "ok": True,
                    "ontology": len(data.get("ontology_proposals", [])),
                    "questions": len(data.get("competency_questions", [])),
                    "in_tok": in_tok,
                    "out_tok": out_tok,
                    "cost_usd": round(cost, 6),
                    "price_in_per_1m": round(float(pricing.get("input") or 0) * 1_000_000, 4),
                    "price_out_per_1m": round(float(pricing.get("output") or 0) * 1_000_000, 4),
                }
            )
        except Exception as exc:
            row["ok"] = False
            row["time_s"] = round(time.perf_counter() - t0, 2)
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    print(json.dumps({"summary": rows}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
