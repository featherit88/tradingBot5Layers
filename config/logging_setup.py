"""Structured logging configuration for bot and backtest entry points."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class _JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


_HUMAN_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(
    *,
    json_format: bool = False,
    log_level: str = "INFO",
    log_file: str | None = None,
) -> None:
    """Configure the root logger.

    Args:
        json_format: If True, output JSON lines (for production / log aggregation).
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        log_file: Optional file path to write logs to (in addition to stderr).
    """
    root = logging.getLogger()

    # Clear existing handlers to make this idempotent
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    formatter = _JSONFormatter() if json_format else logging.Formatter(_HUMAN_FORMAT)

    # Console handler (stderr)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
