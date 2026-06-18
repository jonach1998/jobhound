from __future__ import annotations

import logging
import time
from collections.abc import Iterator, Sequence
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from jobhound.config import ProfileConfig
from jobhound.utils.logging_utils import log_event
from jobhound.models import Job, make_job_id
from jobhound.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
REQUEST_DELAY = 1.5
DESCRIPTION_LIMIT = 3000
DESCRIPTION_MIN_LENGTH = 50
MAX_PAGES = 3

COMPUTRABAJO_TLDS = {
    "argentina": "com.ar",
    "bolivia": "com.bo",
    "chile": "cl",
    "colombia": "com.co",
    "costa rica": "co.cr",
    "dominican republic": "com.do",
    "ecuador": "com.ec",
    "el salvador": "com.sv",
    "guatemala": "com.gt",
    "honduras": "com.hn",
    "mexico": "com.mx",
    "nicaragua": "com.ni",
    "panama": "com.pa",
    "paraguay": "com.py",
    "peru": "com.pe",
    "puerto rico": "com.pr",
    "uruguay": "com.uy",
    "venezuela": "com.ve",
}

LISTING_SELECTORS = "article.box_offer, div.offer_item, article[data-id]"
TITLE_SELECTOR = "h2 a, h3 a, a.js-o-link, a[class*='title']"
COMPANY_SELECTOR = "a.fc_base.t_ellipsis"
LOCATION_SELECTOR = "p.fs16.fc_base.mt5:not(.dFlex)"
DESCRIPTION_SELECTORS = (
    "div.box_detail p.mbB",
    "div.box_detail",
    "div.job_description",
    "section.description",
    "div#job_description",
    "div.offer_description",
    "div[class*='description']",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CR,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class ComputrabajoScraper(BaseScraper):
    def __init__(
        self,
        search_terms: Sequence[str],
        tld: str = "co.cr",
        session: requests.Session | None = None,
        request_delay: float = REQUEST_DELAY,
    ) -> None:
        super().__init__(search_terms)
        self.base_url = f"https://www.computrabajo.{tld}"
        self.session = session or requests.Session()
        self.request_delay = request_delay

    @classmethod
    def from_profile(cls, profile: ProfileConfig) -> ComputrabajoScraper | None:
        tld = COMPUTRABAJO_TLDS.get(profile.country)
        if not tld:
            return None
        return cls(profile.search_terms, tld)

    def scrape(self) -> Iterator[Job]:
        seen: set[str] = set()
        for term in self.search_terms:
            log.info(f"[computrabajo] searching: {term} on {self.base_url}")
            for job in self._search(term):
                if job.id in seen:
                    continue
                seen.add(job.id)
                yield self._with_description(job)

    def _search(self, term: str) -> list[Job]:
        jobs: list[Job] = []
        seen_ids: set[str] = set()

        for page in range(1, MAX_PAGES + 1):
            url = f"{self.base_url}/ofertas-de-trabajo/?q={quote(term)}"
            if page > 1:
                url += f"&p={page}"

            soup = self._fetch(url)
            if not soup:
                break

            page_jobs = [
                job
                for card in self._cards(soup)
                if (job := self._job_from_card(card)) and job.id not in seen_ids
            ]

            if not page_jobs:
                break

            for job in page_jobs:
                seen_ids.add(job.id)
            jobs.extend(page_jobs)

        return jobs

    def _with_description(self, job: Job) -> Job:
        job.description = self._description(job.url)
        time.sleep(self.request_delay)
        return job

    def _fetch(self, url: str) -> BeautifulSoup | None:
        try:
            response = self.session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return BeautifulSoup(response.text, "lxml")
        except requests.RequestException as exc:
            log.warning(log_event("computrabajo", "fetch.failed", url=url, error=exc))
            return None

    def _description(self, url: str) -> str:
        soup = self._fetch(url)
        if not soup:
            return ""

        for selector in DESCRIPTION_SELECTORS:
            element = soup.select_one(selector)
            text = element.get_text(separator="\n", strip=True) if element else ""
            if len(text) > DESCRIPTION_MIN_LENGTH:
                return text[:DESCRIPTION_LIMIT]

        return ""

    def _job_from_card(self, card: Tag) -> Job | None:
        title_element = card.select_one(TITLE_SELECTOR)
        href = title_element.get("href") if title_element else None
        title = title_element.get_text(strip=True) if title_element else ""

        if not title or not isinstance(href, str):
            return None

        company = card.select_one(COMPANY_SELECTOR)
        location = card.select_one(LOCATION_SELECTOR)
        company_name = company.get_text(strip=True) if company else ""
        url = urljoin(self.base_url, href.split("#")[0])
        return Job(
            id=make_job_id("computrabajo", url, title, company_name),
            site="computrabajo",
            title=title,
            company=company_name,
            location=location.get_text(strip=True) if location else "",
            url=url,
        )

    @staticmethod
    def _cards(soup: BeautifulSoup) -> list[Tag]:
        return soup.select(LISTING_SELECTORS) or soup.select("article")
