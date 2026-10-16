from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionLayout:
    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def trace_raw(self) -> Path:
        return self.root / "trace.raw.jsonl"

    @property
    def trace(self) -> Path:
        return self.root / "trace.jsonl"

    @property
    def segments(self) -> Path:
        return self.root / "segments.json"

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def frames_index(self) -> Path:
        return self.root / "frames.json"

    @property
    def analysis(self) -> Path:
        return self.root / "analysis.json"

    @property
    def playbook(self) -> Path:
        return self.root / "playbook.md"

    @property
    def report(self) -> Path:
        return self.root / "report.md"

    @property
    def ontology(self) -> Path:
        return self.root / "ontology_proposals.yaml"

    @property
    def questions(self) -> Path:
        return self.root / "competency_questions.yaml"

    @staticmethod
    def create(sessions_root: str, session_id: str) -> SessionLayout:
        root = Path(sessions_root) / session_id
        root.mkdir(parents=True, exist_ok=True)
        return SessionLayout(root)

    @staticmethod
    def latest(sessions_root: str) -> SessionLayout:
        base = Path(sessions_root)
        manifests = sorted(base.glob("*/manifest.json"))
        if not manifests:
            raise FileNotFoundError("no sessions")
        return SessionLayout(manifests[-1].parent)
