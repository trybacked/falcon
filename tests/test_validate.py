from __future__ import annotations

import json
from pathlib import Path

import pytest

from falcon.layout import SessionLayout
from falcon.validate import BundleError, validate_bundle, validate_manifest


def test_validate_manifest_consent_and_id(tmp_path: Path) -> None:
    layout = SessionLayout.create(str(tmp_path), "good")
    layout.manifest.write_text(
        json.dumps({"session_id": "good", "consent": True}),
        encoding="utf-8",
    )
    validate_manifest(layout)


def test_validate_manifest_rejects_wrong_folder(tmp_path: Path) -> None:
    layout = SessionLayout.create(str(tmp_path), "folder-a")
    layout.manifest.write_text(
        json.dumps({"session_id": "folder-b", "consent": True}),
        encoding="utf-8",
    )
    with pytest.raises(BundleError, match="does not match"):
        validate_manifest(layout)


def test_validate_bundle_with_fixture(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "synthetic_trace.jsonl"
    layout = SessionLayout.create(str(tmp_path), "bundle")
    layout.manifest.write_text(
        json.dumps({"session_id": "bundle", "consent": True}),
        encoding="utf-8",
    )
    layout.trace_raw.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    events = validate_bundle(layout)
    assert len(events) >= 8
