from __future__ import annotations

from falcon.capture.windows import WindowsBackend
from falcon.models import EventType


def test_is_ready_uses_injected_probe() -> None:
    backend = WindowsBackend(ready=lambda: (False, "no uia"))
    assert backend.is_ready() == (False, "no uia")


def test_front_context_delegates() -> None:
    backend = WindowsBackend(foreground=lambda: ("Notepad", "Untitled"))
    assert backend.front_context() == ("Notepad", "Untitled")


def test_poll_app_activate_on_first_app() -> None:
    backend = WindowsBackend(
        foreground=lambda: ("Notepad", "Untitled"),
        focused=lambda: None,
    )
    events = backend.poll(1.0)
    assert len(events) == 1
    assert events[0].type == EventType.APP_ACTIVATE
    assert events[0].app == "Notepad"
    assert events[0].window == "Untitled"


def test_poll_window_change_same_app() -> None:
    state = {"win": "A"}

    def front() -> tuple[str, str | None]:
        return "Notepad", state["win"]

    backend = WindowsBackend(foreground=front, focused=lambda: None)
    backend._state["app"] = "Notepad"
    backend._state["win"] = "A"

    state["win"] = "B"
    events = backend.poll(2.0)
    assert len(events) == 1
    assert events[0].type == EventType.WINDOW_CHANGE
    assert events[0].window == "B"


def test_poll_select_on_focus_change() -> None:
    focus = {"snap": ("Edit", "Body", None)}

    def focused():
        return focus["snap"]

    backend = WindowsBackend(
        foreground=lambda: ("App", "Win"),
        focused=focused,
    )
    backend._state.update(app="App", win="Win")

    events = backend.poll(3.0)
    assert len(events) == 1
    assert events[0].type == EventType.SELECT
    assert events[0].target == "Body"

    events = backend.poll(3.1)
    assert events == []

    focus["snap"] = ("Edit", "Other field", None)
    events = backend.poll(4.0)
    assert len(events) == 1
    assert events[0].type == EventType.SELECT
    assert events[0].target == "Other field"


def test_poll_press_for_button_role() -> None:
    backend = WindowsBackend(
        foreground=lambda: ("App", "Win"),
        focused=lambda: ("Button", "OK", None),
    )
    backend._state.update(app="App", win="Win")
    events = backend.poll(5.0)
    assert events[0].type == EventType.PRESS


def test_poll_value_change() -> None:
    values = {"v": "a"}

    def focused():
        return "Edit", "Search", values["v"]

    backend = WindowsBackend(
        foreground=lambda: ("App", "Win"),
        focused=focused,
    )
    backend._state.update(app="App", win="Win", snap=("Edit", "Search", "a"))

    values["v"] = "ab"
    events = backend.poll(6.0)
    assert len(events) == 1
    assert events[0].type == EventType.VALUE_CHANGE
    assert events[0].value == "ab"


def test_poll_value_truncated() -> None:
    long_val = "x" * 300

    backend = WindowsBackend(
        value_max_chars=50,
        foreground=lambda: ("App", "Win"),
        focused=lambda: ("Edit", "Field", long_val),
    )
    backend._state.update(app="App", win="Win", snap=("Edit", "Field", "old"))

    events = backend.poll(7.0)
    assert events[0].type == EventType.VALUE_CHANGE
    assert events[0].value is not None
    assert len(events[0].value) == 50
