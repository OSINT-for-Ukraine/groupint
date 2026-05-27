"""OSINT incident mapping: watchlist, pipeline, map, export."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone

import folium
import streamlit as st

from core.incidents.atlos_csv_export import (
    DEFAULT_SENSITIVE as ATLOS_DEFAULT_SENSITIVE,
    DEFAULT_STATUS as ATLOS_DEFAULT_STATUS,
    incidents_to_atlos_csv_str,
)
from core.incidents.config import (
    apply_incidents_secrets,
    llm_provider,
    poll_interval_sec,
)
from core.incidents.geojson import incidents_to_geojson_str, incidents_to_json_str
from core.incidents.keywords import parse_keyword_lines
from core.incidents.watchlist_channels import (
    parse_channel_lines,
    parse_channels_from_upload,
)
from core.incidents.monitor import fetch_watchlist_now
from core.incidents.pipeline import run_pending_pipeline
from core.incidents.report import generate_incident_report
from core.login import run_until_complete
from core.tg_api_connector import normalize_telegram_group_ref
from db.dal import GraphManager
from streamlit_utils.telegram_auth import get_page_client, render_telegram_auth_panel

apply_incidents_secrets()

try:
    st.set_page_config(page_title="Incidents", layout="wide")
except Exception:
    pass
st.title("OSINT Incident Mapping")
st.caption(
    "Monitor Telegram channels, extract geocoded incidents via LLM pipeline. "
    "Adapted from [Telegram-OSINT-Incident-Mapping](https://github.com/Namithnp/Telegram-OSINT-Incident-Mapping) (MIT)."
)

GraphManager.ensure_incident_constraints()

# --- Telegram auth (required for manual fetch) ---
st.header("Telegram authentication")
render_telegram_auth_panel(page_id="incidents", location="main")
st.divider()

# --- Global keywords + scheduler ---
monitor_cfg = GraphManager.get_incident_monitor_config()

st.header("Global keyword filter")
st.caption(
    "Messages must match **at least one** keyword from the combined list "
    "(global + per-channel) to enter the incident pipeline. Leave filters disabled "
    "to process all messages."
)
gcol1, gcol2 = st.columns([1, 3])
with gcol1:
    global_kw_enabled = st.checkbox(
        "Enable global keywords",
        value=bool(monitor_cfg.get("global_keywords_enabled")),
        key="global_kw_enabled",
    )
with gcol2:
    global_kw_text = st.text_area(
        "Global keywords (one per line, or comma-separated)",
        value="\n".join(monitor_cfg.get("global_keywords") or []),
        height=100,
        key="global_kw_text",
    )
if st.button("Save global keywords", key="btn_save_global_kw"):
    GraphManager.upsert_incident_monitor_config(
        global_keywords=parse_keyword_lines(global_kw_text),
        global_keywords_enabled=global_kw_enabled,
    )
    st.success("Global keyword settings saved.")
    st.rerun()

st.header("Message fetch scheduler")
st.caption(
    "Automatic fetch runs in the **groupint-incident-worker** container on enabled "
    "watchlist channels. Changing the interval applies on the next worker cycle."
)
interval_presets = {
    "5 min": 300,
    "15 min": 900,
    "30 min": 1800,
    "1 hour": 3600,
    "2 hours": 7200,
    "6 hours": 21600,
    "Custom": -1,
}
current_interval = int(monitor_cfg.get("fetch_interval_sec") or poll_interval_sec())
preset_labels = list(interval_presets.keys())
default_preset = next(
    (label for label, sec in interval_presets.items() if sec == current_interval),
    "Custom",
)
if default_preset not in preset_labels:
    default_preset = "Custom"

s1, s2, s3 = st.columns(3)
with s1:
    scheduler_on = st.checkbox(
        "Enable automatic fetch",
        value=bool(monitor_cfg.get("scheduler_enabled")),
        key="scheduler_enabled",
    )
with s2:
    preset = st.selectbox(
        "Fetch interval",
        options=preset_labels,
        index=preset_labels.index(default_preset),
        key="fetch_interval_preset",
    )
with s3:
    run_after = st.checkbox(
        "Run pipeline after each fetch",
        value=bool(monitor_cfg.get("run_pipeline_after_fetch", True)),
        key="run_pipeline_after_fetch",
    )

custom_sec = current_interval
if preset == "Custom":
    custom_sec = st.number_input(
        "Custom interval (seconds)",
        min_value=60,
        max_value=86400,
        value=current_interval,
        step=60,
        key="fetch_interval_custom",
    )
else:
    custom_sec = interval_presets[preset]

last_fetch = monitor_cfg.get("last_fetch_at")
if last_fetch:
    try:
        last_dt = datetime.fromisoformat(str(last_fetch).replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        next_dt = last_dt + timedelta(seconds=custom_sec)
        st.caption(
            f"Last fetch: {last_fetch[:19]} UTC · Next fetch ~{next_dt.strftime('%Y-%m-%d %H:%M')} UTC "
            f"({'enabled' if scheduler_on else 'scheduler disabled'})"
        )
    except ValueError:
        st.caption(f"Last fetch: {last_fetch}")
else:
    st.caption(
        f"No fetch recorded yet. Scheduler: {'enabled' if scheduler_on else 'disabled'}."
    )

sc1, sc2 = st.columns(2)
with sc1:
    if st.button("Save scheduler", key="btn_save_scheduler"):
        GraphManager.upsert_incident_monitor_config(
            scheduler_enabled=scheduler_on,
            fetch_interval_sec=int(custom_sec),
            run_pipeline_after_fetch=run_after,
        )
        st.success("Scheduler settings saved.")
        st.rerun()
with sc2:
    fetch_now = st.button(
        "Fetch watchlist now",
        type="primary",
        key="btn_fetch_watchlist",
        disabled=not st.session_state.get("auth"),
    )
    if not st.session_state.get("auth"):
        st.caption("Authorize Telegram above to fetch manually.")

if fetch_now:
    client = get_page_client("incidents")
    if not client:
        st.error("No Telegram client. Connect above first.")
    else:
        with st.spinner("Fetching watchlist channels…"):
            try:
                summary = run_until_complete(
                    fetch_watchlist_now(
                        client,
                        run_pipeline=run_after,
                    )
                )
                st.success("Fetch completed")
                st.json(summary)
            except Exception as exc:
                st.error(f"Fetch failed: {exc}")

st.divider()

# --- Watchlist ---
st.header("Watchlist channels")


def _bulk_add_channels(refs: list[str], *, enabled: bool) -> int:
    for ref in refs:
        GraphManager.upsert_watchlist_channel(ref, enabled=enabled)
    return len(refs)


col_add, col_en = st.columns([3, 1])
with col_add:
    new_channel = st.text_input(
        "Channel (@name or t.me link)",
        placeholder="OsintTV or https://t.me/OsintTV",
        key="watchlist_add",
    )
with col_en:
    enabled_default = st.checkbox("Enabled", value=True, key="watchlist_enabled")

if st.button("Add to watchlist", key="btn_add_watchlist") and new_channel.strip():
    ref = normalize_telegram_group_ref(new_channel.strip())
    GraphManager.upsert_watchlist_channel(ref, enabled=enabled_default)
    st.success(f"Added `{ref}`")
    st.rerun()

with st.expander("Add multiple channels (paste or upload)", expanded=False):
    st.caption(
        "One channel per line, or separated by commas. "
        "Supports @name, username, or https://t.me/… links. "
        "Upload `.txt`, `.csv` (first column or header `channel_ref`), or `.json` (array of strings)."
    )
    bulk_text = st.text_area(
        "Paste channel list",
        height=120,
        placeholder="OsintTV\n@channel2\nhttps://t.me/channel3",
        key="watchlist_bulk_text",
    )
    bulk_file = st.file_uploader(
        "Or upload a file",
        type=["txt", "csv", "json"],
        key="watchlist_bulk_file",
    )
    bulk_enabled = st.checkbox(
        "Enabled for new channels",
        value=True,
        key="watchlist_bulk_enabled",
    )
    if st.button("Add all to watchlist", key="btn_bulk_watchlist"):
        refs: list[str] = []
        if bulk_file is not None:
            try:
                refs = parse_channels_from_upload(bulk_file)
            except Exception as exc:
                st.error(f"Could not read file: {exc}")
        pasted = parse_channel_lines(bulk_text) if bulk_text.strip() else []
        if pasted:
            refs = list(dict.fromkeys(refs + pasted))
        if not refs:
            st.warning("No channels found. Paste or upload a list first.")
        else:
            n = _bulk_add_channels(refs, enabled=bulk_enabled)
            st.success(f"Added **{n}** channel(s) to the watchlist.")
            st.rerun()

channels = GraphManager.list_watchlist_channels()
if channels:
    for ch in channels:
        ref = ch.get("channel_ref", "")
        with st.expander(f"**{ref}**", expanded=False):
            if ch.get("last_polled_at"):
                st.caption(f"Last poll: {ch['last_polled_at'][:19]}")
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                new_state = st.checkbox(
                    "Channel enabled",
                    value=bool(ch.get("enabled", True)),
                    key=f"wl_en_{ref}",
                )
            with c2:
                ch_kw_on = st.checkbox(
                    "Enable channel keywords",
                    value=bool(ch.get("keywords_enabled")),
                    key=f"wl_kw_en_{ref}",
                )
            with c3:
                use_global = st.checkbox(
                    "Also use global keywords",
                    value=bool(ch.get("use_global_keywords", True)),
                    key=f"wl_kw_global_{ref}",
                )
            ch_kw_text = st.text_area(
                "Channel keywords",
                value="\n".join(ch.get("keywords") or []),
                height=80,
                key=f"wl_kw_text_{ref}",
            )
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Save channel", key=f"wl_save_{ref}"):
                    GraphManager.upsert_watchlist_channel(
                        ref,
                        enabled=new_state,
                        keywords=parse_keyword_lines(ch_kw_text),
                        keywords_enabled=ch_kw_on,
                        use_global_keywords=use_global,
                    )
                    st.success(f"Saved `{ref}`")
                    st.rerun()
            with b2:
                if st.button("Remove", key=f"wl_del_{ref}"):
                    GraphManager.delete_watchlist_channel(ref)
                    st.rerun()
else:
    st.info("No watchlist channels yet. Add OSINT Telegram channels to monitor.")

st.divider()

# --- Pipeline status ---
st.header("Pipeline queue")
try:
    counts = GraphManager.incident_pipeline_counts()
    if counts:
        st.json(counts)
    else:
        st.caption("No messages in Neo4j yet, or pipeline idle.")
except Exception as exc:
    st.warning(f"Could not load queue counts: {exc}")

st.caption(f"LLM provider: `{llm_provider()}` (set INCIDENT_LLM_PROVIDER / API keys)")

if st.button("Run pipeline now", type="primary", key="btn_run_pipeline"):
    with st.spinner("Running incident pipeline…"):
        try:
            result = run_pending_pipeline(max_rounds_per_stage=10)
            st.success("Pipeline finished")
            st.json(result)
        except Exception as exc:
            st.error(f"Pipeline failed: {exc}")

st.divider()

# --- Map & export ---
st.header("Incident map")
today = date.today()
default_from = today - timedelta(days=7)
d1, d2, d3 = st.columns(3)
with d1:
    date_from = st.date_input("From", value=default_from)
with d2:
    date_to = st.date_input("To", value=today)
with d3:
    category_filter = st.selectbox(
        "Category",
        options=["(all)"] + sorted(
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
        ),
    )

date_from_s = date_from.isoformat() if date_from else None
date_to_s = date_to.isoformat() + "T23:59:59" if date_to else None
cat = None if category_filter == "(all)" else category_filter

incidents = GraphManager.list_incidents_for_map(
    date_from=date_from_s,
    date_to=date_to_s,
    category=cat,
    limit=2000,
)

if incidents:
    st.write(f"**{len(incidents)}** incidents with coordinates")

    m = folium.Map(location=[20, 0], zoom_start=2)
    for inc in incidents:
        lat, lon = inc.get("lat"), inc.get("lon")
        if lat is None or lon is None:
            continue
        popup = (
            f"<b>{inc.get('category')}</b><br>"
            f"{inc.get('location_text')}<br>"
            f"{(inc.get('summary') or '')[:300]}"
        )
        folium.Marker(
            [float(lat), float(lon)],
            popup=folium.Popup(popup, max_width=300),
            tooltip=inc.get("category"),
        ).add_to(m)

    st.components.v1.html(m._repr_html_(), height=500, scrolling=True)

    geojson_str = incidents_to_geojson_str(incidents)
    st.download_button(
        "Download GeoJSON",
        data=geojson_str,
        file_name="incidents.geojson",
        mime="application/geo+json",
    )

    st.download_button(
        "Download JSON",
        data=incidents_to_json_str(incidents),
        file_name="incidents.json",
        mime="application/json",
    )

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "id",
            "category",
            "location_text",
            "lat",
            "lon",
            "occurred_at",
            "summary",
            "source_group_id",
        ],
    )
    writer.writeheader()
    for inc in incidents:
        writer.writerow({k: inc.get(k) for k in writer.fieldnames})
    st.download_button(
        "Download CSV",
        data=buf.getvalue(),
        file_name="incidents.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("Export for Atlos (manual bulk import)")
    st.caption(
        "Download a CSV for **Atlos cloud** bulk import. Required columns: "
        "`status`, `description`, `sensitive` (lowercase). "
        "Optional `geolocation` as `latitude,longitude` — confirm column names in your "
        "project’s **Manage → Bulk import** docs if import fails."
    )
    atlos_status = st.selectbox(
        "Default status column",
        ["To Do", "Unclaimed", "In Progress"],
        index=0,
        key="atlos_csv_status",
    )
    atlos_sensitive = st.text_input(
        "Default sensitive column",
        value=ATLOS_DEFAULT_SENSITIVE,
        key="atlos_csv_sensitive",
    )
    atlos_csv = incidents_to_atlos_csv_str(
        incidents,
        status=atlos_status,
        sensitive=atlos_sensitive.strip() or ATLOS_DEFAULT_SENSITIVE,
        require_coordinates=True,
    )
    st.download_button(
        "Download CSV for Atlos bulk import",
        data=atlos_csv,
        file_name="incidents-atlos-import.csv",
        mime="text/csv",
        type="primary",
        key="btn_atlos_csv_download",
    )
    st.markdown(
        """
