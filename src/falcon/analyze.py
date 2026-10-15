from __future__ import annotations

import json
from typing import assert_never

from falcon.models import ActionStep, CaptureEvent, EventType


def _resolve_type(e: CaptureEvent) -> EventType:
    if isinstance(e.type, EventType):
        return e.type
    return EventType(str(e.type))


def _window_phrase(window: str | None) -> str:
    return f"«{window}»" if window else "finestra attiva"


def _enrich_target(target: str | None, ax_text: str | None) -> str | None:
    if not target or not ax_text or "|" in target or ":" in target:
        return target
    parts = [p.strip() for p in ax_text.split(" · ") if p.strip()]
    if len(parts) >= 2 and target in parts:
        return f"{parts[0]}|{parts[1]}"
    return target


def format_target(target: str | None, ax_text: str | None = None) -> str:
    target = _enrich_target(target, ax_text)
    if not target:
        return "elemento"
    if target.startswith("@"):
        return target
    for sep in ("|", ":"):
        if sep in target:
            role, _, label = target.partition(sep)
            role = role.strip()
            label = label.strip()
            if label and role:
                return f"«{label}» ({role})"
            if label:
                return f"«{label}»"
            if role:
                return f"«{role}»"
    return f"«{target}»"


def _keyboard_text_input(app: str, win: str, value: str | None) -> str:
    if value:
        return f"In {app}, finestra {win}: digita «{value}»"
    return f"In {app}, finestra {win}: digita testo"


def _keyboard_submit(app: str, win: str, value: str | None) -> str:
    if value:
        return f"In {app}, finestra {win}: conferma input «{value}»"
    return f"In {app}, finestra {win}: conferma input (Invio)"


def _click_description(app: str, win: str, target: str | None, ax_text: str | None) -> str:
    formatted = format_target(target, ax_text)
    if formatted.startswith("@"):
        return f"In {app}, finestra {win}: click in {formatted}"
    return f"In {app}, finestra {win}: click su {formatted}"


def describe_event(e: CaptureEvent) -> str:
    win = _window_phrase(e.window)
    app = e.app or "applicazione"
    et = _resolve_type(e)

    match et:
        case EventType.APP_ACTIVATE:
            if e.window:
                return f"In {app}, passa alla finestra {win}"
            return f"Attiva l'applicazione {app}"
        case EventType.WINDOW_CHANGE:
            return f"In {app}, passa alla finestra {win}"
        case EventType.VALUE_CHANGE:
            if e.target == "keyboard":
                return _keyboard_text_input(app, win, e.value)
            if e.target == "keyboard.submit":
                return _keyboard_submit(app, win, e.value)
            field = format_target(e.target, e.ax_text)
            return f"In {app}, finestra {win}: imposta {field} = «{e.value}»"
        case EventType.PRESS | EventType.SELECT:
            return _click_description(app, win, e.target, e.ax_text)
        case EventType.KEYBOARD:
            return _keyboard_text_input(app, win, e.value)
        case EventType.FRAME:
            return f"In {app}: frame catturato"
        case _ as unreachable:
            assert_never(unreachable)


def events_to_steps(events: list[CaptureEvent]) -> list[ActionStep]:
    steps: list[ActionStep] = []
    for i, e in enumerate(events, 1):
        steps.append(
            ActionStep(
                step_id=f"S{i:03d}",
                description=describe_event(e),
                app=e.app,
                evidence_events=[e.event_id],
                evidence_frames=[e.frame_id] if e.frame_id else [],
            )
        )
    return steps


def run_analyze(events: list[CaptureEvent]) -> list[ActionStep]:
    return events_to_steps(events)


def steps_to_json(steps: list[ActionStep]) -> str:
    return json.dumps(
        [
            {
                "step_id": s.step_id,
                "description": s.description,
                "app": s.app,
                "evidence_events": s.evidence_events,
                "evidence_frames": s.evidence_frames,
            }
            for s in steps
        ],
        ensure_ascii=False,
        indent=1,
    )
