from __future__ import annotations

import sys

from falcon.capture.recorder import CaptureBackend


def create_backend() -> CaptureBackend:
    if sys.platform == "darwin":
        raise RuntimeError(
            "macOS capture uses the Swift falcon-recorder. "
            "Build: cd packages/platform-macos && swift build -c release, "
            "then: falcon record --name <session>"
        )
    if sys.platform == "win32":
        from falcon.capture.windows import WindowsBackend

        return WindowsBackend()
    raise RuntimeError(f"unsupported platform {sys.platform}")
