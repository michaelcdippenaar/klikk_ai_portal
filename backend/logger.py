"""
Structured logging for the Klikk AI Portal.

Logs are written to:
  - logs/portal.log        (all levels, rotating daily)
  - logs/errors.log        (ERROR+ only, rotating daily)
  - stdout                 (INFO+)

Usage:
    from logger import log
    log.info("Agent started", extra={"session_id": "abc"})
    log.error("TM1 member not found", extra={"tool": "tm1_query_mdx", "detail": str(e)})
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from pathlib import Path


LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class JSONFormatter(logging.Formatter):
    """Structured JSON log lines for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        # Merge any extra fields passed via log.info(..., extra={...})
        for key in ("session_id", "tool", "detail", "mdx", "error_type",
                     "element", "dimension", "cube", "user_message",
                     "duration_ms", "provider", "model"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = self._format_exception(record)
        return json.dumps(entry, default=str)

    def _format_exception(self, record: logging.LogRecord) -> str:
        import traceback
        return "".join(traceback.format_exception(*record.exc_info))


class ReadableFormatter(logging.Formatter):
    """Human-readable format for stdout."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        tool = getattr(record, "tool", "")
        prefix = f"[{tool}] " if tool else ""
        return f"{ts} {record.levelname:<5} {prefix}{record.getMessage()}"


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("klikk_portal")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # --- File handler: all logs (rotating daily, keep 30 days) ---
    all_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_DIR / "portal.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(JSONFormatter())
    logger.addHandler(all_handler)

    # --- File handler: errors only (rotating daily, keep 90 days) ---
    err_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_DIR / "errors.log",
        when="midnight",
        backupCount=90,
        encoding="utf-8",
    )
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(JSONFormatter())
    logger.addHandler(err_handler)

    # --- Stdout handler ---
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(ReadableFormatter())
    logger.addHandler(console)

    return logger


log = _setup_logger()
