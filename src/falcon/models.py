from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from typing import Any, Literal


class EventType(StrEnum):
    APP_ACTIVATE = "app_activate"
    WINDOW_CHANGE = "window_change"
    VALUE_CHANGE = "value_change"
    KEYBOARD = "keyboard"
    PRESS = "press"
    SELECT = "select"
    FRAME = "frame"


@dataclass(frozen=True)
class MousePayload:
    x: int | None = None
    y: int | None = None
    button: str | None = None


@dataclass(frozen=True)
class KeyboardPayload:
    text: str | None = None
    key: str | None = None


@dataclass(frozen=True)
class AxPayload:
    role: str | None = None
    title: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class RawTraceLine:
    """Recorder-native JSONL row (Swift ORR flat or nested internal shape)."""

    kind: str
    timestamp: float
    app: str = ""
    window: str | None = None
    mouse: MousePayload | None = None
    keyboard: KeyboardPayload | None = None
    ax: AxPayload | None = None
    session_id: str | None = None

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> RawTraceLine:
        ts = obj.get("timestamp", obj.get("ts"))
        if ts is None:
            raise ValueError("raw trace line requires timestamp or ts")
        mouse = RawTraceLine._mouse(obj)
        keyboard = RawTraceLine._keyboard(obj)
        ax = RawTraceLine._ax(obj)
        session_id = obj.get("sessionId") or obj.get("session_id")
        if isinstance(session_id, str):
            sid: str | None = session_id
        else:
            sid = None
        app = str(obj.get("app") or "")
        window = obj.get("window")
        win = str(window) if window is not None else None
        return RawTraceLine(
            kind=str(obj["kind"]),
            timestamp=float(ts),
            app=app,
            window=win,
            mouse=mouse,
            keyboard=keyboard,
            ax=ax,
            session_id=sid,
        )

    @staticmethod
    def _mouse(obj: dict[str, Any]) -> MousePayload | None:
        block = obj.get("mouse")
        if isinstance(block, dict):
            return MousePayload(
                x=_as_int(block.get("x")),
                y=_as_int(block.get("y")),
                button=_as_str(block.get("button")),
            )
        if any(k in obj for k in ("x", "y", "button")):
            return MousePayload(
                x=_as_int(obj.get("x")),
                y=_as_int(obj.get("y")),
                button=_as_str(obj.get("button")),
            )
        return None

    @staticmethod
    def _keyboard(obj: dict[str, Any]) -> KeyboardPayload | None:
        block = obj.get("keyboard")
        if isinstance(block, dict):
            return KeyboardPayload(
                text=_as_str(block.get("text")),
                key=_as_str(block.get("key")),
            )
        if "text" in obj:
            return KeyboardPayload(text=_as_str(obj.get("text")))
        return None

    @staticmethod
    def _ax(obj: dict[str, Any]) -> AxPayload | None:
        block = obj.get("ax")
        if not isinstance(block, dict):
            return None
        return AxPayload(
            role=_as_str(block.get("role")),
            title=_as_str(block.get("title")),
            value=_as_str(block.get("value")),
        )


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    return int(v)


def _as_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if s else None


def is_native_capture_event(obj: dict[str, Any]) -> bool:
    return "type" in obj and "kind" not in obj


@dataclass(frozen=True)
class CaptureEvent:
    event_id: str
    ts: float
    type: EventType | str
    app: str
    window: str | None = None
    target: str | None = None
    value: str | None = None
    ax_text: str | None = None
    frame_id: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(line: str) -> CaptureEvent:
        d = json.loads(line)
        if "text" in d and d.get("value") is None:
            d["value"] = d.pop("text")
        allowed = {f.name for f in fields(CaptureEvent)}
        d = {k: v for k, v in d.items() if k in allowed}
        try:
            d["type"] = EventType(d["type"])
        except ValueError:
            pass
        return CaptureEvent(**d)


@dataclass(frozen=True)
class FrameRef:
    frame_id: str
    path: str
    ts: float
    phash: str


@dataclass(frozen=True)
class ActionStep:
    step_id: str
    description: str
    app: str
    evidence_events: list[str]
    evidence_frames: list[str]


@dataclass(frozen=True)
class OntologyProposal:
    kind: Literal["object_type", "link_type"]
    name: str
    description: str
    evidence: list[str]


@dataclass(frozen=True)
class CompetencyQuestion:
    question: str
    rationale: str
    evidence_steps: list[str]


def dataclass_list_to_json(items: list[Any]) -> str:
    return json.dumps([asdict(x) for x in items], ensure_ascii=False, indent=1)
