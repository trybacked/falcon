from __future__ import annotations

import threading
import time
from collections.abc import Callable

import Quartz
from CoreFoundation import (
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CFRunLoopRun,
    kCFRunLoopCommonModes,
)

ClickContext = Callable[[], tuple[str, str | None]]


class ClickWatcher:
    def __init__(self, context: ClickContext) -> None:
        self._pending: list[tuple[float, int, int, str, str | None]] = []
        self._lock = threading.Lock()
        self._context = context
        self.active = False
        ready = threading.Event()
        threading.Thread(target=self._loop, args=(ready,), daemon=True).start()
        ready.wait(timeout=2)

    def drain(self) -> list[tuple[float, int, int, str, str | None]]:
        with self._lock:
            out = self._pending[:]
            self._pending.clear()
        return out

    def _loop(self, ready: threading.Event) -> None:
        def callback(_proxy, _etype, event, _refcon):
            loc = Quartz.CGEventGetLocation(event)
            app, window = self._context()
            with self._lock:
                self._pending.append(
                    (time.time(), int(loc.x), int(loc.y), app, window)
                )
            return event

        mask = Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask,
            callback,
            None,
        )
        ready.set()
        if not tap:
            return
        self.active = True
        Quartz.CGEventTapEnable(tap, True)
        source = CFMachPortCreateRunLoopSource(None, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
        CFRunLoopRun()
