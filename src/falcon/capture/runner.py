from __future__ import annotations

import signal
import sys
import threading

from falcon.capture.frames import FrameStore
from falcon.capture.grabber import PilGrabber
from falcon.capture.recorder import CaptureBackend, SessionRecorder
from falcon.config import CaptureConfig
from falcon.layout import SessionLayout


def run_python_recorder(
    layout: SessionLayout,
    backend: CaptureBackend,
    capture: CaptureConfig,
    *,
    warn_input_monitoring: str | None = None,
) -> None:
    ok, reason = backend.is_ready()
    if not ok:
        print(reason, file=sys.stderr)
        sys.exit(1)
    if warn_input_monitoring:
        print(warn_input_monitoring, file=sys.stderr)

    frames = FrameStore(layout.root, capture.dedup_hamming)
    recorder = SessionRecorder(layout, backend, PilGrabber(), frames, capture)
    stop = threading.Event()
    record_error: list[BaseException] = []

    def run_recorder() -> None:
        try:
            recorder.run(stop)
        except BaseException as exc:
            record_error.append(exc)
            stop.set()

    def on_sig(*_: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, on_sig)
    thread = threading.Thread(target=run_recorder, daemon=True)
    thread.start()
    print(f"recording {layout.root.name} — Ctrl+C to stop")
    while not stop.wait(0.2):
        if not thread.is_alive() and record_error:
            print(str(record_error[0]), file=sys.stderr)
            sys.exit(1)
    thread.join(timeout=5)
    if record_error:
        print(str(record_error[0]), file=sys.stderr)
        sys.exit(1)
