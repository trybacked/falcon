from __future__ import annotations

import re
from pathlib import Path

import pytest

from falcon.ingest import ingest_path
from falcon.layout import SessionLayout
from falcon.models import CaptureEvent, EventType
from falcon.scrub import PATTERNS, Scrubber

_EMAIL = PATTERNS[0][1]
_FISCAL = PATTERNS[2][1]


def test_scrub_email_placeholder_stable() -> None:
    s = Scrubber()
    a = s.scrub_text("contact user@example.com please")
    b = s.scrub_text("user@example.com")
    assert a == "contact [EMAIL-1] please"
    assert b == "[EMAIL-1]"


def test_scrub_independent_instances() -> None:
    a = Scrubber()
    b = Scrubber()
    assert a.scrub_text("a@test.it") == "[EMAIL-1]"
    assert b.scrub_text("a@test.it") == "[EMAIL-1]"


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("IT60X0546811801", "IBAN"),
        ("RSSMRA85T10A562S", "FISCAL"),
        ("IT12345678901", "VAT"),
    ],
)
def test_scrub_patterns(raw: str, kind: str) -> None:
    out = Scrubber().scrub_text(f"value={raw}")
    assert f"[{kind}-1]" in out
    assert raw not in out


def test_scrub_event_preserves_non_text_fields() -> None:
    ev = CaptureEvent(
        event_id="E-000001",
        ts=1.5,
        type=EventType.PRESS,
        app="App",
        window="W",
        target="OK",
        frame_id="F-1",
    )
    out = Scrubber().scrub_event(ev)
    assert out.event_id == "E-000001"
    assert out.ts == 1.5
    assert out.type == EventType.PRESS
    assert out.app == "App"
    assert out.frame_id == "F-1"


def test_scrub_keyboard_value_and_ax_text() -> None:
    ev = CaptureEvent(
        event_id="E-000002",
        ts=2.0,
        type=EventType.VALUE_CHANGE,
        app="Mail",
        window="Compose",
        target="To",
        value="secret@corp.example.com",
        ax_text="AXTextField · To · secret@corp.example.com",
    )
    out = Scrubber().scrub_event(ev)
    assert out.value == "[EMAIL-1]"
    assert out.ax_text == "AXTextField · To · [EMAIL-1]"
    assert "secret@corp" not in (out.value or "")
    assert "secret@corp" not in (out.ax_text or "")


def test_typed_email_fixture_becomes_placeholder() -> None:
    fixture = Path(__file__).parent / "fixtures" / "keyboard_typed_email.jsonl"
    events = ingest_path(fixture)
    scrubbed = Scrubber().scrub_events(events)
    blob = "\n".join(e.to_json() for e in scrubbed)
    assert not _EMAIL.search(blob)
    assert "[EMAIL-1]" in blob
    keyboard_ev = next(e for e in scrubbed if e.target == "keyboard")
    assert keyboard_ev.value == "[EMAIL-1]"
    ax_ev = next(e for e in scrubbed if e.target == "Email")
    assert ax_ev.value == "[EMAIL-1]"
    assert ax_ev.ax_text is not None
    assert "user@example.com" not in ax_ev.ax_text


def test_analyze_ingest_scrubs_keyboard_and_ax(tmp_path: Path) -> None:
    """Mirrors cmd_analyze: ingest_path → scrub_events → trace.jsonl."""
    layout = SessionLayout.create(str(tmp_path), "scrub-ingest")
    fixture = Path(__file__).parent / "fixtures" / "keyboard_typed_email.jsonl"
    layout.trace_raw.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    raw = ingest_path(layout.trace_raw)
    scrubbed = Scrubber().scrub_events(raw)
    layout.trace.write_text("\n".join(e.to_json() for e in scrubbed), encoding="utf-8")

    trace = layout.trace.read_text(encoding="utf-8")
    assert not _EMAIL.search(trace)
    assert "[EMAIL-1]" in trace
    assert all("user@example.com" not in e.to_json() for e in scrubbed)


def test_synthetic_fixture_no_raw_pii_after_scrub(synthetic_trace_path: Path) -> None:
    scrubbed = Scrubber().scrub_events(ingest_path(synthetic_trace_path))
    text = "\n".join(e.to_json() for e in scrubbed)
    assert not _EMAIL.search(text)
    assert not _FISCAL.search(text)
    assert re.search(r"\[EMAIL-\d+\]", text)
