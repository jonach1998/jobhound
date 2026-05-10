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

GRAPHQL_URL = "https://api.cindejobs.com/graphql"
# fairId 100 is the permanent job fair — required; without it the API returns 0 results.
_FAIR_ID = 100
_RESULTS_PER_PAGE = 20
_REQUEST_TIMEOUT = 15
_DESCRIPTION_LIMIT = 3000

# CINDE is Costa Rica's investment promotion agency — all listings are in Costa Rica.
_SUPPORTED_COUNTRIES = frozenset({"costa rica"})

_QUERY = """
query($search: String, $page: Int, $limit: Int) {
    viewJobOffers(search: $search, page: $page, limit: $limit, fairId: 100) {
        uuid slug name companyName companySlug officeName description
    }
}
"""

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
}


class CindeJobsScraper(BaseScraper):
    """Scraper for cindejobs.com — CINDE's job board for Costa Rica multinationals.

    Uses the public GraphQL API (no auth required). All jobs are in Costa Rica,
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
    def from_profile(cls, profile: ProfileConfig) -> CindeJobsScraper | None:
        if profile.country not in _SUPPORTED_COUNTRIES:
            return None
        return cls(profile.search_terms)

    def scrape(self) -> Iterator[Job]:
        seen: set[str] = set()
        for term in self.search_terms:
            log.info(f"[cindejobs] searching: {term}")
            for job in self._search(term):
                if job.id not in seen:
                    seen.add(job.id)
                    yield job

    def _search(self, term: str) -> list[Job]:
        jobs: list[Job] = []
        seen_uuids: set[str] = set()
        page = 1

        while True:
            raw_jobs = self._fetch_page(term, page)
            if not raw_jobs:
                break

            for raw in raw_jobs:
                uuid = (raw.get("uuid") or "").strip()
                if uuid and uuid not in seen_uuids:
                    seen_uuids.add(uuid)
                    job = self._to_job(raw)
                    if job:
                        jobs.append(job)

            if len(raw_jobs) < _RESULTS_PER_PAGE:
                break
            page += 1

        return jobs

    def _fetch_page(self, term: str, page: int) -> list[dict]:
        payload = {
            "query": _QUERY,
            "variables": {"search": term, "page": page, "limit": _RESULTS_PER_PAGE},
        }
        try:
            response = self.session.post(
                GRAPHQL_URL, json=payload, headers=_HEADERS, timeout=_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json().get("data", {}).get("viewJobOffers") or []
        except (requests.RequestException, ValueError, KeyError) as exc:
            log.warning(log_event("cindejobs", "fetch.failed", page=page, term=term, error=exc))
            return []

    def _to_job(self, raw: dict) -> Job | None:
        title = (raw.get("name") or "").strip()
        uuid = (raw.get("uuid") or "").strip()
        if not title or not uuid:
            return None

        company = (raw.get("companyName") or "").strip()
        company_slug = (raw.get("companySlug") or "").strip()
        slug = (raw.get("slug") or "").strip()
        url = (
            f"https://cindejobs.com/en/fair/{company_slug}/{slug}"
            if company_slug and slug
            else f"https://cindejobs.com/en/job/{uuid}"
        )

        description_html = raw.get("description") or ""
        description = BeautifulSoup(description_html, "lxml").get_text(separator="\n", strip=True)

        return Job(
            id=make_job_id("cindejobs", uuid, title, company),
            site="cindejobs",
            title=title,
            company=company,
            location=(raw.get("officeName") or "").strip(),
            url=url,
            description=description[:_DESCRIPTION_LIMIT],
        )
