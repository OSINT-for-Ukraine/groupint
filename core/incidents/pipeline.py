"""Orchestrate incident pipeline stages until queues are empty or max rounds."""

from __future__ import annotations

import logging
from typing import Any

from db.dal import GraphManager

from core.incidents.config import llm_is_configured
from core.incidents import stages

logger = logging.getLogger(__name__)

STAGE_RUNNERS = [
    ("keyword_prefilter", stages.run_keyword_prefilter_batch),
    ("clean", stages.run_clean_batch),
    ("filter", stages.run_filter_batch),
    ("dedupe", stages.run_dedupe),
    ("extract", stages.run_extract_batch),
    ("geocode", stages.run_geocode_batch),
    ("link", stages.run_link_incidents_batch),
]


def run_pending_pipeline(*, max_rounds_per_stage: int = 5) -> dict[str, Any]:
    """Run each stage repeatedly until no work or max rounds."""
    GraphManager.ensure_incident_constraints()
    if not llm_is_configured():
        logger.info(
            "Skipping incident LLM pipeline: set ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "(and INCIDENT_LLM_PROVIDER if using OpenAI)."
        )
        return {
            "skipped": True,
            "reason": "no_llm_api_key",
            "queue": GraphManager.incident_pipeline_counts(),
        }
    totals: dict[str, int] = {}
    for stage_name, runner in STAGE_RUNNERS:
        stage_total = 0
        for _ in range(max_rounds_per_stage):
            try:
                n = runner()
            except Exception as exc:
                logger.exception("Stage %s failed: %s", stage_name, exc)
                break
            stage_total += n
            if n == 0:
                break
        totals[stage_name] = stage_total
    totals["queue"] = GraphManager.incident_pipeline_counts()
    return totals


def run_full_pipeline(**kwargs: Any) -> dict[str, Any]:
    return run_pending_pipeline(**kwargs)
