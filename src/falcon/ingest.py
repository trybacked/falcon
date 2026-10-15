from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from falcon.models import (
    AxPayload,
    CaptureEvent,
    EventType,
    MousePayload,
    RawTraceLine,
    is_native_capture_event,
)

_PRESS_AX_ROLES = frozenset(
    {"AXButton", "AXLink", "AXMenuItem", "AXPopUpButton", "AXCheckBox", "AXRadioButton"}
)
_SESSION_KINDS = frozenset({"session.started", "session.ended"})


@dataclass
class IngestState:
    app: str = ""
    window: str | None = None


def ingest_jsonl(text: str) -> list[CaptureEvent]:
    state = IngestState()
    events: list[CaptureEvent] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        events.extend(parse_jsonl_line(line, state))
    return [_coerce_event_type(e) for e in assign_event_ids(events)]


def ingest_path(path: Path) -> list[CaptureEvent]:
    return ingest_jsonl(path.read_text(encoding="utf-8"))


def parse_jsonl_line(line: str, state: IngestState | None = None) -> list[CaptureEvent]:
    ctx = state if state is not None else IngestState()
    obj = json.loads(line)
    if not isinstance(obj, dict):
        raise ValueError("each JSONL row must be an object")
    if is_native_capture_event(obj):
        ev = CaptureEvent.from_json(line)
        if ev.app:
            ctx.app = ev.app
        if ev.window:
            ctx.window = ev.window
        return [ev]
    raw = RawTraceLine.from_dict(obj)
    return raw_to_events(raw, ctx)


def raw_to_events(raw: RawTraceLine, state: IngestState) -> list[CaptureEvent]:
    if raw.kind in _SESSION_KINDS:
        return []
    app = raw.app or state.app
    window = raw.window if raw.window is not None else state.window

    if raw.kind == "window.changed":
        events: list[CaptureEvent] = []
        if app and app != state.app:
            events.append(_event(raw.timestamp, EventType.APP_ACTIVATE, app, window))
        elif window and window != state.window:
            events.append(_event(raw.timestamp, EventType.WINDOW_CHANGE, app, window))
        if app:
            state.app = app
        if window is not None:
            state.window = window
        return events

    if raw.kind == "mouse.click":
        target = _mouse_target(raw.mouse)
        return [_event(raw.timestamp, EventType.PRESS, app, window, target=target)]

    if raw.kind == "keyboard.text_input":
        text = raw.keyboard.text if raw.keyboard else None
        return [
            _event(
                raw.timestamp,
                EventType.VALUE_CHANGE,
                app,
                window,
                target="keyboard",
                value=text,
            )
        ]

    if raw.kind == "keyboard.submit":
        text = raw.keyboard.text if raw.keyboard else None
        return [
            _event(
                raw.timestamp,
                EventType.VALUE_CHANGE,
                app,
                window,
                target="keyboard.submit",
                value=text,
            )
        ]

    if raw.ax is not None or raw.kind.startswith("ax."):
        return _ax_events(raw, app, window)

    return []


def _coerce_event_type(ev: CaptureEvent) -> CaptureEvent:
    if isinstance(ev.type, EventType):
        return ev
    return replace(ev, type=EventType(str(ev.type)))


def assign_event_ids(events: list[CaptureEvent], start: int = 0) -> list[CaptureEvent]:
    n = start
    out: list[CaptureEvent] = []
    for ev in events:
        if ev.event_id:
            if ev.event_id.startswith("E-"):
                try:
                    n = max(n, int(ev.event_id[2:]))
                except ValueError:
                    pass
            out.append(ev)
            continue
        n += 1
        out.append(replace(ev, event_id=f"E-{n:06d}"))
    return out


def _ax_snapshot(ax: AxPayload) -> str | None:
    parts = [p for p in (ax.role, ax.title, ax.value) if p]
    return " · ".join(parts) if parts else None


def _ax_events(raw: RawTraceLine, app: str, window: str | None) -> list[CaptureEvent]:
    ax = raw.ax or AxPayload()
    target = ax.title or ax.role or "ax"
    ax_text = _ax_snapshot(ax)
    kind = raw.kind
    if kind in {"ax.value_changed", "ax.value_change"} or ax.value is not None:
        return [
            _event(
                raw.timestamp,
                EventType.VALUE_CHANGE,
                app,
                window,
                target=target,
                value=ax.value,
                ax_text=ax_text,
            )
        ]
    et = EventType.PRESS if ax.role in _PRESS_AX_ROLES else EventType.SELECT
    return [_event(raw.timestamp, et, app, window, target=target, ax_text=ax_text)]


def _mouse_target(mouse: MousePayload | None) -> str:
    if mouse is None:
        return "mouse"
    if mouse.x is not None and mouse.y is not None:
        return f"@{mouse.x},{mouse.y}"
    if mouse.button:
        return mouse.button
    return "mouse"


def _event(
    ts: float,
    et: EventType,
    app: str,
    window: str | None,
    *,
    target: str | None = None,
    value: str | None = None,
    ax_text: str | None = None,
    frame_id: str | None = None,
) -> CaptureEvent:
    return CaptureEvent(
        event_id="",
        ts=ts,
        type=et,
        app=app,
        window=window,
        target=target,
        value=value,
        ax_text=ax_text,
        frame_id=frame_id,
    )
