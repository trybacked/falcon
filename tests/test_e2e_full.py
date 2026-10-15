"""End-to-end: recorder-shaped JSONL → ingest → analyze → distill → report (offline)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

from falcon import cli
from falcon.ingest import ingest_jsonl
from falcon.layout import SessionLayout
from falcon.scrub import PATTERNS


def _session_config(tmp_path: Path, session_id: str) -> tuple[Path, Path]:
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    config_path = tmp_path / "falcon-test.toml"
    config_path.write_text(
        f'[paths]\nsessions_root = "{sessions_root.as_posix()}"\n',
        encoding="utf-8",
    )
    layout = SessionLayout.create(str(sessions_root), session_id)
    layout.manifest.write_text(
        json.dumps({"session_id": session_id, "consent": True, "recorder": "orr-fixture"}),
        encoding="utf-8",
    )
    return config_path, layout


def _args(session: str, config: Path) -> argparse.Namespace:
    return argparse.Namespace(session=session, config=str(config), name=None)


@pytest.mark.usefixtures("block_network")
def test_e2e_cli_orr_to_report(
    tmp_path: Path,
    fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "orr_style.jsonl"
    session_id = "e2e-full"
    config_path, layout = _session_config(tmp_path, session_id)
    layout.trace_raw.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    cli.cmd_ingest(_args(session_id, config_path))
    raw_after = layout.trace_raw.read_text(encoding="utf-8")
    assert '"kind":' not in raw_after
    assert '"type":' in raw_after

    cli.cmd_analyze(_args(session_id, config_path))
    assert layout.segments.is_file()
    steps = json.loads(layout.analysis.read_text(encoding="utf-8"))
    assert len(steps) >= 7
    assert all(s["step_id"].startswith("S") for s in steps)

    monkeypatch.setattr(cli, "build_client", lambda _cfg: fake_llm)
    cli.cmd_distill(_args(session_id, config_path))

    assert layout.playbook.is_file()
    assert layout.ontology.is_file()
    assert layout.questions.is_file()
    playbook = layout.playbook.read_text(encoding="utf-8")
    assert playbook.startswith("# Playbook")
    assert "analyze.py — falcon" in playbook or "Cursor" in playbook

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.cmd_report(_args(session_id, config_path))
    assert "# Playbook" in buf.getvalue()

    assert fake_llm.prompts
    prompt = fake_llm.prompts[0]
    assert "F-" not in prompt


@pytest.mark.usefixtures("block_network")
def test_e2e_subprocess_ingest_analyze_synthetic(
    tmp_path: Path,
    synthetic_trace_path: Path,
) -> None:
    session_id = "e2e-subprocess"
    config_path, layout = _session_config(tmp_path, session_id)
    layout.trace_raw.write_text(synthetic_trace_path.read_text(encoding="utf-8"), encoding="utf-8")

    base = [
        sys.executable,
        "-m",
        "falcon.cli",
        "--config",
        str(config_path),
    ]
    for cmd in ("ingest", "analyze"):
        proc = subprocess.run(
            [*base, cmd, "--session", session_id],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[1],
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout

    assert layout.trace.is_file()
    trace = layout.trace.read_text(encoding="utf-8")
    assert "[EMAIL-" in trace
    analysis = json.loads(layout.analysis.read_text(encoding="utf-8"))
    assert len(analysis) >= 8


@pytest.fixture
def complex_session_path() -> Path:
    return Path(__file__).parent / "fixtures" / "complex_session.jsonl"


@pytest.mark.usefixtures("block_network")
def test_e2e_complex_multi_window_session(
    tmp_path: Path,
    complex_session_path: Path,
    fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mixed Swift ORR + native UIA rows, many apps/windows, PII, clicks, frames."""
    session_id = "e2e-complex"
    config_path, layout = _session_config(tmp_path, session_id)
    raw_text = complex_session_path.read_text(encoding="utf-8")
    layout.trace_raw.write_text(raw_text, encoding="utf-8")

    ingested = ingest_jsonl(raw_text)
    assert len(ingested) >= 28
    apps = {e.app for e in ingested if e.app}
    expected_apps = {
        "Cursor",
        "Safari",
        "Microsoft Excel",
        "Microsoft Outlook",
        "Microsoft Teams",
        "Notepad",
    }
    assert apps >= expected_apps

    cli.cmd_ingest(_args(session_id, config_path))
    cli.cmd_analyze(_args(session_id, config_path))

    trace = layout.trace.read_text(encoding="utf-8")
    assert not PATTERNS[0][1].search(trace)
    assert "[EMAIL-" in trace
    assert "[FISCAL-" in trace
    assert "RSSMRA85T10A562S" not in trace

    steps = json.loads(layout.analysis.read_text(encoding="utf-8"))
    assert len(steps) >= 25
    descriptions = " ".join(s["description"] for s in steps)
    for fragment in (
        "test_e2e_full.py",
        "Portale HR",
        "Report Q1",
        "Posta in arrivo",
        "Nuovo messaggio",
        "Microsoft Teams",
        "Notepad",
    ):
        assert fragment in descriptions, fragment

    step_apps = {s["app"] for s in steps if s.get("app")}
    assert "Microsoft Outlook" in step_apps
    assert "Safari" in step_apps

    monkeypatch.setattr(cli, "build_client", lambda _cfg: fake_llm)
    cli.cmd_distill(_args(session_id, config_path))
    playbook = layout.playbook.read_text(encoding="utf-8")
    assert playbook.count("## ") >= 20
    assert "Evidence:" in playbook
    assert "F-000010" not in fake_llm.prompts[0]


@pytest.mark.usefixtures("block_network")
def test_e2e_complex_subprocess_pipeline(
    tmp_path: Path,
    complex_session_path: Path,
) -> None:
    session_id = "e2e-complex-sub"
    config_path, layout = _session_config(tmp_path, session_id)
    layout.trace_raw.write_text(complex_session_path.read_text(encoding="utf-8"), encoding="utf-8")

    base = [sys.executable, "-m", "falcon.cli", "--config", str(config_path)]
    for cmd in ("ingest", "analyze"):
        proc = subprocess.run(
            [*base, cmd, "--session", session_id],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[1],
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout

    steps = json.loads(layout.analysis.read_text(encoding="utf-8"))
    assert len(steps) >= 25
