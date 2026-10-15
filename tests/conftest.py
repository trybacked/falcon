from __future__ import annotations

import json
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from falcon.layout import SessionLayout


@dataclass
class FakeTextCompletion:
    """Records prompts and returns deterministic JSON for distill."""

    prompts: list[str] = field(default_factory=list)
    responses: list[str] = field(default_factory=list)

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.responses:
            return self.responses.pop(0)
        return _default_distill_json(prompt)


def _default_distill_json(prompt: str) -> str:
    step_ids = re.findall(r'"step_id":\s*"(S\d{3})"', prompt)
    if not step_ids:
        step_ids = ["S001"]
    primary = step_ids[0]
    return json.dumps(
        {
            "ontology_proposals": [
                {
                    "kind": "object_type",
                    "name": "UserAction",
                    "description": "Passo osservato nel trace",
                    "evidence": [primary],
                }
            ],
            "competency_questions": [
                {
                    "question": "In quali applicazioni opera l'utente?",
                    "rationale": "Derivato dagli step del trace",
                    "evidence_steps": step_ids[: min(2, len(step_ids))],
                }
            ],
        },
        ensure_ascii=False,
    )


@pytest.fixture
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _deny(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network disabled in offline tests")

    monkeypatch.setattr(socket.socket, "connect", _deny)


@pytest.fixture
def fake_llm() -> FakeTextCompletion:
    return FakeTextCompletion()


@pytest.fixture
def synthetic_trace_path() -> Path:
    return Path(__file__).parent / "fixtures" / "synthetic_trace.jsonl"


@pytest.fixture
def ingested_session(tmp_path: Path, synthetic_trace_path: Path) -> SessionLayout:
    layout = SessionLayout.create(str(tmp_path), "e2e-offline")
    layout.trace_raw.write_text(synthetic_trace_path.read_text(encoding="utf-8"), encoding="utf-8")
    layout.manifest.write_text('{"session_id": "e2e-offline", "consent": true}', encoding="utf-8")
    return layout
