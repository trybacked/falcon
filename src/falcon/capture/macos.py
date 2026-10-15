from __future__ import annotations

from typing import Any

import AppKit
import Quartz
from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    AXUIElementCopyAttributeValue,
    AXUIElementCopyElementAtPosition,
    AXUIElementCreateApplication,
    AXUIElementCreateSystemWide,
    AXUIElementGetPid,
)
from Foundation import NSDictionary

from falcon.capture.appswitch import AppSwitchWatcher
from falcon.capture.clicks import ClickWatcher
from falcon.models import CaptureEvent, EventType

AX_FOCUSED_APP = "AXFocusedApplication"
AX_FOCUSED = "AXFocusedUIElement"
AX_WINDOW = "AXFocusedWindow"
AX_ROLE = "AXRole"
AX_TITLE = "AXTitle"
AX_VALUE = "AXValue"
AX_DESCRIPTION = "AXDescription"
PRESS_ROLES = frozenset(
    {"AXButton", "AXLink", "AXMenuItem", "AXPopUpButton", "AXCheckBox", "AXRadioButton"}
)


def _ax(el: Any, attr: str) -> Any:
    err, val = AXUIElementCopyAttributeValue(el, attr, None)
    return val if err == 0 else None


def _app_ax(app_obj: Any) -> Any | None:
    if not app_obj:
        return None
    return AXUIElementCreateApplication(app_obj.processIdentifier())


def _label(el: Any) -> str:
    for attr in (AX_TITLE, AX_DESCRIPTION, AX_ROLE):
        v = _ax(el, attr)
        if v:
            return str(v)
    return ""


def _target_at(root: Any, x: int, y: int) -> str:
    bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    ax_y = int(bounds.size.height - y)
    err, el = AXUIElementCopyElementAtPosition(root, float(x), float(ax_y), None)
    if err != 0 or not el:
        return f"@{x},{y}"
    name = _label(el)
    return name or f"@{x},{y}"


class MacOSBackend:
    def __init__(self, value_max_chars: int = 200) -> None:
        self._value_max = value_max_chars
        self._state: dict[str, Any] = {}
        self._system = AXUIElementCreateSystemWide()
        self._switches = AppSwitchWatcher(self._active_app_obj, self._window)
        self._clicks = ClickWatcher(self._click_context)

    def is_ready(self) -> tuple[bool, str]:
        if AXIsProcessTrusted():
            return True, ""
        AXIsProcessTrustedWithOptions(
            NSDictionary.dictionaryWithObject_forKey_(True, "AXTrustedCheckOptionPrompt")
        )
        if AXIsProcessTrusted():
            return True, ""
        name = AppKit.NSProcessInfo.processInfo().processName()
        return False, (
            f"Accessibility required for “{name}”. "
            "System Settings → Privacy & Security → Accessibility: "
            "enable Python, Cursor, or Terminal, "
            "then quit and reopen the terminal."
        )

    def _active_app_obj(self) -> Any | None:
        err, app_el = AXUIElementCopyAttributeValue(self._system, AX_FOCUSED_APP, None)
        if err == 0 and app_el:
            err, pid = AXUIElementGetPid(app_el, None)
            if err == 0:
                app_obj = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
                if app_obj:
                    return app_obj
        return AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()

    def front_context(self) -> tuple[str, str | None]:
        app_obj = self._active_app_obj()
        app = str(app_obj.localizedName()) if app_obj else ""
        return app, self._window(app_obj)

    def _click_context(self) -> tuple[str, str | None]:
        return self.front_context()

    def poll(self, now: float) -> list[CaptureEvent]:
        events: list[CaptureEvent] = []
        for ts, app_name, win in self._switches.drain():
            if not app_name or self._state.get("app") == app_name:
                continue
            events.append(
                CaptureEvent("", ts, EventType.APP_ACTIVATE, app_name, window=win)
            )
            self._state["app"] = app_name
            self._state["win"] = win
            self._state.pop("snap", None)
        app_obj = self._active_app_obj()
        app = str(app_obj.localizedName()) if app_obj else ""
        window = self._window(app_obj)
        if app and self._state.get("app") != app:
            events.append(
                CaptureEvent("", now, EventType.APP_ACTIVATE, app, window=window)
            )
        elif window and self._state.get("win") != window:
            events.append(
                CaptureEvent("", now, EventType.WINDOW_CHANGE, app, window=window)
            )
        focused = self._focused(app_obj)
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
                    et = EventType.PRESS if role in PRESS_ROLES else EventType.SELECT
                    events.append(
                        CaptureEvent("", now, et, app, window=window, target=target)
                    )
                self._state["snap"] = snap
        for ts, x, y, click_app, click_win in self._clicks.drain():
            target = _target_at(self._system, x, y)
            events.append(
                CaptureEvent(
                    "",
                    ts,
                    EventType.PRESS,
                    click_app or app,
                    window=click_win or window,
                    target=target,
                )
            )
        self._state["app"] = app
        self._state["win"] = window
        return events

    def _window(self, app_obj: Any) -> str | None:
        app_ax = _app_ax(app_obj)
        if not app_ax:
            return None
        err, win = AXUIElementCopyAttributeValue(app_ax, AX_WINDOW, None)
        if err != 0 or not win:
            return None
        t = _ax(win, AX_TITLE)
        return str(t) if t else None

    def _focused(self, app_obj: Any) -> tuple[str, str, Any] | None:
        el = self._focused_element(self._system)
        if el is None:
            app_ax = _app_ax(app_obj)
            if app_ax:
                el = self._focused_element(app_ax)
        if el is None:
            return None
        role = str(_ax(el, AX_ROLE) or "")
        target = _label(el)
        value = _ax(el, AX_VALUE)
        return role, target, value

    def _focused_element(self, root: Any) -> Any | None:
        err, el = AXUIElementCopyAttributeValue(root, AX_FOCUSED, None)
        return el if err == 0 and el else None
