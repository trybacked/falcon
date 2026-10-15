from __future__ import annotations

import pytest

from falcon.citations import CitationError, EvidenceIndex, validate_citations
from falcon.models import ActionStep, CaptureEvent, EventType, FrameRef


def _event(**kwargs: object) -> CaptureEvent:
    base = {
        "event_id": "e1",
        "ts": 0.0,
        "type": EventType.PRESS,
        "app": "App",
    }
    base.update(kwargs)
    return CaptureEvent(**base)  # type: ignore[arg-type]


def _frame(**kwargs: object) -> FrameRef:
    base = {"frame_id": "f1", "path": "/p.jpg", "ts": 0.0, "phash": "abc"}
    base.update(kwargs)
    return FrameRef(**base)  # type: ignore[arg-type]


def test_from_session_collects_ids() -> None:
    index = EvidenceIndex.from_session(
        [_event(event_id="e1"), _event(event_id="e2")],
        [_frame(frame_id="f1")],
    )
    assert index.events == frozenset({"e1", "e2"})
    assert index.frames == frozenset({"f1"})


def test_from_session_accepts_none() -> None:
    index = EvidenceIndex.from_session(None, None)
    assert index.events == frozenset()
    assert index.frames == frozenset()


def test_from_session_rejects_empty_event_id() -> None:
    with pytest.raises(ValueError, match="event_id"):
        EvidenceIndex.from_session([_event(event_id="")], [])


def test_from_session_rejects_empty_frame_id() -> None:
    with pytest.raises(ValueError, match="frame_id"):
        EvidenceIndex.from_session([], [_frame(frame_id="")])


def test_validate_citations_passes() -> None:
    index = EvidenceIndex.from_session([_event(event_id="e1")], [_frame(frame_id="f1")])
    steps = [
        ActionStep(
            step_id="S001",
            description="x",
            app="App",
            evidence_events=["e1"],
            evidence_frames=["f1"],
        )
    ]
    validate_citations(steps, index)


def test_validate_citations_unknown_event() -> None:
    index = EvidenceIndex.from_session([_event(event_id="e1")], [])
    steps = [
        ActionStep(
            step_id="S002",
            description="x",
            app="App",
            evidence_events=["missing"],
            evidence_frames=[],
        )
    ]
    with pytest.raises(CitationError) as exc:
        validate_citations(steps, index)
    err = exc.value
    assert err.step_id == "S002"
    assert err.kind == "event"
    assert err.citation_id == "missing"


def test_validate_citations_unknown_frame() -> None:
    index = EvidenceIndex.from_session([], [_frame(frame_id="f1")])
    steps = [
        ActionStep(
            step_id="S003",
            description="x",
            app="App",
            evidence_events=[],
            evidence_frames=["ghost"],
        )
    ]
    with pytest.raises(CitationError) as exc:
        validate_citations(steps, index)
    assert exc.value.kind == "frame"
    assert exc.value.citation_id == "ghost"
