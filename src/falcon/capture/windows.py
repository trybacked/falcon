from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from falcon.models import CaptureEvent, EventType

ForegroundFn = Callable[[], tuple[str, str | None]]
FocusedFn = Callable[[], tuple[str, str, Any] | None]

PRESS_TYPES = frozenset(
    {
        "Button",
        "Hyperlink",
        "MenuItem",
        "CheckBox",
        "RadioButton",
        "SplitButton",
    }
)

_UIA_VALUE_PROPERTY = 30045


def _label(info: Any) -> str:
    for attr in ("name", "automation_id", "class_name", "control_type"):
        v = getattr(info, attr, None)
        if v:
            return str(v)
    return ""


def _element_value(info: Any) -> Any:
    try:
        return info.element.GetCurrentPropertyValue(_UIA_VALUE_PROPERTY)
    except Exception:
        pass
    try:
        iface = info.element.GetCurrentPattern(10002)
        if iface is not None:
            return iface.CurrentValue
    except Exception:
        pass
    return None


def default_foreground() -> tuple[str, str | None]:
    import win32api
    import win32gui
    import win32process
    from pywinauto import Desktop

    try:
        win = Desktop(backend="uia").get_active()
    except Exception:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "", None
        title = win32gui.GetWindowText(hwnd) or None
        return title or "", title

    title = win.window_text() or None
    app = ""
    try:
        pid = win.process_id()
        exe = win32process.GetModuleFileNameEx(
            win32api.OpenProcess(0x1000, False, pid),
            0,
        )
        app = Path(exe).stem
    except Exception:
        app = title or ""
    return app, title


def default_focused() -> tuple[str, str, Any] | None:
    from pywinauto.uia_defines import IUIA
    from pywinauto.uia_element_info import UIAElementInfo

    try:
        raw = IUIA().get_focused_element()
        if raw is None:
            return None
        info = UIAElementInfo(raw)
    except Exception:
        return None
    role = str(getattr(info, "control_type", "") or "")
    target = _label(info)
    value = _element_value(info)
    return role, target, value


def default_is_ready() -> tuple[bool, str]:
    try:
        from pywinauto import Desktop

        Desktop(backend="uia").get_active()
        return True, ""
    except ImportError:
        return False, (
            "pywinauto is not installed. "
            "Install with: pip install 'falcon[win32]'"
        )
    except Exception as exc:
        return False, f"UI Automation unavailable: {exc}"


class WindowsBackend:
    """Windows capture via pywinauto/UIA (foreground window, focus, value changes)."""

    def __init__(
        self,
        value_max_chars: int = 200,
        *,
        foreground: ForegroundFn | None = None,
        focused: FocusedFn | None = None,
        ready: Callable[[], tuple[bool, str]] | None = None,
    ) -> None:
        self._value_max = value_max_chars
        self._state: dict[str, Any] = {}
        self._foreground = foreground or default_foreground
        self._focused = focused or default_focused
        self._ready = ready or default_is_ready

    def is_ready(self) -> tuple[bool, str]:
        return self._ready()

    def front_context(self) -> tuple[str, str | None]:
        return self._foreground()

    def poll(self, now: float) -> list[CaptureEvent]:
        events: list[CaptureEvent] = []
        app, window = self._foreground()
        if app and self._state.get("app") != app:
            events.append(
                CaptureEvent("", now, EventType.APP_ACTIVATE, app, window=window)
            )
        elif window and self._state.get("win") != window:
            events.append(
                CaptureEvent("", now, EventType.WINDOW_CHANGE, app, window=window)
            )

        focused = self._focused()
        if focused:
            role, target, value = focused
            snap = (role, target, str(value) if value is not None else None)
            prev = self._state.get("snap")
            if snap != prev:
                if prev and snap[2] is not None and snap[2] != prev[2]:
                    events.append(
                        CaptureEvent(
                            "",
                            now,
                            EventType.VALUE_CHANGE,
                            app,
                            window=window,
                            target=target or role,
                            value=snap[2][: self._value_max],
                        )
                    )
                elif snap[1] and (not prev or snap[:2] != prev[:2]):
                    et = EventType.PRESS if role in PRESS_TYPES else EventType.SELECT
                    events.append(
                        CaptureEvent("", now, et, app, window=window, target=target)
                    )
                self._state["snap"] = snap

        self._state["app"] = app
        self._state["win"] = window
        return events
