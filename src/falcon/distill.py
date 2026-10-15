from __future__ import annotations

import json

import yaml

from falcon.config import OutputConfig
from falcon.llm import TextCompletion, extract_json
from falcon.models import ActionStep, CompetencyQuestion, OntologyProposal


def playbook_from_steps(steps: list[ActionStep]) -> str:
    lines = ["# Playbook", ""]
    for i, s in enumerate(steps, 1):
        lines.append(f"## {i}. {s.description}")
        lines.append(f"\n*Evidence: {', '.join(s.evidence_events)}*\n")
    return "\n".join(lines)


def distill_prompt(steps: list[ActionStep], language: str) -> str:
    payload = json.dumps(
        [{"step_id": s.step_id, "description": s.description, "app": s.app} for s in steps],
        ensure_ascii=False,
    )
    return f"""From these actions, language {language}, return JSON only:
{{"ontology_proposals":[{{"kind":"object_type"|"link_type","name","description","evidence"}}],
 "competency_questions":[{{"question","rationale","evidence_steps"}}]}}
evidence / evidence_steps must cite step_id from input.

ACTIONS:
{payload}
"""


def run_distill(
    steps: list[ActionStep],
    client: TextCompletion,
    output: OutputConfig,
) -> tuple[str, str, str]:
    playbook_md = playbook_from_steps(steps)
    data = extract_json(client.complete(distill_prompt(steps, output.language)))
    proposals = [OntologyProposal(**p) for p in data.get("ontology_proposals", [])]
    questions = [CompetencyQuestion(**q) for q in data.get("competency_questions", [])]
    prop_yaml = yaml.safe_dump([p.__dict__ for p in proposals], allow_unicode=True, sort_keys=False)
    cq_yaml = yaml.safe_dump([q.__dict__ for q in questions], allow_unicode=True, sort_keys=False)
    return playbook_md, prop_yaml, cq_yaml
