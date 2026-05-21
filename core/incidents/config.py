"""Incident pipeline configuration from environment."""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def llm_provider() -> str:
    return (os.environ.get("INCIDENT_LLM_PROVIDER") or "anthropic").strip().lower()


def llm_is_configured() -> bool:
    """True when the selected provider has an API key in the environment."""
    if llm_provider() == "openai":
        return bool(os.environ.get("OPENAI_API_KEY", "").strip())
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def llm_model() -> str:
    default = (
        "claude-sonnet-4-20250514"
        if llm_provider() == "anthropic"
        else "gpt-4o-mini"
    )
    return (os.environ.get("INCIDENT_LLM_MODEL") or default).strip()


def batch_size(stage: str) -> int:
    key = f"INCIDENT_BATCH_{stage.upper()}"
    defaults = {"keyword": 64}
    default = defaults.get(stage, _int_env("INCIDENT_BATCH_SIZE", 16))
    return _int_env(key, default)


def poll_interval_sec() -> int:
    return _int_env("INCIDENT_POLL_INTERVAL_SEC", 300)


def poll_message_limit() -> int:
    return _int_env("INCIDENT_POLL_MESSAGE_LIMIT", 50)


def google_maps_api_key() -> str | None:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    return key or None


def telegram_creds_from_env() -> tuple[str, str, str] | None:
    phone = os.environ.get("TELEGRAM_PHONE", "").strip()
    api_id = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    if phone and api_id and api_hash:
        return phone, api_id, api_hash
    return _telegram_creds_from_secrets()


def _telegram_creds_from_secrets() -> tuple[str, str, str] | None:
    for path in (
        os.environ.get("STREAMLIT_SECRETS_PATH", ""),
        "/app/.streamlit/secrets.toml",
        ".streamlit/secrets.toml",
    ):
        if not path or not os.path.isfile(path):
            continue
        try:
            import tomllib

            with open(path, "rb") as fh:
                data = tomllib.load(fh)
            tg = data.get("telegram") or {}
            phone = str(tg.get("phone", "")).strip()
            api_id = str(tg.get("api_id", "")).strip()
            api_hash = str(tg.get("api_hash", "")).strip()
            if phone and api_id and api_hash:
                return phone, api_id, api_hash
        except Exception:
            continue
    return None


def apply_incidents_secrets() -> None:
    """Load [incidents] from secrets.toml into env when not already set."""
    for path in ("/app/.streamlit/secrets.toml", ".streamlit/secrets.toml"):
        if not os.path.isfile(path):
            continue
        try:
            import tomllib

            with open(path, "rb") as fh:
                inc = tomllib.load(fh).get("incidents") or {}
            mapping = {
                "INCIDENT_LLM_PROVIDER": "llm_provider",
                "INCIDENT_LLM_MODEL": "llm_model",
                "INCIDENT_POLL_INTERVAL_SEC": "poll_interval_sec",
                "ANTHROPIC_API_KEY": "anthropic_api_key",
                "OPENAI_API_KEY": "openai_api_key",
                "GOOGLE_MAPS_API_KEY": "google_maps_api_key",
            }
            for env_key, secret_key in mapping.items():
                if os.environ.get(env_key):
                    continue
                val = inc.get(secret_key)
                if val is not None and str(val).strip():
                    os.environ[env_key] = str(val).strip()
        except Exception:
            pass
        break
