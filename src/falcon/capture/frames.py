from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from imagehash import ImageHash, phash
from PIL import Image

from falcon.models import FrameRef


class FrameStore:
    def __init__(self, session_root: Path, dedup_hamming: int) -> None:
        self._dir = session_root / "frames"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index = session_root / "frames.json"
        self._dedup = dedup_hamming
        self.frames: list[FrameRef] = []
        if self._index.is_file():
            self.frames = [FrameRef(**x) for x in json.loads(self._index.read_text())]
        self._last: ImageHash | None = None

    def save(self, image: Image.Image, ts: float | None = None) -> FrameRef | None:
        ts = time.time() if ts is None else ts
        h = phash(image)
        if self._last is not None and h - self._last <= self._dedup:
            return None
        frame_id = f"F-{int(ts * 1000):013d}"
        rel = f"frames/{frame_id}.jpg"
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(self._dir / f"{frame_id}.jpg", "JPEG", quality=70)
        ref = FrameRef(frame_id, rel, ts, str(h))
        self.frames.append(ref)
        self._last = h
        self._index.write_text(json.dumps([asdict(f) for f in self.frames], indent=1))
        return ref
