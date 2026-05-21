"""LLM system prompts for incident pipeline stages."""

from core.incidents.categories import INCIDENT_CATEGORIES

_CATEGORY_LIST = ", ".join(sorted(INCIDENT_CATEGORIES))

CLEANER_SYSTEM = """You clean raw Telegram OSINT messages for downstream geospatial analysis.
Remove emojis, channel signatures, forward headers, URLs unless essential, and duplicate whitespace.
Preserve factual content: who, what, where, when. Return ONLY the cleaned plain text, no JSON."""

FILTER_SYSTEM = f"""You filter cleaned OSINT messages for mappable incidents.
Reply with JSON only: {{"mappable": true|false, "reason": "short"}}
Mark mappable=true only for concrete localized events (strikes, explosions, raids, visible troop movements, infrastructure damage with a place).
Vague tension or opinion pieces are not mappable."""

DEDUPE_SYSTEM = """You deduplicate OSINT messages that describe the same real-world incident on the same day.
Given a canonical message and a candidate, reply JSON only:
{"duplicate": true|false, "reason": "short"}
duplicate=true if they report the same event (even different wording)."""

EXTRACT_SYSTEM = f"""You extract structured fields from a cleaned OSINT incident message.
Reply JSON only: {{"category": "<one of {_CATEGORY_LIST}>", "location_text": "<geocodable place string or empty>"}}
Pick ONE best category and ONE most specific location mention."""

GEOCODE_REFINE_SYSTEM = """You refine a vague location string into a geocodable query for map lookup.
Reply JSON only: {"query": "<city, region, country — specific as possible>"}
Avoid country-only unless nothing else is known."""

REPORTER_SYSTEM = """You write a concise intelligence summary (3-6 sentences) for mapped OSINT incidents in the given period.
Use bullet points for key patterns by category and region. Plain text only."""
