# Rev 1
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOG_DIR, LOG_LEVEL

_FORMATTER = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_LOG_FILE = LOG_DIR / "slv_assistant.log"
_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per file
_BACKUP_COUNT = 3

_root_configured = False


def _configure_root() -> None:
    global _root_configured
    if _root_configured:
        return

    root = logging.getLogger("slv")
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    fh = RotatingFileHandler(
        _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    fh.setFormatter(_FORMATTER)

    ch = logging.StreamHandler()
    ch.setFormatter(_FORMATTER)

    root.addHandler(fh)
    root.addHandler(ch)
    root.propagate = False
    _root_configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(f"slv.{name}")