1. Open your project on [platform.atlos.org](https://platform.atlos.org).
2. Go to **Manage** → scroll to **Bulk import**.
3. **Upload a file** → review → **Publish to Atlos**.

See `docs/incidents/atlos-export.md` in the repository for column details.
        """
    )

    # API export disabled — use CSV bulk import to cloud Atlos.
    ATLOS_API_EXPORT_ENABLED = False
    if ATLOS_API_EXPORT_ENABLED:
        from core.incidents.atlos_export import (
            atlos_config,
            export_incidents_batch,
            normalize_base_url,
            test_atlos_connection,
        )
        from core.incidents.config import (
            apply_atlos_secrets,
            default_atlos_api_token,
            default_atlos_base_url,
        )

        apply_atlos_secrets()
        st.subheader("Export to Atlos (API)")
        st.caption("Push filtered incidents to Atlos via API v2.")
        monitor_cfg = GraphManager.get_incident_monitor_config()
        env_base = default_atlos_base_url()
        env_token = default_atlos_api_token()
        saved_base = monitor_cfg.get("atlos_base_url") or env_base
        saved_token = monitor_cfg.get("atlos_api_token") or env_token

        preset = st.selectbox(
            "URL preset",
            ["Local Docker (atlos:4000)", "Cloud (platform.atlos.org)", "Custom"],
            key="atlos_url_preset",
        )
        preset_urls = {
            "Local Docker (atlos:4000)": "http://atlos:4000",
            "Cloud (platform.atlos.org)": "https://platform.atlos.org",
        }
        default_url = preset_urls.get(preset, saved_base)

        ac1, ac2 = st.columns(2)
        with ac1:
            atlos_url_input = st.text_input(
                "Atlos API base URL",
                value=default_url if preset != "Custom" else saved_base,
                key="atlos_base_url_input",
            )
        with ac2:
            atlos_token_input = st.text_input(
                "Atlos API token",
                value=saved_token,
                type="password",
                key="atlos_token_input",
            )

        skip_exported = st.checkbox(
            "Skip incidents already exported to Atlos",
            value=True,
            key="atlos_skip_exported",
        )
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            if st.button("Save Atlos settings", key="btn_save_atlos"):
                GraphManager.upsert_incident_monitor_config(
                    atlos_base_url=normalize_base_url(atlos_url_input),
                    atlos_api_token=atlos_token_input.strip(),
                )
                st.success("Atlos settings saved.")
                st.rerun()
        with sc2:
            if st.button("Reset to .env defaults", key="btn_atlos_reset"):
                GraphManager.upsert_incident_monitor_config(
                    atlos_base_url=env_base,
                    atlos_api_token=env_token,
                )
                st.rerun()
        with sc3:
            if st.button("Test Atlos connection", key="btn_atlos_test"):
                cfg = atlos_config()
                ok, msg = test_atlos_connection(
                    atlos_url_input or cfg["base_url"],
                    atlos_token_input or cfg["api_token"],
                )
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        if st.button(
            "Export filtered incidents to Atlos",
            type="primary",
            key="btn_atlos_export",
        ):
            cfg = atlos_config()
            base = normalize_base_url(atlos_url_input) or cfg["base_url"]
            token = (atlos_token_input or cfg["api_token"]).strip()
            if not token:
                st.error("Set an Atlos API token before exporting.")
            else:
                to_export = GraphManager.list_incidents_for_export(
                    date_from=date_from_s,
                    date_to=date_to_s,
                    category=cat,
                    skip_exported=skip_exported,
                )
                with st.spinner(f"Exporting {len(to_export)} incident(s)…"):
                    result = export_incidents_batch(
                        to_export,
                        base_url=base,
                        api_token=token,
                        skip_exported=skip_exported,
                    )
                st.success(
                    f"Created **{result['created']}**, skipped **{result['skipped']}**, "
                    f"failed **{result['failed']}**"
                )
                if result.get("errors"):
                    with st.expander("Export errors"):
                        for err in result["errors"][:50]:
                            st.write(err)
                st.rerun()
else:
    st.info("No geocoded incidents in this range. Run the pipeline after fetching messages.")

if st.button("Generate intelligence report", key="btn_report"):
    with st.spinner("Generating report…"):
        try:
            report = generate_incident_report(
                date_from=date_from_s,
                date_to=date_to_s,
            )
            st.markdown(report)
        except Exception as exc:
            st.error(f"Report failed: {exc}")
