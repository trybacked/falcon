from __future__ import annotations

import sys
from pathlib import Path


def runtime_root() -> Path:
    """Directory containing the running `falcon` executable (or repo root in dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return runtime_root()
    return Path(__file__).resolve().parents[2]


def bundled_config_candidates() -> list[Path]:
    root = runtime_root()
    return [root / "config.toml", root / "config.toml.example"]


def native_recorder_candidates() -> list[Path]:
    if sys.platform != "darwin":
        return []
    root = runtime_root()
    repo = repo_root()
    return [
        root / "falcon-recorder",
        root / "bin" / "falcon-recorder",
        repo / "packages" / "platform-macos" / ".build" / "release" / "falcon-recorder",
        repo / "packages" / "platform-macos" / ".build" / "debug" / "falcon-recorder",
    ]
