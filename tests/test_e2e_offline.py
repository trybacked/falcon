from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from falcon.analyze import run_analyze, steps_to_json
from falcon.citations import EvidenceIndex, validate_citations
from falcon.config import OutputConfig
from falcon.distill import run_distill
from falcon.ingest import ingest_path
from falcon.layout import SessionLayout
from falcon.models import EventType, FrameRef
from falcon.scrub import PATTERNS, Scrubber
from falcon.segment import coalesce_value_changes

_EMAIL = PATTERNS[0][1]
_FISCAL = PATTERNS[2][1]


def _ingest(layout: SessionLayout, fixture: Path) -> None:
    layout.trace_raw.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")


@pytest.mark.usefixtures("block_network")
def test_offline_pipeline(
    tmp_path: Path,
    synthetic_trace_path: Path,
    fake_llm,
) -> None:
    layout = SessionLayout.create(str(tmp_path), "pipeline")
    _ingest(layout, synthetic_trace_path)

    scrubber = Scrubber()
    raw = ingest_path(layout.trace_raw)
    scrubbed = [scrubber.scrub_event(e) for e in raw]
    layout.trace.write_text("\n".join(e.to_json() for e in scrubbed), encoding="utf-8")

    trace_text = layout.trace.read_text(encoding="utf-8")
    assert not _EMAIL.search(trace_text)
    assert not _FISCAL.search(trace_text)
    assert "[EMAIL-" in trace_text

    coalesced = coalesce_value_changes([e for e in scrubbed if e.type != EventType.FRAME])
    email_storms = [
        e for e in coalesced if e.type == EventType.VALUE_CHANGE and e.target == "Email"
    ]
    assert len(email_storms) == 1
    assert coalesced[2].event_id == "E-000005"

    steps = run_analyze(coalesced)
    frames: list[FrameRef] = []
    validate_citations(steps, EvidenceIndex.from_session(scrubbed, frames))
    layout.analysis.write_text(steps_to_json(steps), encoding="utf-8")

    output = OutputConfig(language="it")
    playbook, prop_yaml, cq_yaml = run_distill(steps, fake_llm, output)
    layout.playbook.write_text(playbook, encoding="utf-8")
    layout.ontology.write_text(prop_yaml, encoding="utf-8")
    layout.questions.write_text(cq_yaml, encoding="utf-8")

    assert layout.trace.is_file()
    assert layout.analysis.is_file()
    assert layout.playbook.is_file()
    assert layout.ontology.is_file()
    assert layout.questions.is_file()

    assert len(steps) >= 8
    assert "# Playbook" in playbook
    assert "E-000001" in playbook
    assert "object_type" in prop_yaml or "UserAction" in prop_yaml
    assert "question" in cq_yaml.lower() or "Quali" in cq_yaml

    assert len(fake_llm.prompts) == 1
    joined_prompts = "\n".join(fake_llm.prompts)
    assert "F-000001" not in joined_prompts
    assert "frame" not in joined_prompts.lower()

    loaded = json.loads(layout.analysis.read_text(encoding="utf-8"))
    assert all(re.fullmatch(r"S\d{3}", s["step_id"]) for s in loaded)


@pytest.mark.usefixtures("block_network")
def test_offline_pipeline_with_ingested_fixture(
    ingested_session: SessionLayout,
    fake_llm,
) -> None:
    layout = ingested_session
    scrubber = Scrubber()
    scrubbed = [scrubber.scrub_event(e) for e in ingest_path(layout.trace_raw)]
    events = coalesce_value_changes([e for e in scrubbed if e.type != EventType.FRAME])
    steps = run_analyze(events)
    validate_citations(steps, EvidenceIndex.from_session(scrubbed, []))
    run_distill(steps, fake_llm, OutputConfig())
    assert fake_llm.prompts
