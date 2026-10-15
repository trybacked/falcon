from __future__ import annotations

import threading
import time
from collections.abc import Callable

ActiveApp = Callable[[], object | None]


class AppSwitchWatcher:
    def __init__(
        self,
        active_app: ActiveApp,
        window_for: Callable[[object], str | None],
        interval_s: float = 0.12,
    ) -> None:
        self._pending: list[tuple[float, str, str | None]] = []
        self._lock = threading.Lock()
        self._active_app = active_app
        self._window_for = window_for
        self._last: str | None = None
        self._stop = threading.Event()
        threading.Thread(target=self._run, args=(interval_s,), daemon=True).start()

    def drain(self) -> list[tuple[float, str, str | None]]:
        with self._lock:
            out = self._pending[:]
            self._pending.clear()
        return out

    def _run(self, interval_s: float) -> None:
        while not self._stop.is_set():
            app_obj = self._active_app()
            name = str(app_obj.localizedName()) if app_obj else ""
            if name and name != self._last:
                window = self._window_for(app_obj) if app_obj else None
                with self._lock:
                    self._pending.append((time.time(), name, window))
                self._last = name
            time.sleep(interval_s)
