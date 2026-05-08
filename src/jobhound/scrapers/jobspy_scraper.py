from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from typing import Any

from jobhound.utils.logging_utils import log_event
from jobhound.models import Job, make_job_id
from jobhound.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

JOB_SITES = ("linkedin", "indeed")
LOCATION = "Costa Rica"
INDEED_COUNTRY = "costa rica"
RESULTS_WANTED = 25
HOURS_OLD = 72


class JobSpyScraper(BaseScraper):
    def __init__(
        self,
        search_terms: Sequence[str],
        job_sites: Sequence[str] = JOB_SITES,
    ) -> None:
        super().__init__(search_terms)
        self.job_sites = job_sites

    def scrape(self) -> Iterator[Job]:
        from jobspy import scrape_jobs

        seen: set[str] = set()
        for term in self.search_terms:
            log.info(f"[jobspy] searching: {term}")
            try:
                jobs = scrape_jobs(
                    site_name=list(self.job_sites),
                    search_term=term,
                    location=LOCATION,
                    country_indeed=INDEED_COUNTRY,
                    results_wanted=RESULTS_WANTED,
                    hours_old=HOURS_OLD,
                    description_format="markdown",
                    linkedin_fetch_description=True,
                )
            except Exception as exc:
                log.warning(log_event("jobspy", "term.failed", term=term, error=exc))
                continue

            if jobs is None or jobs.empty:
                continue

            for _, row in jobs.iterrows():
                job = self._to_job(row)
                if job and job.id not in seen:
                    seen.add(job.id)
                    yield job

    def _to_job(self, row: Any) -> Job | None:
        site = clean_text(row.get("site"))
        url = clean_text(row.get("job_url"))
        title = clean_text(row.get("title"))
        company = clean_text(row.get("company"))

        if not title or not url:
            return None

        return Job(
            id=make_job_id(site, url, title, company),
            site=site,
            title=title,
            company=company,
            location=clean_text(row.get("location")),
            url=url,
            description=clean_text(row.get("description")),
            posted_date=clean_text(row.get("date_posted")),
        )


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    return "" if text.lower() == "nan" else text
