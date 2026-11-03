"""Logs go to stdout for journalctl and to a size-limited file that can be copied off the VM.

Logs leave the VM, so they hold IDs and timings only, never words or opinions.
"""

import logging
import logging.handlers
from pathlib import Path

from .config import ROOT, settings


def setup(name: str) -> None:
    cfg = settings()
    folder = Path(cfg.log_dir)
    if not folder.is_absolute():
        folder = ROOT / folder
    folder.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file = logging.handlers.RotatingFileHandler(
        folder / f"{name}.log", maxBytes=cfg.log_max_bytes, backupCount=cfg.log_backups
    )
    stream = logging.StreamHandler()
    root = logging.getLogger()
    root.handlers.clear()
    for handler in (file, stream):
        handler.setFormatter(fmt)
        root.addHandler(handler)
    root.setLevel(logging.INFO)
