from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from typing import Any

import yaml

from falcon.config import OutputConfig
from falcon.llm import TextCompletion, extract_json
from falcon.models import ActionStep, ProcessReport, dataclass_from_dict
from falcon.report_md import render_report

_SCHEMA: dict[str, Any] = {
    "process": {
        "name": "short process name",
        "summary": "executive summary (3-6 sentences): what the operator does, why, outcome",
        "business_goal": "business outcome the process serves",
        "scope": "what is covered / not covered by the observed session",
        "actors": [{"role": "...", "responsibilities": "..."}],
        "systems": [
            {
                "name": "...",
                "purpose": "role of this system in the process",
                "evidence_steps": ["S001"],
            }
        ],
    },
    "phases": [
        {
            "phase_id": "P01",
            "name": "phase name",
            "objective": "what this phase achieves",
            "narrative": "detailed narrative (4-8 sentences): sequence, context, handoffs, rules",
            "actor_role": "role performing the phase",
            "systems": ["system names used"],
            "inputs": ["information/artifacts required to start"],
            "outputs": ["artifacts/state produced"],
            "actions": [
                {"description": "one observable action, business wording", "step_ids": ["S001"]}
            ],
            "decision_points": ["where the operator chooses between alternatives and why"],
            "data_entities": ["business objects touched (customer, email, ticket, invoice...)"],
            "pain_points": ["friction observed in this phase"],
            "evidence_steps": ["all step_ids covered by this phase"],
        }
    ],
    "pain_points": [
        {
            "title": "...",
            "description": "...",
            "impact": "time/quality/risk/compliance",
            "evidence_steps": ["S001"],
        }
    ],
    "opportunities": [
        {
            "title": "...",
            "description": "what to build or change",
            "type": "automation|integration|ai_assist|process_redesign|data_quality",
            "value_hypothesis": "expected business value and how to measure it",
            "effort": "low|medium|high",
            "priority": "P0|P1|P2",
            "evidence_steps": ["S001"],
        }
    ],
    "ontology_proposals": [
        {
            "kind": "object_type|link_type|property",
            "name": "...",
            "description": "...",
            "evidence": ["S001"],
        }
    ],
    "competency_questions": [{"question": "...", "rationale": "...", "evidence_steps": ["S001"]}],
    "open_questions": [
        {"question": "...", "audience": "process owner|IT|operator|compliance", "why": "..."}
    ],
    "assumptions": ["assumptions made where evidence is weak"],
}


def _steps_payload(steps: list[ActionStep]) -> str:
    return json.dumps(
        [{"step_id": s.step_id, "description": s.description, "app": s.app} for s in steps],
        ensure_ascii=False,
    )


def distill_prompt(steps: list[ActionStep], language: str) -> str:
    schema = json.dumps(_SCHEMA, indent=2, ensure_ascii=False)
    return f"""You are a Forward Deployed Engineer and Deployment Strategist analysing a
consent-based UI shadowing session recorded inside an enterprise. The input is an ordered list of
low-level observed actions (app switches, clicks, typed values; PII already redacted as [EMAIL-1]).

Your task: reconstruct the BUSINESS PROCESS the operator is executing and produce a structured,
detailed discovery report that an FDE can use to design an ontology and integrations, and that a
Deployment Strategist can use to prioritise value and plan rollout.

Rules:
- Write every free-text field in language: {language}. Keep JSON keys and enum values in English.
- Be thorough and verbose in narratives, objectives, rationales and value hypotheses.
- Group ALL steps into ordered phases; every step_id must appear in exactly one phase's
  evidence_steps. Steps that belong to the recording tooling itself (IDE, terminal, the recorder)
  go in a dedicated phase named "Fuori perimetro / tooling" and are excluded from opportunities.
- Use business wording (what the operator achieves), not UI wording, in action descriptions;
  keep the step_ids as the audit trail.
- Only cite step_ids present in the input. Never invent systems, data or actors not supported by
  evidence; when inferring, state it in assumptions.
- Ontology: propose object types, link types and key properties grounded in the observed data
  entities. Competency questions: what the organisation should be able to answer with that ontology.
- Open questions: concrete questions to ask stakeholders to close gaps in understanding.
- Return ONLY a JSON object matching this schema (no prose before or after):
{schema}

OBSERVED ACTIONS:
{_steps_payload(steps)}
"""


def _known_only(ids: list[str], known: frozenset[str]) -> list[str]:
    return [i for i in ids if i in known]


def _sanitize_citations(report: ProcessReport, steps: list[ActionStep]) -> ProcessReport:
    known = frozenset(s.step_id for s in steps)
    phases = [
        replace(
            p,
            actions=[replace(a, step_ids=_known_only(a.step_ids, known)) for a in p.actions],
            evidence_steps=_known_only(p.evidence_steps, known),
        )
        for p in report.phases
    ]
    return replace(
        report,
        process=replace(
            report.process,
            systems=[
                replace(s, evidence_steps=_known_only(s.evidence_steps, known))
                for s in report.process.systems
            ],
        ),
        phases=phases,
        pain_points=[
            replace(p, evidence_steps=_known_only(p.evidence_steps, known))
            for p in report.pain_points
        ],
        opportunities=[
            replace(o, evidence_steps=_known_only(o.evidence_steps, known))
            for o in report.opportunities
        ],
        ontology_proposals=[
            replace(o, evidence=_known_only(o.evidence, known)) for o in report.ontology_proposals
        ],
        competency_questions=[
            replace(q, evidence_steps=_known_only(q.evidence_steps, known))
            for q in report.competency_questions
        ],
    )


def parse_report(data: dict[str, Any], steps: list[ActionStep]) -> ProcessReport:
    return _sanitize_citations(dataclass_from_dict(ProcessReport, data), steps)


def playbook_from_steps(steps: list[ActionStep]) -> str:
    lines = ["# Playbook", ""]
    for i, s in enumerate(steps, 1):
        lines.append(f"## {i}. {s.description}")
        lines.append(f"\n*Evidence: {', '.join(s.evidence_events)}*\n")
    return "\n".join(lines)


def _yaml(items: list[Any]) -> str:
    return yaml.safe_dump([asdict(i) for i in items], allow_unicode=True, sort_keys=False)


@dataclass(frozen=True)
class DistillOutputs:
    playbook_md: str
    report_md: str
    ontology_yaml: str
    questions_yaml: str
    report: ProcessReport


def run_distill(
    steps: list[ActionStep],
    client: TextCompletion,
    output: OutputConfig,
    session_id: str = "",
) -> DistillOutputs:
    data = extract_json(client.complete(distill_prompt(steps, output.language)))
    report = parse_report(data, steps)
    return DistillOutputs(
        playbook_md=playbook_from_steps(steps),
        report_md=render_report(report, steps, session_id),
        ontology_yaml=_yaml(report.ontology_proposals),
        questions_yaml=_yaml(report.competency_questions),
        report=report,
    )
