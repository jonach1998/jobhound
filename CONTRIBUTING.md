# Contributing to JobHound

## Prerequisites

- Python 3.12
- Docker and Docker Compose (only needed to run the full app — not required for tests)

## Setup

```bash
git clone https://github.com/jonach1998/jobhound.git
cd jobhound

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt pytest
```

## Running tests

Tests do not require Docker or a real API key — all external calls are mocked.

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

To run a single test file:

```bash
PYTHONPATH=src python -m pytest tests/services/test_job_scorer.py -v
```

## Running the app

### With Docker (recommended)

See the [README](README.md#running-with-docker-recommended) for the full step-by-step. The short version:

```bash
cp .env.example .env  # fill in your values
docker compose up -d --build
docker compose logs -f jobhound
```

### Without Docker

Useful for iterating quickly without rebuilding the container.

```bash
cp .env.example .env
# Fill in .env with real values

PYTHONPATH=src python src/main.py
```

Profiles are loaded from `profiles/` and the database is created at `data/jobs.sqlite`, both relative to the project root.

## Project structure

```
src/jobhound/
  app.py               # main orchestration loop
  config/
    env.py             # environment variable helpers
    app_config.py      # top-level app configuration
    profile_config.py  # per-profile config loading and discovery
  models/
    job.py             # Job dataclass
    job_id.py          # stable content-based job ID (SHA-256)
  repositories/
    job_repository.py  # SQLite persistence (deduplication, notifications)
  scrapers/
    base.py            # BaseScraper ABC
    jobspy_scraper.py  # LinkedIn + Indeed via python-jobspy
    computrabajo_scraper.py  # Computrabajo (Costa Rica) via HTML scraping
    __init__.py        # SCRAPERS registry — add new scrapers here
  services/
    job_scorer.py      # AI scoring via OpenAI-compatible API
    scoring_prompt.py  # prompt construction and JSON parsing
    telegram_notifier.py  # Telegram message formatting and delivery
  utils/
    logging_utils.py   # structured log formatting helpers
tests/                 # mirrors src/jobhound/ structure
```

## Adding a scraper

1. Create `src/jobhound/scrapers/my_site_scraper.py`.
2. Subclass `BaseScraper` and implement `scrape()` and `from_profile()`.
3. Add the class to `SCRAPERS` in `src/jobhound/scrapers/__init__.py`.

```python
from __future__ import annotations
from collections.abc import Iterator, Sequence

from jobhound.config import ProfileConfig
from jobhound.models import Job, make_job_id
from jobhound.scrapers.base import BaseScraper


class MySiteScraper(BaseScraper):
    def __init__(self, search_terms: Sequence[str], country: str = "") -> None:
        super().__init__(search_terms)
        self.country = country

    @classmethod
    def from_profile(cls, profile: ProfileConfig) -> MySiteScraper | None:
        # Return None to skip this scraper for the given profile
        # (e.g. when the country is not supported by the site).
        return cls(profile.search_terms, profile.country)

    def scrape(self) -> Iterator[Job]:
        for term in self.search_terms:
            for raw in self._fetch(term):
                yield Job(
                    id=make_job_id("mysite", raw["url"], raw["title"], raw["company"]),
                    site="mysite",
                    title=raw["title"],
                    company=raw["company"],
                    location=raw["location"],
                    url=raw["url"],
                    description=raw["description"],
                )
```

- `make_job_id` produces a stable 16-character hex ID from site + URL + title + company — use it so the same job is not scored twice across runs.
- `from_profile` builds the scraper instance for a given profile. Return `None` to skip the scraper (for example, if the profile doesn't configure a country your site supports).

## Adding a profile

Copy `profiles/example/`, rename the folder, and edit the three files:

- **`profile.yaml`** — set `display_name`, `score_threshold` (0–100), `country`, optionally `location`, and `search_terms`.
- **`cv.txt`** — the candidate's CV in plain text. Sent verbatim to the AI for every job scored.
- **`scoring_prompt.txt`** — scoring instructions for the AI. See `profiles/example/scoring_prompt.txt` for a complete example.

Remove `example: true` from `profile.yaml` when ready. The app auto-discovers all active profiles at startup.

## Code style

JobHound uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting (line length 100, Python 3.12).

```bash
pip install ruff
ruff check src/ tests/
ruff format src/ tests/
```

## Pull requests

- Run the full test suite before opening a PR.
- Keep changes focused — one feature or fix per PR.
- Add or update tests for any new behavior.
- New scrapers should include at least one unit test with a mocked HTTP response.
