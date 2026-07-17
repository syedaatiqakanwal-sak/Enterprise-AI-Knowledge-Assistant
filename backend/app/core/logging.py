"""
Enterprise logging configuration.

Features
--------
- Console logging (colored in development)
- Rotating application log file
- Dedicated rotating error log file
- Environment-aware log levels
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from app.core.config import Environment, settings

try:
    from colorlog import ColoredFormatter

    _COLORLOG_AVAILABLE = True
except ImportError:  # pragma: no cover - optional at install time
    _COLORLOG_AVAILABLE = False


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


def _build_console_handler(level: int) -> logging.Handler:
    """Create a console StreamHandler, colored in development when possible."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

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
    """Create a rotating file handler writing to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        filename=str(path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_PLAIN_FORMAT, datefmt=_DATE_FORMAT))
    return handler


def setup_logging(force: bool = False) -> None:
    """
    Initialize enterprise logging once for the process.

    Parameters
    ----------
    force:
        Reconfigure even if logging was already set up (useful in tests).
    """
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

    # Keep uvicorn loggers aligned without duplicating handlers
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True

    # Quiet noisy third-party libraries in production
    if settings.is_production:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)

    _configured = True
    logging.getLogger(__name__).info(
        "Logging initialized | env=%s | level=%s | dir=%s",
        settings.ENVIRONMENT.value,
        settings.LOG_LEVEL,
        log_dir,
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a named logger (ensures setup has run)."""
    if not _configured:
        setup_logging()
    return logging.getLogger(name if name else __name__)
