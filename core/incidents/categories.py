"""Closed incident category labels."""

INCIDENT_CATEGORIES = frozenset(
    {
        "attack",
        "explosion",
        "shelling",
        "drone_strike",
        "air_strike",
        "air_activity",
        "raid_search",
        "arrest_detention",
        "movement",
        "infrastructure",
        "casualties",
        "other",
    }
)


def normalize_category(raw: str | None) -> str:
    if not raw:
        return "other"
    value = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if value in INCIDENT_CATEGORIES:
        return value
    aliases = {
        "ied": "explosion",
        "bombing": "air_strike",
        "shooting": "attack",
        "clash": "attack",
    }
    return aliases.get(value, "other")
