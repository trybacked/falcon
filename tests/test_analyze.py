from __future__ import annotations

from pathlib import Path

import pytest

from falcon.analyze import describe_event, format_target, run_analyze
from falcon.ingest import ingest_jsonl
from falcon.models import CaptureEvent, EventType


def _ev(**kwargs: object) -> CaptureEvent:
    base = {
        "event_id": "E-000001",
        "ts": 1.0,
        "type": "press",
        "app": "TestApp",
        "window": "Main",
        "target": None,
        "value": None,
        "frame_id": None,
    }
    base.update(kwargs)
    return CaptureEvent(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (None, "elemento"),
        ("Accedi", "«Accedi»"),
        ("@120,340", "@120,340"),
        ("Button|Salva", "«Salva» (Button)"),
        ("Edit:Nome cliente", "«Nome cliente» (Edit)"),
    ],
)
def test_format_target(target: str | None, expected: str) -> None:
    assert format_target(target) == expected


def test_describe_window_change_enum() -> None:
    ev = _ev(type=EventType.WINDOW_CHANGE, app="Safari", window="Home")
    assert describe_event(ev) == "In Safari, passa alla finestra «Home»"


def test_describe_keyboard_text_input_via_value_change() -> None:
    ev = _ev(type=EventType.VALUE_CHANGE, target="keyboard", value="ciao mondo")
    assert describe_event(ev) == "In TestApp, finestra «Main»: digita «ciao mondo»"


def test_describe_keyboard_text_input_empty() -> None:
    ev = _ev(type=EventType.VALUE_CHANGE, target="keyboard", value=None)
    assert describe_event(ev) == "In TestApp, finestra «Main»: digita testo"


def test_describe_keyboard_submit_via_value_change() -> None:
    ev = _ev(type=EventType.VALUE_CHANGE, target="keyboard.submit", value="query")
    assert describe_event(ev) == "In TestApp, finestra «Main»: conferma input «query»"


def test_describe_press_richer_target() -> None:
    ev = _ev(type=EventType.PRESS, target="Button|OK")
    assert describe_event(ev) == "In TestApp, finestra «Main»: click su «OK» (Button)"


def test_describe_click_coordinates() -> None:
    ev = _ev(type=EventType.PRESS, target="@10,20")
    assert describe_event(ev) == "In TestApp, finestra «Main»: click in @10,20"


def test_describe_value_change_richer_target() -> None:
    ev = _ev(type=EventType.VALUE_CHANGE, target="Edit:Email", value="a@b.it")
    assert describe_event(ev) == "In TestApp, finestra «Main»: imposta «Email» (Edit) = «a@b.it»"


def test_describe_value_change_ax_text_enriches_target() -> None:
    ev = _ev(
        type=EventType.VALUE_CHANGE,
        target="Email",
        value="a@b.it",
        ax_text="AXTextField · Email · a@b.it",
    )
    expected = "In TestApp, finestra «Main»: imposta «Email» (AXTextField) = «a@b.it»"
    assert describe_event(ev) == expected


def test_describe_ingested_keyboard_as_value_change() -> None:
    ev = _ev(type=EventType.VALUE_CHANGE, target="keyboard", value="ciao")
    assert describe_event(ev) == "In TestApp, finestra «Main»: digita «ciao»"


def test_run_analyze_orr_style_fixture() -> None:
    path = Path(__file__).parent / "fixtures" / "orr_style.jsonl"
    events = ingest_jsonl(path.read_text(encoding="utf-8"))
    steps = run_analyze(events)
    descriptions = [s.description for s in steps]

    assert len(steps) == 8
    assert any("passa alla finestra «analyze.py — falcon»" in d for d in descriptions)
    assert any("digita «def describe_event»" in d for d in descriptions)
    assert any("conferma input «def describe_event»" in d for d in descriptions)
    assert any("click in @512,384" in d for d in descriptions)
    assert any("click su «Salva» (Button)" in d for d in descriptions)
    assert any("imposta «Nome cliente» (Edit) = «Acme Srl»" in d for d in descriptions)
