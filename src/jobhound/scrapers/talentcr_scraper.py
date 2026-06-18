from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence

import requests
from bs4 import BeautifulSoup

from jobhound.config import ProfileConfig
from jobhound.models import Job, make_job_id
from jobhound.scrapers.base import BaseScraper
from jobhound.utils.logging_utils import log_event

log = logging.getLogger(__name__)

_API_URL = "https://talento.procomer.com/api/candidate/jobs"
_MAX_PAGES = 30
_REQUEST_TIMEOUT = 20
_DESCRIPTION_LIMIT = 3000

_SUPPORTED_COUNTRIES = frozenset({"costa rica"})

_HEADERS = {
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
}


class TalentCRScraper(BaseScraper):
    """Scraper for talento.procomer.com — PROCOMER's job board for Costa Rica free-trade-zone companies.

    Uses the public REST API (no auth required). All jobs are in Costa Rica,
    so this scraper is only active for profiles with country = 'costa rica'.
    """

    def __init__(
        self,
        search_terms: Sequence[str],
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(search_terms)
        self.session = session or requests.Session()

    @classmethod
    def from_profile(cls, profile: ProfileConfig) -> TalentCRScraper | None:
        if profile.country not in _SUPPORTED_COUNTRIES:
            return None
        return cls(profile.search_terms)

    def scrape(self) -> Iterator[Job]:
        seen: set[str] = set()
        for term in self.search_terms:
            log.info(f"[talentcr] searching: {term}")
            for job in self._search(term):
                if job.id not in seen:
                    seen.add(job.id)
                    yield job

    def _search(self, term: str) -> list[Job]:
        jobs: list[Job] = []
        seen_ids: set[int] = set()
        page = 1

        while page <= _MAX_PAGES:
            raw_jobs, last_page = self._fetch_page(term, page)
            if not raw_jobs:
                break

            for raw in raw_jobs:
                job_id = raw.get("id")
                if job_id is not None and job_id not in seen_ids:
                    seen_ids.add(job_id)
                    job = self._to_job(raw)
                    if job:
                        jobs.append(job)

            if page >= last_page:
                break
            page += 1

        return jobs

    def _fetch_page(self, term: str, page: int) -> tuple[list[dict], int]:
        try:
            response = self.session.get(
                _API_URL,
                params={"search": term, "page": page},
                headers=_HEADERS,
                timeout=_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            jobs_data = response.json().get("data", {}).get("jobs", {})
            return jobs_data.get("data") or [], jobs_data.get("last_page", 1)
        except (requests.RequestException, ValueError, AttributeError) as exc:
            log.warning(log_event("talentcr", "fetch.failed", page=page, term=term, error=exc))
            return [], 1

    def _to_job(self, raw: dict) -> Job | None:
        job_id = raw.get("id")
        title = (raw.get("name") or "").strip()
        if not title or job_id is None:
            return None

        company = (raw.get("organization_name") or "").strip()
        provincia = (raw.get("provincia") or "").strip()
        canton = (raw.get("canton") or "").strip()
        location = ", ".join(part for part in (provincia, canton) if part)
        url = f"https://talento.procomer.com/job/{job_id}"

        description_html = raw.get("description") or ""
        description = BeautifulSoup(description_html, "lxml").get_text(separator="\n", strip=True)

        return Job(
            id=make_job_id("talentcr", url, title, company),
            site="talentcr",
            title=title,
            company=company,
            location=location,
            url=url,
            description=description[:_DESCRIPTION_LIMIT],
        )
