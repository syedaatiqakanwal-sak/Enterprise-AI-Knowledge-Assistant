"""
Enterprise logging configuration (Module 12).

- Structured JSON logs in staging/production (or LOG_JSON=true)
- Console + rotating app/error files
- Request / correlation IDs via contextvars
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from app.core.config import Environment, settings

try:
    from colorlog import ColoredFormatter

    _COLORLOG_AVAILABLE = True
except ImportError:  # pragma: no cover
    _COLORLOG_AVAILABLE = False


request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_PLAIN_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
)
_COLOR_FORMAT = (
    "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s%(reset)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}

_configured = False


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for aggregation (ELK / CloudWatch / Loki)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
            "environment": settings.ENVIRONMENT.value,
            "version": settings.PROJECT_VERSION,
        }
        rid = request_id_ctx.get()
        cid = correlation_id_ctx.get()
        if rid:
            payload["request_id"] = rid
        if cid:
            payload["correlation_id"] = cid
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def set_request_ids(*, request_id: str | None, correlation_id: str | None = None) -> None:
    request_id_ctx.set(request_id)
    correlation_id_ctx.set(correlation_id or request_id)


def clear_request_ids() -> None:
    request_id_ctx.set(None)
    correlation_id_ctx.set(None)


def _use_json() -> bool:
    return bool(settings.LOG_JSON) or settings.ENVIRONMENT in (
        Environment.PRODUCTION,
        Environment.STAGING,
    )


def _build_console_handler(level: int) -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    if _use_json():
        handler.setFormatter(JsonFormatter())
        return handler

    use_color = (
        settings.ENVIRONMENT == Environment.DEVELOPMENT
        and _COLORLOG_AVAILABLE
        and sys.stdout.isatty()
    )
    if use_color:
        formatter: logging.Formatter = ColoredFormatter(
            _COLOR_FORMAT,
            datefmt=_DATE_FORMAT,
            log_colors=_LOG_COLORS,
        )
    else:
        formatter = logging.Formatter(_PLAIN_FORMAT, datefmt=_DATE_FORMAT)
    handler.setFormatter(formatter)
    return handler


def _build_rotating_file_handler(
    path: Path,
    level: int,
    max_bytes: int,
    backup_count: int,
) -> logging.Handler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        filename=str(path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(
        JsonFormatter() if _use_json() else logging.Formatter(_PLAIN_FORMAT, datefmt=_DATE_FORMAT)
    )
    return handler


def setup_logging(force: bool = False) -> None:
    global _configured
    if _configured and not force:
        return

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)

    root.addHandler(_build_console_handler(log_level))
    root.addHandler(
        _build_rotating_file_handler(
            log_dir / "app.log",
            level=log_level,
            max_bytes=settings.LOG_MAX_BYTES,
            backup_count=settings.LOG_BACKUP_COUNT,
        )
    )
    root.addHandler(
        _build_rotating_file_handler(
            log_dir / "error.log",
            level=logging.ERROR,
            max_bytes=settings.LOG_MAX_BYTES,
            backup_count=settings.LOG_BACKUP_COUNT,
        )
    )

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True

    if settings.is_production or settings.is_staging:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)

    _configured = True
    logging.getLogger(__name__).info(
        "Logging initialized | env=%s | level=%s | json=%s | dir=%s",
        settings.ENVIRONMENT.value,
        settings.LOG_LEVEL,
        _use_json(),
        log_dir,
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    if not _configured:
        setup_logging()
    return logging.getLogger(name if name else __name__)
