# Telegram credentials and API keys

Groupint uses the **Telegram user API** via [Telethon](https://docs.telethon.dev/). You need a real Telegram account and application credentials from Telegram — not a BotFather bot token for group scraping.

## Obtain api_id and api_hash

1. Sign up for [Telegram](https://telegram.org/) on your phone number.
2. Log in at [https://my.telegram.org](https://my.telegram.org/) with the **same number**.
3. Open [API development tools](https://my.telegram.org/apps).
4. Create an application (title, short name, platform — e.g. Desktop).
5. Copy **App api_id** (numeric) and **App api_hash** (32-character hex string).

**Policy:** Telegram typically allows **one** api_id/api_hash pair per phone number.

Store these in a password manager. Do not commit them to git.

## Configure Groupint

**Option A — `.streamlit/secrets.toml`:**

```toml
[telegram]
phone = "+1234567890"
api_id = "12345678"
api_hash = "your_api_hash_here"
```

**Option B — `.env`:**

```bash
TELEGRAM_PHONE=+1234567890
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
```

Phone numbers must use international format with a leading `+`.

## Virtual numbers (OSINT setups)

Some investigators use SMS rental services (e.g. Grizzly SMS) to receive the Telegram registration code. That workflow is documented step-by-step in the [Ukrainian full tutorial](../tutorial-full-workflow-uk.md).

Risks:

- Virtual numbers are often one-time; you may need a new number if the session expires.
- Follow Telegram ToS and provider rules; do not use for spam or ban evasion.

## Common mistakes

| Problem | Fix |
|---------|-----|
| Swapped api_id and api_hash | api_id is digits only; api_hash is a string |
| Wrong phone format | Use `+country_code...` |
| `ERROR` on my.telegram.org | Wait and retry; ensure the account is not restricted |
| Secrets in git | Add `.env` and `secrets.toml` to `.gitignore`; never push keys |

## Next steps

- [Sessions and authentication](sessions-and-auth.md) — OTP and saved sessions
