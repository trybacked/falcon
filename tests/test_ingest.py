from __future__ import annotations

import json
from pathlib import Path

from falcon.ingest import ingest_jsonl, parse_jsonl_line
from falcon.models import CaptureEvent, EventType, RawTraceLine


def test_native_trace_line_unchanged() -> None:
    line = (
        '{"event_id": "E-000001", "ts": 1000.0, "type": "app_activate", '
        '"app": "Safari", "window": null, "target": null, "value": null, "frame_id": null}'
    )
    events = ingest_jsonl(line)
    assert len(events) == 1
    assert events[0].event_id == "E-000001"
    assert events[0].type == EventType.APP_ACTIVATE
    assert events[0].app == "Safari"


def test_orr_flat_mouse_click() -> None:
    line = json.dumps(
        {"kind": "mouse.click", "ts": 10.0, "x": 100, "y": 200, "button": "left", "sessionId": "s1"}
    )
    events = ingest_jsonl(line)
    assert len(events) == 1
    ev = events[0]
    assert ev.type == EventType.PRESS
    assert ev.target == "@100,200"
    assert ev.event_id == "E-000001"


def test_orr_window_changed_app_activate() -> None:
    lines = "\n".join(
        [
            json.dumps({"kind": "window.changed", "ts": 1.0, "app": "Chrome", "window": "Tab A"}),
            json.dumps({"kind": "window.changed", "ts": 2.0, "app": "Chrome", "window": "Tab B"}),
        ]
    )
    events = ingest_jsonl(lines)
    assert [e.type for e in events] == [EventType.APP_ACTIVATE, EventType.WINDOW_CHANGE]
    assert events[0].window == "Tab A"
    assert events[1].window == "Tab B"


def test_internal_nested_ax_value_change() -> None:
    line = json.dumps(
        {
            "kind": "ax.value_changed",
            "timestamp": 5.5,
            "app": "Excel",
            "window": "Sheet1",
            "mouse": None,
            "keyboard": None,
            "ax": {"role": "AXTextField", "title": "A1", "value": "hello"},
        }
    )
    events = ingest_jsonl(line)
    assert len(events) == 1
    assert events[0].type == EventType.VALUE_CHANGE
    assert events[0].target == "A1"
    assert events[0].value == "hello"
    assert events[0].ax_text == "AXTextField · A1 · hello"


def test_session_lifecycle_skipped() -> None:
    lines = "\n".join(
        [
            json.dumps({"kind": "session.started", "ts": 0.0, "sessionId": "abc"}),
            json.dumps({"kind": "session.ended", "ts": 99.0, "sessionId": "abc"}),
        ]
    )
    assert ingest_jsonl(lines) == []


def test_mixed_native_and_orr_assigns_ids() -> None:
    native = (
        '{"event_id": "E-000003", "ts": 1.0, "type": "press", "app": "A", '
        '"window": null, "target": "OK", "value": null, "frame_id": null}'
    )
    orr = json.dumps({"kind": "mouse.click", "ts": 2.0, "x": 1, "y": 2, "app": "A"})
    events = ingest_jsonl(f"{native}\n{orr}")
    assert [e.event_id for e in events] == ["E-000003", "E-000004"]


def test_synthetic_fixture_native_compat(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "synthetic_trace.jsonl"
    ingested = ingest_jsonl(fixture.read_text(encoding="utf-8"))
    direct = [
        CaptureEvent.from_json(line)
        for line in fixture.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(ingested) == len(direct)
    for a, b in zip(ingested, direct, strict=True):
        assert a.event_id == b.event_id
        assert a.type == b.type
        assert a.app == b.app


def test_raw_trace_line_from_dict_flat() -> None:
    raw = RawTraceLine.from_dict(
        {"kind": "keyboard.text_input", "ts": 3.0, "text": "hi", "sessionId": "x"}
    )
    assert raw.keyboard is not None
    assert raw.keyboard.text == "hi"
    events = parse_jsonl_line(json.dumps({"kind": "keyboard.text_input", "ts": 3.0, "text": "hi"}))
    assert events[0].type == EventType.VALUE_CHANGE
    assert events[0].value == "hi"
