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
    out = run_distill(steps, fake_llm, output, session_id="pipeline")
    layout.playbook.write_text(out.playbook_md, encoding="utf-8")
    layout.report.write_text(out.report_md, encoding="utf-8")
    layout.ontology.write_text(out.ontology_yaml, encoding="utf-8")
    layout.questions.write_text(out.questions_yaml, encoding="utf-8")

    assert layout.trace.is_file()
    assert layout.analysis.is_file()
    assert layout.playbook.is_file()
    assert layout.report.is_file()
    assert layout.ontology.is_file()
    assert layout.questions.is_file()

    assert len(steps) >= 8
    assert "# Playbook" in out.playbook_md
    assert "E-000001" in out.playbook_md
    assert "object_type" in out.ontology_yaml or "UserAction" in out.ontology_yaml
    assert "question" in out.questions_yaml.lower() or "Quali" in out.questions_yaml

    report_md = out.report_md
    assert report_md.startswith("# Report di processo — Processo di test")
    for section in (
        "## 1. Executive summary",
        "## 4. Processo end-to-end per fasi",
        "### 4.1 Fase P01 — Preparazione",
        "### 4.2 Fase P02 — Esecuzione",
        "## 6. Opportunità di deployment",
        "## 7. Proposte di ontologia",
        "## Appendice A — Tracciabilità step → eventi",
    ):
        assert section in report_md, section
    assert "S001 (E-000001)" in report_md
    assert "S999" not in report_md
    half = len(steps) // 2
    assert f"S001–S{half:03d} ({half} step)" in report_md
    assert [p.phase_id for p in out.report.phases] == ["P01", "P02"]
    covered = {sid for p in out.report.phases for sid in p.evidence_steps}
    assert covered == {s.step_id for s in steps}

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
