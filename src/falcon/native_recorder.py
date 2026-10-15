from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def native_recorder_binary() -> Path | None:
    if sys.platform != "darwin":
        return None
    base = _REPO_ROOT / "packages" / "platform-macos" / ".build"
    for config in ("release", "debug"):
        candidate = base / config / "falcon-recorder"
        if candidate.is_file():
            return candidate
    return None
