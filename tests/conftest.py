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
    half = max(1, len(step_ids) // 2)
    return json.dumps(
        {
            "process": {
                "name": "Processo di test",
                "summary": "Sessione sintetica usata nei test offline.",
                "business_goal": "Verificare la pipeline",
                "scope": "Solo eventi del fixture",
                "actors": [{"role": "Operatore", "responsibilities": "Esegue il processo"}],
                "systems": [
                    {"name": "App", "purpose": "Sistema di test", "evidence_steps": [primary]}
                ],
            },
            "phases": [
                {
                    "phase_id": "P01",
                    "name": "Preparazione",
                    "objective": "Avvio del lavoro",
                    "narrative": "Prima metà degli step.",
                    "actor_role": "Operatore",
                    "systems": ["App"],
                    "inputs": ["Richiesta"],
                    "outputs": ["Bozza"],
                    "actions": [{"description": "Apre il contesto", "step_ids": step_ids[:half]}],
                    "decision_points": [],
                    "data_entities": ["Richiesta"],
                    "pain_points": [],
                    "evidence_steps": step_ids[:half],
                },
                {
                    "phase_id": "P02",
                    "name": "Esecuzione",
                    "objective": "Completamento",
                    "narrative": "Seconda metà degli step.",
                    "actor_role": "Operatore",
                    "systems": ["App"],
                    "inputs": ["Bozza"],
                    "outputs": ["Risultato"],
                    "actions": [{"description": "Completa il lavoro", "step_ids": step_ids[half:]}],
                    "decision_points": ["Invio o salvataggio"],
                    "data_entities": ["Risultato"],
                    "pain_points": ["Passaggi manuali"],
                    "evidence_steps": step_ids[half:],
                },
            ],
            "pain_points": [
                {
                    "title": "Doppia digitazione",
                    "description": "Dati reinseriti a mano",
                    "impact": "tempo",
                    "evidence_steps": [primary, "S999"],
                }
            ],
            "opportunities": [
                {
                    "title": "Automatizzare l'inserimento",
                    "description": "Precompilare i campi",
                    "type": "automation",
                    "value_hypothesis": "Meno tempo per pratica",
                    "effort": "low",
                    "priority": "P1",
                    "evidence_steps": [primary],
                }
            ],
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
            "open_questions": [
                {"question": "Chi approva?", "audience": "process owner", "why": "Non osservato"}
            ],
            "assumptions": ["Sessione rappresentativa"],
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
