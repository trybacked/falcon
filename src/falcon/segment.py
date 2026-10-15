from __future__ import annotations

import json

from falcon.models import CaptureEvent, EventType


def segment_id(index: int) -> str:
    """Stable id for the nth task segment (0-based)."""
    return f"seg-{index:03d}"


def _event_type(ev: CaptureEvent) -> EventType | str:
    raw = ev.type
    if isinstance(raw, EventType):
        return raw
    try:
        return EventType(raw)
    except ValueError:
        return raw


def _is_type(ev: CaptureEvent, kind: EventType) -> bool:
    return _event_type(ev) == kind


def _same_value_change_target(a: CaptureEvent, b: CaptureEvent) -> bool:
    return a.app == b.app and a.window == b.window and a.target == b.target


def coalesce_value_changes(events: list[CaptureEvent]) -> list[CaptureEvent]:
    out: list[CaptureEvent] = []
    for ev in events:
        if (
            out
            and _is_type(ev, EventType.VALUE_CHANGE)
            and _is_type(out[-1], EventType.VALUE_CHANGE)
            and _same_value_change_target(out[-1], ev)
        ):
            out[-1] = ev
        else:
            out.append(ev)
    return out


def _starts_new_segment(prev: CaptureEvent, ev: CaptureEvent, idle_gap_s: float) -> bool:
    if (ev.ts - prev.ts) > idle_gap_s:
        return True
    if _is_type(ev, EventType.APP_ACTIVATE):
        return True
    if ev.app != prev.app:
        return True
    return False


def segment_tasks(events: list[CaptureEvent], idle_gap_s: float) -> list[list[CaptureEvent]]:
    if idle_gap_s < 0:
        raise ValueError("idle_gap_s must be non-negative")
    if not events:
        return []
    groups: list[list[CaptureEvent]] = [[events[0]]]
    for prev, ev in zip(events, events[1:], strict=False):
        if ev.ts < prev.ts:
            raise ValueError("events must be sorted by ts")
        if _starts_new_segment(prev, ev, idle_gap_s):
            groups.append([ev])
        else:
            groups[-1].append(ev)
    return groups


def segments_to_json(groups: list[list[CaptureEvent]]) -> str:
    payload = [
        {"segment_id": segment_id(i), "event_ids": [e.event_id for e in group]}
        for i, group in enumerate(groups)
    ]
    return json.dumps(payload, ensure_ascii=False, indent=1)
