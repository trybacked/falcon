from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, cast

from falcon.install_paths import bundled_config_candidates


@dataclass(frozen=True)
class CaptureConfig:
    poll_interval_s: float = 0.5
    frame_interval_s: float = 3.0
    idle_gap_s: float = 45.0
    dedup_hamming: int = 6


@dataclass(frozen=True)
class LlmConfig:
    base_url: str = "https://ai-gateway.vercel.sh/v1"
    model: str = "openai/gpt-4o-mini"
    api_key_env: str = "AI_GATEWAY_API_KEY"
    timeout_s: float = 120.0


@dataclass(frozen=True)
class PathsConfig:
    sessions_root: str = "sessions"


@dataclass(frozen=True)
class OutputConfig:
    language: str = "it"


@dataclass(frozen=True)
class AppConfig:
    capture: CaptureConfig = CaptureConfig()
    llm: LlmConfig = LlmConfig()
    paths: PathsConfig = PathsConfig()
    output: OutputConfig = OutputConfig()


def _merge[T](cls: type[T], data: dict[str, Any], env_prefix: str) -> T:
    if not is_dataclass(cls):
        raise TypeError(f"{cls} is not a dataclass")
    kwargs: dict[str, Any] = {}
    for f in fields(cast(Any, cls)):
        env_key = f"{env_prefix}__{f.name}".upper()
        if env_key in os.environ:
            val = os.environ[env_key]
            kwargs[f.name] = float(val) if f.type is float else int(val) if f.type is int else val
        elif f.name in data:
            kwargs[f.name] = data[f.name]
    return cls(**kwargs)


def load_config(path: Path | None = None) -> AppConfig:
    data: dict[str, Any] = {}
    if path and path.is_file():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    return AppConfig(
        capture=_merge(CaptureConfig, data.get("capture", {}), "FW_CAPTURE"),
        llm=_merge(LlmConfig, data.get("llm", {}), "FW_LLM"),
        paths=_merge(PathsConfig, data.get("paths", {}), "FW_PATHS"),
        output=_merge(OutputConfig, data.get("output", {}), "FW_OUTPUT"),
    )


def resolve_config_path(arg: str | None) -> Path | None:
    if arg:
        return Path(arg)
    env = os.environ.get("FW_CONFIG")
    if env:
        return Path(env)
    p = Path("config.toml")
    if p.is_file():
        return p
    for candidate in bundled_config_candidates():
        if candidate.is_file():
            return candidate
    return None
