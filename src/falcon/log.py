from __future__ import annotations

import logging
import os

LOG = logging.getLogger("falcon")


def configure_logging() -> None:
    level = logging.DEBUG if os.environ.get("FW_DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )
