"""Shared utilities: logging, JSON persistence, time helpers."""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import config


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-18s | %(message)s"


def configure_logging(level: str | None = None) -> None:
    """Initialise a single root logger. Safe to call multiple times."""
    lvl = (level or config.LOG_LEVEL).upper()
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(handler)
    root.setLevel(lvl)
    # Quiet some noisy libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("socketio").setLevel(logging.WARNING)
    logging.getLogger("engineio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------
def now_ts() -> float:
    return time.time()


def fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


# ---------------------------------------------------------------------------
# JSON persistence
# ---------------------------------------------------------------------------
class JsonListStore:
    """Append-only JSON-lines store with thread-safe reads.

    Each line in the file is one JSON object. Used for alerts and
    predictions logs (REQ: data retention / alert log persistence).
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, obj: dict[str, Any]) -> None:
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(obj, default=str) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        items: list[dict[str, Any]] = []
        with self._lock:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return items

    def update(self, predicate, patch: dict[str, Any]) -> int:
        """Update records matching predicate in-place.

        Returns the number of records updated.
        """
        items = self.read_all()
        updated = 0
        for item in items:
            if predicate(item):
                item.update(patch)
                updated += 1
        with self._lock:
            with self.path.open("w", encoding="utf-8") as fh:
                for item in items:
                    fh.write(json.dumps(item, default=str) + "\n")
        return updated


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
def chunked(iterable: Iterable, size: int):
    buf = []
    for item in iterable:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf
