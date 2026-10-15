from __future__ import annotations

from PIL import Image, ImageGrab


class PilGrabber:
    def grab(self) -> Image.Image | None:
        try:
            return ImageGrab.grab()
        except OSError:
            return None
