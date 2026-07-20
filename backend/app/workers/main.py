"""
Background worker process (Module 12).

Runs as a separate container/pod for async workloads (meeting queue stats,
future job consumers). Does not introduce new AI features.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from app.core.logging import setup_logging
from app.services.meeting_jobs import meeting_job_queue

logger = logging.getLogger(__name__)
_shutdown = asyncio.Event()


def _handle_signal(*_: object) -> None:
    _shutdown.set()


async def _run() -> None:
    setup_logging()
    logger.info("Worker started — meeting queue monitor")
    while not _shutdown.is_set():
        stats = meeting_job_queue.stats()
        logger.info("worker.heartbeat queue=%s", stats)
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            continue
    logger.info("Worker shutting down")


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _handle_signal())
    loop.run_until_complete(_run())


if __name__ == "__main__":
    main()
