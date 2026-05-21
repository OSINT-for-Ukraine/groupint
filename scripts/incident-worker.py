#!/usr/bin/env python3
"""Background incident monitor: poll watchlist channels and run LLM pipeline."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Repo root on path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.incidents.config import apply_incidents_secrets, llm_is_configured
from core.incidents.monitor import run_monitor_loop

apply_incidents_secrets()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("incident-worker")


def main() -> None:
    stop = asyncio.Event()

    def _stop(*_args: object) -> None:
        logger.info("Shutdown requested")
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    if not llm_is_configured():
        logger.warning(
            "ANTHROPIC_API_KEY / OPENAI_API_KEY not set — ingest will run, "
            "LLM pipeline skipped until keys are configured."
        )
    try:
        asyncio.run(run_monitor_loop(stop_event=stop))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logger.exception("Worker exited: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
