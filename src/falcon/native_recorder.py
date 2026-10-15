from __future__ import annotations

import sys
from pathlib import Path

from falcon.install_paths import native_recorder_candidates


def native_recorder_binary() -> Path | None:
    if sys.platform != "darwin":
        return None
    for candidate in native_recorder_candidates():
        if candidate.is_file():
            return candidate
    return None
