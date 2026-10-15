from __future__ import annotations

import pytest

from falcon.models import CaptureEvent, EventType
from falcon.segment import coalesce_value_changes, segment_id, segment_tasks


def _event(**kwargs: object) -> CaptureEvent:
    base = {
        "event_id": "e1",
        "ts": 0.0,
        "type": EventType.PRESS,
        "app": "App",
        "window": "W",
        "target": "T",
    }
    base.update(kwargs)
    return CaptureEvent(**base)  # type: ignore[arg-type]


def test_coalesce_consecutive_same_target() -> None:
    events = [
        _event(event_id="e1", ts=1.0, type=EventType.VALUE_CHANGE, value="a"),
        _event(event_id="e2", ts=2.0, type=EventType.VALUE_CHANGE, value="b"),
    ]
    out = coalesce_value_changes(events)
    assert len(out) == 1
    assert out[0].event_id == "e2"
    assert out[0].value == "b"


def test_coalesce_keeps_different_targets() -> None:
    events = [
        _event(event_id="e1", type=EventType.VALUE_CHANGE, target="A"),
        _event(event_id="e2", type=EventType.VALUE_CHANGE, target="B"),
    ]
    assert len(coalesce_value_changes(events)) == 2


def test_coalesce_string_value_change_type() -> None:
    events = [
        _event(event_id="e1", type="value_change", value="a"),
        _event(event_id="e2", type=EventType.VALUE_CHANGE, value="b"),
    ]
    out = coalesce_value_changes(events)
    assert len(out) == 1
    assert out[0].event_id == "e2"


def test_segment_empty() -> None:
    assert segment_tasks([], idle_gap_s=10.0) == []


def test_segment_single_event() -> None:
    assert segment_tasks([_event(ts=0.0)], idle_gap_s=10.0) == [[_event(ts=0.0)]]


def test_segment_split_on_idle_gap() -> None:
    events = [_event(event_id="e1", ts=0.0), _event(event_id="e2", ts=100.0)]
    groups = segment_tasks(events, idle_gap_s=30.0)
    assert len(groups) == 2
    assert [e.event_id for e in groups[0]] == ["e1"]
    assert [e.event_id for e in groups[1]] == ["e2"]


def test_segment_no_split_at_exact_gap() -> None:
    events = [_event(event_id="e1", ts=0.0), _event(event_id="e2", ts=30.0)]
    groups = segment_tasks(events, idle_gap_s=30.0)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_segment_split_on_app_change() -> None:
    events = [
        _event(event_id="e1", ts=0.0, app="A"),
        _event(event_id="e2", ts=1.0, app="B"),
    ]
    groups = segment_tasks(events, idle_gap_s=100.0)
    assert len(groups) == 2


def test_segment_split_on_app_activate() -> None:
    events = [
        _event(event_id="e1", ts=0.0, type=EventType.PRESS),
        _event(event_id="e2", ts=1.0, type=EventType.APP_ACTIVATE),
    ]
    groups = segment_tasks(events, idle_gap_s=100.0)
    assert len(groups) == 2


def test_segment_rejects_negative_idle_gap() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        segment_tasks([_event()], idle_gap_s=-1.0)


def test_segment_rejects_unsorted_timestamps() -> None:
    events = [_event(event_id="e1", ts=5.0), _event(event_id="e2", ts=1.0)]
    with pytest.raises(ValueError, match="sorted"):
        segment_tasks(events, idle_gap_s=10.0)


def test_segment_id_format() -> None:
    assert segment_id(0) == "seg-000"
    assert segment_id(12) == "seg-012"
