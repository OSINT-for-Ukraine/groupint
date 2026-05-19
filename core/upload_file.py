import json

import pandas as pd

from core.tg_api_connector import normalize_telegram_group_ref
from db.dal import GraphManager


def parse_json_users(uploaded_file) -> dict[str, int]:
    """Import JSON export into Neo4j (users with group lists per entry)."""
    json_data = json.load(uploaded_file)
    return GraphManager.import_json_users(json_data)


def parse_xls_users(uploaded_file, group_ref: str) -> int:
    """Import XLSX member list for a single group into Neo4j."""
    ref = normalize_telegram_group_ref(group_ref)
    if not ref:
        raise ValueError("Group ref is required for XLSX import (e.g. Republic_of_Gagazia_Chat).")

    contents = uploaded_file.getvalue()
    with pd.ExcelFile(contents) as file:
        xls = pd.read_excel(file)

    id_col = next((c for c in xls.columns if str(c).lower().replace(" ", "") in ("userid", "id")), None)
    name_col = next(
        (c for c in xls.columns if str(c).lower() in ("username", "user name", "name")),
        None,
    )
    if id_col is None:
        raise ValueError("XLSX must have a 'User ID' or 'id' column.")

    users: list[tuple] = []
    for _, row in xls.iterrows():
        raw_id = row[id_col]
        if pd.isna(raw_id):
            continue
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        username = ""
        if name_col is not None and not pd.isna(row[name_col]):
            username = str(row[name_col])
        users.append((user_id, username, username))

    return GraphManager.add_extracted_group_members(
        ref,
        users,
        group_title=ref,
        scrape_source="file_xlsx",
    )
