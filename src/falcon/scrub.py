from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace

from falcon.models import CaptureEvent

PATTERNS = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")),
    ("FISCAL", re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b")),
    ("VAT", re.compile(r"\b(?:IT)?\d{11}\b")),
]


class Scrubber:
    def __init__(self) -> None:
        self._map: dict[tuple[str, str], str] = {}
        self._counts: dict[str, int] = {}

    def scrub_text(self, text: str) -> str:
        out = text
        for kind, pat in PATTERNS:

            def sub(m: re.Match[str], k: str = kind) -> str:
                key = (k, m.group(0))
                if key not in self._map:
                    self._counts[k] = self._counts.get(k, 0) + 1
                    self._map[key] = f"[{k}-{self._counts[k]}]"
                return self._map[key]

            out = pat.sub(sub, out)
        return out

    def scrub_event(self, ev: CaptureEvent) -> CaptureEvent:
        return replace(
            ev,
            window=self.scrub_text(ev.window) if ev.window else None,
            target=self.scrub_text(ev.target) if ev.target else None,
            value=self.scrub_text(ev.value) if ev.value else None,
            ax_text=self.scrub_text(ev.ax_text) if ev.ax_text else None,
        )

    def scrub_events(self, events: Iterable[CaptureEvent]) -> list[CaptureEvent]:
        return [self.scrub_event(e) for e in events]
