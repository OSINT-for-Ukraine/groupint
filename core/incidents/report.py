"""Generate intelligence summary for mapped incidents."""

from __future__ import annotations

from db.dal import GraphManager

from core.incidents.llm_client import complete_text
from core.incidents.prompts import REPORTER_SYSTEM


def generate_incident_report(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
) -> str:
    incidents = GraphManager.list_incidents_for_map(
        date_from=date_from, date_to=date_to, limit=limit
    )
    if not incidents:
        return "No geocoded incidents in the selected period."
    lines = []
    for inc in incidents[:50]:
        lines.append(
            f"- [{inc.get('category')}] {inc.get('location_text')} "
            f"({inc.get('occurred_at', '')[:10]}): "
            f"{(inc.get('summary') or '')[:200]}"
        )
    user = (
        f"Period: {date_from or 'any'} to {date_to or 'any'}\n"
        f"Count: {len(incidents)}\n\nIncidents:\n" + "\n".join(lines)
    )
    return complete_text(REPORTER_SYSTEM, user, max_tokens=1500)
