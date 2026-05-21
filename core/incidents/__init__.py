"""OSINT incident mapping pipeline (adapted from Telegram-OSINT-Incident-Mapping, MIT)."""

__all__ = [
    "run_full_pipeline",
    "run_pending_pipeline",
]


def run_pending_pipeline(*args, **kwargs):
    from core.incidents.pipeline import run_pending_pipeline as _fn

    return _fn(*args, **kwargs)


def run_full_pipeline(*args, **kwargs):
    from core.incidents.pipeline import run_full_pipeline as _fn

    return _fn(*args, **kwargs)
