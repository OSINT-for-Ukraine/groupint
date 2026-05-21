<p align="center">


  <h3 align="center">📡 Groupint</h3>

  <p align="center">
    An OSINT tool to identify actors and networks on Telegram
   
  </p>
</p>

# Groupint

Groupint is an application developed by [OSINT for Ukraine](https://www.osintforukraine.com/) that enables investigators to scrape data from Telegram groups and connect "who's talking to whom" through an intuitive and visually appealing graph user interface.

This tool empowers investigators to analyse networks within specific Telegram communities. A separate **Incidents** module monitors watchlisted channels, runs an LLM pipeline, and maps geocoded reports (with optional export to [Atlos](https://atlos.org)).

## Documentation

**Full user guide:** [docs/index.md](docs/index.md)

| Topic | Guide |
|-------|--------|
| Install and configure | [docs/installation.md](docs/installation.md) |
| Docker (Groupint only) | [docs/docker/desktop-stack.md](docs/docker/desktop-stack.md) |
| Docker (+ local Atlos) | [docs/docker/full-stack-with-atlos.md](docs/docker/full-stack-with-atlos.md) |
| Telegram login | [docs/telegram/sessions-and-auth.md](docs/telegram/sessions-and-auth.md) |
| Scrape groups & graphs | [docs/main-application.md](docs/main-application.md) |
| Incidents pipeline | [docs/incidents/overview.md](docs/incidents/overview.md) |
| Gephi import | [docs/neo4j-and-gephi.md](docs/neo4j-and-gephi.md) |
| Tutorial (UK) | [docs/tutorial-full-workflow-uk.md](docs/tutorial-full-workflow-uk.md) |

## About OSINT for Ukraine

[OSINT for Ukraine](https://www.osintforukraine.com/) is an independent non-profit foundation dedicated to using open-source intelligence to investigate international war crimes in relation to the Russo-Ukrainian war, Research Influence and Disinformation operations in Europe, and to provide OSINT and OPSEC advisory and training.
  
Headquartered in The Hague, we are a multinational team of professionals with experience in OSINT investigations, human rights law, and investigative journalism. Our Research and Development team is dedicated to developing full spectrum OSINT solutions in the pursuit of justice, truth, memory.

## Quick start

### Acquire API credentials

Groupint uses your own Telegram account (via [Telethon](https://docs.telethon.dev/)) to scrape group members and stores results in Neo4j for graph analysis.

Acquire your `API id` and `API hash` from [Telegram](https://core.telegram.org/api/obtaining_api_id):

1. Sign up for Telegram
2. Log in at [https://my.telegram.org](https://my.telegram.org/)
3. Go to ["API development tools"](https://my.telegram.org/apps) and fill out the form
4. You will get your `API id` and `API hash` parameters required for user authorization
5. Each phone number can typically have one api id connected to it

See [docs/telegram/credentials-and-api.md](docs/telegram/credentials-and-api.md) for details.

### Prerequisites

1. Docker (recommended) — see [docs/installation.md](docs/installation.md)
2. Python 3.11 (local dev)
3. Poetry — dependencies and virtual environment
4. [Pre-commit](https://pre-commit.com/) — linters and codestyle

```bash
pip install pre-commit
pre-commit install
```

### Clone and run (Docker)

```bash
git clone https://github.com/OSINT-for-Ukraine/groupint.git
cd groupint
cp .env.example .env
# Edit .env: TELEGRAM_*, LLM keys as needed
./scripts/up-desktop.sh
```

| Service | URL |
|---------|-----|
| Groupint | http://localhost:18501 |
| Neo4j Browser | http://localhost:17474 |

Optional **Groupint + local Atlos**: `./scripts/up-full.sh` — see [docs/docker/full-stack-with-atlos.md](docs/docker/full-stack-with-atlos.md).

### Telegram defaults (optional)

Create `.streamlit/secrets.toml` (do not commit):

```toml
[telegram]
phone = "+1234567890"
api_id = "12345678"
api_hash = "your_api_hash"
```

### Run locally (without Docker)

```bash
poetry install
streamlit run interface.py
```

### Contributing

1. Create a branch for your change
2. Commit with a clear message (pre-commit runs on commit)
3. Push and open a PR to `main`

See [docs/development.md](docs/development.md).

## Licensing

Groupint is distributed under the [GNU Affero General Public License (AGPL-3.0)](https://www.gnu.org/licenses/agpl-3.0.en.html). You are free to use, distribute, and change the software. Any modified version must also be distributed under the AGPL.

## Support and Contact

Report technical issues via the [GitHub issue tracker](https://github.com/OSINT-for-Ukraine/groupint/issues).

## Community Engagement

- [LinkedIn](https://www.linkedin.com/company/osint-for-ukraine/mycompany/)
- [Instagram](https://www.instagram.com/osintforukraine/) — @osintforukraine
- [Linktree](https://linktr.ee/osintforukraine)
- [YouTube](https://www.youtube.com/@OSINTFORUKRAINE)

Thank you for using Groupint and contributing to OSINT for Ukraine's mission to enhance information analysis and transparency.
