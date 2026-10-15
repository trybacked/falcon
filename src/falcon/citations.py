from __future__ import annotations

from dataclasses import dataclass

from falcon.models import ActionStep, CaptureEvent, FrameRef


class CitationError(ValueError):
    """Raised when an action step cites evidence ids missing from the session index."""

    def __init__(self, *, step_id: str, kind: str, citation_id: str) -> None:
        self.step_id = step_id
        self.kind = kind
        self.citation_id = citation_id
        super().__init__(f"unknown {kind} {citation_id!r} in step {step_id!r}")


@dataclass(frozen=True)
class EvidenceIndex:
    events: frozenset[str]
    frames: frozenset[str]

    @staticmethod
    def from_session(
        events: list[CaptureEvent] | None,
        frames: list[FrameRef] | None,
    ) -> EvidenceIndex:
        event_ids: set[str] = set()
        for ev in events or []:
            if not ev.event_id:
                raise ValueError("capture event missing event_id")
            event_ids.add(ev.event_id)
        frame_ids: set[str] = set()
        for fr in frames or []:
            if not fr.frame_id:
                raise ValueError("frame ref missing frame_id")
            frame_ids.add(fr.frame_id)
        return EvidenceIndex(frozenset(event_ids), frozenset(frame_ids))


def validate_citations(steps: list[ActionStep], index: EvidenceIndex) -> None:
    for step in steps:
        for eid in step.evidence_events:
            if eid not in index.events:
                raise CitationError(step_id=step.step_id, kind="event", citation_id=eid)
        for fid in step.evidence_frames:
            if fid not in index.frames:
                raise CitationError(step_id=step.step_id, kind="frame", citation_id=fid)
