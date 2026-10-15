from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
import warnings
from pathlib import Path

from falcon import __version__
from falcon.capture.factory import create_backend
from falcon.capture.runner import run_python_recorder
from falcon.config import AppConfig, load_config, resolve_config_path
from falcon.distill import run_distill
from falcon.layout import SessionLayout
from falcon.llm import build_client
from falcon.log import configure_logging
from falcon.models import ActionStep
from falcon.native_recorder import native_recorder_binary
from falcon.pipeline import normalize_and_write_raw, run_analyze_pipeline
from falcon.validate import BundleError, validate_bundle


def _cfg(args: argparse.Namespace) -> AppConfig:
    return load_config(resolve_config_path(args.config))


def _layout(args: argparse.Namespace, cfg: AppConfig) -> SessionLayout:
    if args.session:
        return SessionLayout(Path(cfg.paths.sessions_root) / args.session)
    return SessionLayout.latest(cfg.paths.sessions_root)


def _print_record_summary(layout: SessionLayout) -> None:
    print(f"trace: {layout.trace_raw}")
    apps: set[str] = set()
    if layout.trace_raw.is_file():
        for line in layout.trace_raw.read_text(encoding="utf-8").splitlines():
            if line.strip():
                app = json.loads(line).get("app")
                if app:
                    apps.add(str(app))
    if apps:
        print(f"apps in trace: {', '.join(sorted(apps))}")


def _cmd_record_native(layout: SessionLayout, binary: Path) -> None:
    layout.root.mkdir(parents=True, exist_ok=True)
    print(f"recording {layout.root.name} — Ctrl+C to stop")
    proc = subprocess.Popen([str(binary), "--output", str(layout.trace_raw)])

    def on_sig(*_: object) -> None:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)

    prev = signal.signal(signal.SIGINT, on_sig)
    try:
        rc = proc.wait()
    finally:
        signal.signal(signal.SIGINT, prev)

    if rc not in (0, -2, 130, 255):
        sys.exit(rc)
    _print_record_summary(layout)


def _write_manifest(layout: SessionLayout, sid: str) -> None:
    layout.manifest.write_text(
        json.dumps(
            {"session_id": sid, "consent": True, "version": __version__, "platform": sys.platform},
            indent=1,
        ),
        encoding="utf-8",
    )


def cmd_record(args: argparse.Namespace) -> None:
    cfg = _cfg(args)
    sid = args.name or time.strftime("session-%Y%m%d-%H%M%S")
    layout = SessionLayout.create(cfg.paths.sessions_root, sid)
    _write_manifest(layout, sid)

    if sys.platform == "darwin":
        if getattr(args, "legacy_python", False):
            warnings.warn(
                "Python capture on macOS is deprecated; prefer the Swift falcon-recorder.",
                DeprecationWarning,
                stacklevel=1,
            )
            from falcon.capture.macos import MacOSBackend

            backend = MacOSBackend()
            hint = None
            if not backend._clicks.active:
                hint = (
                    "Input Monitoring off: enable Python/Cursor under "
                    "Privacy → Input Monitoring to capture clicks."
                )
            run_python_recorder(layout, backend, cfg.capture, warn_input_monitoring=hint)
            _print_record_summary(layout)
            return

        binary = native_recorder_binary()
        if binary is None:
            print(
                "Swift falcon-recorder not built. Run:\n"
                "  cd packages/platform-macos && swift build -c release\n"
                "Or use deprecated PyObjC capture: falcon record --legacy-python",
                file=sys.stderr,
            )
            sys.exit(1)
        _cmd_record_native(layout, binary)
        return

    backend = create_backend()
    run_python_recorder(layout, backend, cfg.capture)
    _print_record_summary(layout)


def cmd_check(args: argparse.Namespace) -> None:
    cfg = _cfg(args)
    layout = _layout(args, cfg)
    try:
        events = validate_bundle(layout)
    except BundleError as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"ok: {len(events)} events, session {layout.root.name}")


def cmd_ingest(args: argparse.Namespace) -> None:
    cfg = _cfg(args)
    layout = _layout(args, cfg)
    try:
        events = normalize_and_write_raw(layout)
    except (BundleError, FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    print(f"ingested {len(events)} events -> {layout.trace_raw}")


def cmd_analyze(args: argparse.Namespace) -> None:
    cfg = _cfg(args)
    layout = _layout(args, cfg)
    try:
        steps = run_analyze_pipeline(layout, cfg)
    except (BundleError, FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    print(f"{len(steps)} steps -> {layout.analysis}")


def cmd_distill(args: argparse.Namespace) -> None:
    cfg = _cfg(args)
    layout = _layout(args, cfg)
    if not layout.analysis.is_file():
        print(f"missing {layout.analysis}; run analyze first", file=sys.stderr)
        sys.exit(1)
    steps = [ActionStep(**s) for s in json.loads(layout.analysis.read_text(encoding="utf-8"))]
    try:
        client = build_client(cfg.llm)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    playbook, prop, cq = run_distill(steps, client, cfg.output)
    layout.playbook.write_text(playbook, encoding="utf-8")
    layout.ontology.write_text(prop, encoding="utf-8")
    layout.questions.write_text(cq, encoding="utf-8")
    print(f"outputs in {layout.root}")


def cmd_report(args: argparse.Namespace) -> None:
    cfg = _cfg(args)
    layout = _layout(args, cfg)
    if not layout.playbook.is_file():
        print(f"missing {layout.playbook}; run distill first", file=sys.stderr)
        sys.exit(1)
    print(layout.playbook.read_text(encoding="utf-8"))


def main() -> None:
    configure_logging()
    p = argparse.ArgumentParser(
        prog="falcon",
        description="Local UI shadowing: record → ingest → analyze → distill → report.",
    )
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config", help="Path to config.toml (default: ./config.toml or FW_CONFIG)")
    sub = p.add_subparsers(dest="cmd", required=True)

    record_sp = sub.add_parser("record", help="Capture a session (Swift on macOS, UIA on Windows)")
    record_sp.add_argument("--session", help=argparse.SUPPRESS)
    record_sp.add_argument("--name", help="Session id (default: session-YYYYMMDD-HHMMSS)")
    record_sp.add_argument(
        "--legacy-python",
        action="store_true",
        help="Deprecated PyObjC capture on macOS only",
    )
    record_sp.set_defaults(fn=cmd_record)

    for name, fn, help_text in (
        ("check", cmd_check, "Validate manifest + trace.raw without writing outputs"),
        ("ingest", cmd_ingest, "Normalize recorder JSONL to CaptureEvent rows in trace.raw"),
        ("analyze", cmd_analyze, "Scrub PII, segment, build analysis.json"),
        ("distill", cmd_distill, "LLM ontology/CQ + playbook.md (requires API key)"),
        ("report", cmd_report, "Print playbook.md to stdout"),
    ):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--session", help="Session folder name under sessions_root")
        sp.set_defaults(fn=fn)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
