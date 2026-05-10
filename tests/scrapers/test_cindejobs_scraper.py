from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from jobhound.scrapers.cindejobs_scraper import CindeJobsScraper

RAW_JOB = {
    "uuid": "uuid-001",
    "slug": "supply-chain-analyst",
    "name": "Supply Chain Analyst",
    "companyName": "Acme Corp",
    "companySlug": "acme-corp",
    "officeName": "Zona Franca La Lima, Cartago",
    "description": "<p>We need a <b>supply chain analyst</b> with ERP experience.</p>",
}


def make_profile(country: str = "costa rica", disable_scrapers: tuple[str, ...] = ()) -> MagicMock:
    profile = MagicMock()
    profile.search_terms = ["supply chain", "procurement"]
    profile.country = country
    profile.disable_scrapers = disable_scrapers
    return profile


class CindeJobsScraperTest(unittest.TestCase):
    def test_to_job_extracts_core_fields(self) -> None:
        scraper = CindeJobsScraper([])
        job = scraper._to_job(RAW_JOB)

        self.assertIsNotNone(job)
        self.assertEqual(job.title, "Supply Chain Analyst")
        self.assertEqual(job.company, "Acme Corp")
        self.assertEqual(job.site, "cindejobs")
        self.assertEqual(job.location, "Zona Franca La Lima, Cartago")
        self.assertEqual(job.url, "https://cindejobs.com/en/fair/acme-corp/supply-chain-analyst")

    def test_to_job_strips_html_from_description(self) -> None:
        scraper = CindeJobsScraper([])
        job = scraper._to_job(RAW_JOB)

        self.assertIsNotNone(job)
        self.assertNotIn("<p>", job.description)
        self.assertNotIn("<b>", job.description)
        self.assertIn("supply chain analyst", job.description)

    def test_to_job_returns_none_when_title_missing(self) -> None:
        scraper = CindeJobsScraper([])
        self.assertIsNone(scraper._to_job({**RAW_JOB, "name": ""}))

    def test_to_job_returns_none_when_uuid_missing(self) -> None:
        scraper = CindeJobsScraper([])
        self.assertIsNone(scraper._to_job({**RAW_JOB, "uuid": ""}))

    def test_to_job_id_is_stable(self) -> None:
        scraper = CindeJobsScraper([])
        job1 = scraper._to_job(RAW_JOB)
        job2 = scraper._to_job(RAW_JOB)

        self.assertIsNotNone(job1)
        self.assertIsNotNone(job2)
        self.assertEqual(job1.id, job2.id)

    def test_to_job_id_differs_for_different_uuids(self) -> None:
        scraper = CindeJobsScraper([])
        job1 = scraper._to_job({**RAW_JOB, "uuid": "uuid-001"})
        job2 = scraper._to_job({**RAW_JOB, "uuid": "uuid-002"})

        self.assertIsNotNone(job1)
        self.assertIsNotNone(job2)
        self.assertNotEqual(job1.id, job2.id)

    def test_to_job_fallback_url_when_slugs_missing(self) -> None:
        scraper = CindeJobsScraper([])
        raw = {**RAW_JOB, "companySlug": "", "slug": ""}
        job = scraper._to_job(raw)

        self.assertIsNotNone(job)
        self.assertIn("uuid-001", job.url)

    def test_from_profile_enabled_for_costa_rica(self) -> None:
        scraper = CindeJobsScraper.from_profile(make_profile("costa rica"))
        self.assertIsNotNone(scraper)

    def test_from_profile_returns_none_for_other_country(self) -> None:
        self.assertIsNone(CindeJobsScraper.from_profile(make_profile("mexico")))
        self.assertIsNone(CindeJobsScraper.from_profile(make_profile("usa")))
        self.assertIsNone(CindeJobsScraper.from_profile(make_profile("germany")))

    def test_search_fetches_page_two_when_page_one_is_full(self) -> None:
        """When page 1 returns a full page (20 items), page 2 must be attempted."""
        calls: list[int] = []
        full_page = [
            {**RAW_JOB, "uuid": f"uuid-{i:03d}", "slug": f"job-{i}"}
            for i in range(20)
        ]

        def fake_fetch(term: str, page: int) -> list:
            calls.append(page)
            return full_page if page == 1 else []

        scraper = CindeJobsScraper(["supply chain"])
        scraper._fetch_page = fake_fetch
        results = scraper._search("supply chain")

        self.assertEqual(len(results), 20)
        self.assertIn(2, calls, "Should attempt page 2 after a full first page")
        self.assertNotIn(3, calls, "Should stop after empty page 2")

    def test_search_does_not_fetch_page_two_when_page_one_is_partial(self) -> None:
        """When page 1 returns fewer than the page limit, no further pages are fetched."""
        calls: list[int] = []

        def fake_fetch(term: str, page: int) -> list:
            calls.append(page)
            return [RAW_JOB]  # 1 result < 20 limit → no more pages

        scraper = CindeJobsScraper(["supply chain"])
        scraper._fetch_page = fake_fetch
        results = scraper._search("supply chain")

        self.assertEqual(len(results), 1)
        self.assertNotIn(2, calls, "Should not fetch page 2 when page 1 is partial")

    def test_search_stops_on_empty_first_page(self) -> None:
        calls: list[int] = []

        def fake_fetch(term: str, page: int) -> list:
            calls.append(page)
            return []

        scraper = CindeJobsScraper(["supply chain"])
        scraper._fetch_page = fake_fetch
        results = scraper._search("supply chain")

        self.assertEqual(results, [])
        self.assertEqual(len(calls), 1, "Should not fetch more pages when first is empty")

    def test_scrape_deduplicates_across_terms(self) -> None:
        def fake_fetch(term: str, page: int) -> list:
            return [RAW_JOB] if page == 1 else []

        scraper = CindeJobsScraper(["supply chain", "logistics"])
        scraper._fetch_page = fake_fetch
        jobs = list(scraper.scrape())

        self.assertEqual(len(jobs), 1)


if __name__ == "__main__":
    unittest.main()
