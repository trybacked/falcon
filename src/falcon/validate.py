from __future__ import annotations

import json

from falcon.layout import SessionLayout
from falcon.models import CaptureEvent


class BundleError(ValueError):
    """Session directory fails ingest/analyze prerequisites."""


def validate_manifest(layout: SessionLayout) -> dict[str, object]:
    if not layout.manifest.is_file():
        raise BundleError(f"missing {layout.manifest}")
    try:
        data = json.loads(layout.manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleError(f"invalid JSON in {layout.manifest}") from exc
    if not isinstance(data, dict):
        raise BundleError("manifest must be a JSON object")
    if data.get("consent") is not True:
        raise BundleError("manifest.consent must be true (voluntary shadowing)")
    session_id = data.get("session_id")
    if not session_id or not isinstance(session_id, str):
        raise BundleError("manifest.session_id must be a non-empty string")
    if session_id != layout.root.name:
        raise BundleError(
            f"manifest.session_id {session_id!r} does not match folder {layout.root.name!r}"
        )
    return data


def require_trace_raw(layout: SessionLayout) -> None:
    if not layout.trace_raw.is_file():
        raise BundleError(f"missing {layout.trace_raw}")
    if layout.trace_raw.stat().st_size == 0:
        raise BundleError(f"empty {layout.trace_raw}")


def validate_events(events: list[CaptureEvent]) -> None:
    if not events:
        raise BundleError("no capture events after ingest")
    for ev in events:
        if not ev.event_id:
            raise BundleError("event missing event_id after normalization")
        if not ev.app:
            raise BundleError(f"event {ev.event_id} missing app")


def validate_bundle(layout: SessionLayout) -> list[CaptureEvent]:
    """Manifest + trace.raw present; return normalized events (does not write files)."""
    from falcon.ingest import ingest_path

    validate_manifest(layout)
    require_trace_raw(layout)
    events = ingest_path(layout.trace_raw)
    validate_events(events)
    return events
