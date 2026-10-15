from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Event
from typing import Protocol

from PIL import Image

from falcon.capture.frames import FrameStore
from falcon.config import CaptureConfig
from falcon.layout import SessionLayout
from falcon.models import CaptureEvent, EventType


class CaptureBackend(Protocol):
    def is_ready(self) -> tuple[bool, str]: ...
    def poll(self, now: float) -> list[CaptureEvent]: ...
    def front_context(self) -> tuple[str, str | None]: ...


class ScreenGrabber(Protocol):
    def grab(self) -> Image.Image | None: ...


def _resume_event_counter(path: Path) -> int:
    if not path.is_file():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        eid = json.loads(line).get("event_id", "")
        if isinstance(eid, str) and eid.startswith("E-"):
            n = max(n, int(eid[2:]))
    return n


class EventIds:
    def __init__(self, start: int = 0) -> None:
        self._n = start

    def next(self) -> str:
        self._n += 1
        return f"E-{self._n:06d}"


class SessionRecorder:
    def __init__(
        self,
        layout: SessionLayout,
        backend: CaptureBackend,
        grabber: ScreenGrabber,
        frames: FrameStore,
        cfg: CaptureConfig,
    ) -> None:
        self._layout = layout
        self._backend = backend
        self._grabber = grabber
        self._frames = frames
        self._cfg = cfg
        self._ids = EventIds(_resume_event_counter(layout.trace_raw))

    def run(self, stop: Event) -> None:
        ok, reason = self._backend.is_ready()
        if not ok:
            raise PermissionError(reason)
        last_frame = 0.0
        while not stop.is_set():
            now = time.time()
            for ev in self._backend.poll(now):
                self._write(self._with_id(ev))
                if ev.type != EventType.FRAME:
                    self._maybe_frame(ev.ts, ev.app)
            if now - last_frame >= self._cfg.frame_interval_s:
                app, _ = self._backend.front_context()
                self._maybe_frame(now, app)
                last_frame = now
            time.sleep(self._cfg.poll_interval_s)

    def _with_id(self, ev: CaptureEvent) -> CaptureEvent:
        if ev.event_id:
            return ev
        from dataclasses import replace

        return replace(ev, event_id=self._ids.next())

    def _maybe_frame(self, ts: float, app: str) -> None:
        img = self._grabber.grab()
        if img is None:
            return
        ref = self._frames.save(img, ts)
        if ref:
            self._write(
                CaptureEvent(
                    event_id=self._ids.next(),
                    ts=ts,
                    type=EventType.FRAME,
                    app=app,
                    frame_id=ref.frame_id,
                )
            )

    def _write(self, ev: CaptureEvent) -> None:
        with self._layout.trace_raw.open("a", encoding="utf-8") as f:
            f.write(ev.to_json() + "\n")
