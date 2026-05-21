# Telegram sessions and authentication

Groupint persists Telethon **StringSession** files so you usually log in once per phone number, then reconnect without repeating OTP on every page load.

## UI flow (main app and Incidents)

1. Open Groupint (http://localhost:18501).
2. Confirm **Phone number**, **Api id**, **Api hash** (from secrets or manual entry).
3. In the sidebar, expand **Telegram sessions** to see saved sessions and health.
4. Click **Create / connect Telegram client**.
   - If a `.string` file exists for that phone → reconnect without OTP.
   - Otherwise → Telegram sends a login code to your Telegram app.
5. Enter the code and click **Verify secret code**.
6. On success, the session is written to disk and shown as connected.

The **Incidents** page uses the same auth panel (`streamlit_utils/telegram_auth.py`).

## Where sessions are stored

| Item | Location |
|------|----------|
| Session file | `GROUPINT_SESSIONS_DIR/<sanitized_phone>.string` |
| Metadata | `<phone>.meta` — `authorized_at`, `last_used_at`, `last_check_ok`, etc. |

In Docker Desktop stack: `/home/appuser/.groupint/sessions/` inside `groupint-streamlit` (persisted via volume).

## Auto-reconnect on refresh

After OTP verification, `persist_telegram_session` saves the StringSession synchronously. On reload, `_auto_reconnect_telegram()` in `interface.py` loads the file if still authorized.

**Verify after setup:**

```bash
docker exec groupint-streamlit ls -la /home/appuser/.groupint/sessions/
```

You should see non-empty `.string` and `.meta` files for your phone.

## Sidebar: Telegram sessions

The expander lists all saved sessions with:

- Health indicator (authorized vs not)
- **Connect** / **Disconnect** / **Delete**
- Optional **Telegram device list** (`GetAuthorizationsRequest`)

## Multi-user and multi-tab

| Scenario | Behavior |
|----------|----------|
| Different phone numbers | Separate `.string` files |
| Same phone, two browser tabs | `SessionInUseError` — only one active Telethon client per number |

Disconnect in one tab before connecting in another.

## Worker sessions

The **incident worker** container uses the same credentials (`TELEGRAM_*` in `.env`) or a shared session volume. Authorize Telegram once in the UI if the worker reports auth errors.

## Code references

- `core/telegram_session.py` — `list_sessions()`, `save_string_session()`, `delete_session_files()`
- `core/tg_api_connector.py` — client creation, `get_telegram_authorizations()`
- `streamlit_utils/telegram_auth.py` — Streamlit UI

## Next steps

- [Main application](../main-application.md)
- [Troubleshooting](../troubleshooting.md) — OTP and session issues
