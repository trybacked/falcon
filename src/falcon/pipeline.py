from __future__ import annotations

import json

from falcon.analyze import run_analyze, steps_to_json
from falcon.citations import EvidenceIndex, validate_citations
from falcon.config import AppConfig
from falcon.ingest import ingest_path
from falcon.layout import SessionLayout
from falcon.log import LOG
from falcon.models import ActionStep, CaptureEvent, EventType, FrameRef
from falcon.scrub import Scrubber
from falcon.segment import coalesce_value_changes, segment_tasks, segments_to_json
from falcon.validate import require_trace_raw, validate_events, validate_manifest


def normalize_and_write_raw(layout: SessionLayout) -> list[CaptureEvent]:
    validate_manifest(layout)
    require_trace_raw(layout)
    events = ingest_path(layout.trace_raw)
    validate_events(events)
    if not events:
        raise ValueError("no events after ingest")
    layout.trace_raw.write_text("\n".join(e.to_json() for e in events) + "\n", encoding="utf-8")
    LOG.info("ingested %s events -> %s", len(events), layout.trace_raw)
    return events


def run_analyze_pipeline(layout: SessionLayout, cfg: AppConfig) -> list[ActionStep]:
    validate_manifest(layout)
    require_trace_raw(layout)

    scrubber = Scrubber()
    raw = ingest_path(layout.trace_raw)
    scrubbed = scrubber.scrub_events(raw)
    layout.trace.write_text("\n".join(e.to_json() for e in scrubbed), encoding="utf-8")

    events = coalesce_value_changes([e for e in scrubbed if e.type != EventType.FRAME])
    groups = segment_tasks(events, cfg.capture.idle_gap_s)
    layout.segments.write_text(segments_to_json(groups), encoding="utf-8")

    steps = run_analyze(events)
    frames = (
        [FrameRef(**x) for x in json.loads(layout.frames_index.read_text(encoding="utf-8"))]
        if layout.frames_index.is_file()
        else []
    )
    validate_citations(steps, EvidenceIndex.from_session(scrubbed, frames))
    layout.analysis.write_text(steps_to_json(steps), encoding="utf-8")
    LOG.info(
        "%s steps, %s segments -> %s",
        len(steps),
        len(groups),
        layout.analysis,
    )
    return steps
