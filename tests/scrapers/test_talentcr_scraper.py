from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from jobhound.scrapers.talentcr_scraper import TalentCRScraper

RAW_JOB = {
    "id": 42,
    "name": "Analista de Logística",
    "organization_name": "ACME S.A.",
    "provincia": "Alajuela",
    "canton": "Alajuela",
    "description": "<p>Se busca <b>analista de logística</b> con experiencia en ERP.</p>",
    "workplace": "on-site",
    "workday": "full time",
}


def make_profile(country: str = "costa rica", disable_scrapers: tuple[str, ...] = ()) -> MagicMock:
    profile = MagicMock()
    profile.search_terms = ["logistica", "compras"]
    profile.country = country
    profile.disable_scrapers = disable_scrapers
    return profile


class TalentCRScraperTest(unittest.TestCase):
    def test_to_job_extracts_core_fields(self) -> None:
        scraper = TalentCRScraper([])
        job = scraper._to_job(RAW_JOB)

        self.assertIsNotNone(job)
        self.assertEqual(job.title, "Analista de Logística")
        self.assertEqual(job.company, "ACME S.A.")
        self.assertEqual(job.site, "talentcr")
        self.assertEqual(job.location, "Alajuela, Alajuela")
        self.assertEqual(job.url, "https://talento.procomer.com/job/42")

    def test_to_job_strips_html_from_description(self) -> None:
        scraper = TalentCRScraper([])
        job = scraper._to_job(RAW_JOB)

        self.assertIsNotNone(job)
        self.assertNotIn("<p>", job.description)
        self.assertNotIn("<b>", job.description)
        self.assertIn("analista de logística", job.description)

    def test_to_job_returns_none_when_title_missing(self) -> None:
        scraper = TalentCRScraper([])
        self.assertIsNone(scraper._to_job({**RAW_JOB, "name": ""}))

    def test_to_job_returns_none_when_id_missing(self) -> None:
        scraper = TalentCRScraper([])
        raw = {k: v for k, v in RAW_JOB.items() if k != "id"}
        self.assertIsNone(scraper._to_job(raw))

    def test_to_job_id_is_stable(self) -> None:
        scraper = TalentCRScraper([])
        job1 = scraper._to_job(RAW_JOB)
        job2 = scraper._to_job(RAW_JOB)

        self.assertIsNotNone(job1)
        self.assertIsNotNone(job2)
        self.assertEqual(job1.id, job2.id)

    def test_to_job_id_differs_for_different_ids(self) -> None:
        scraper = TalentCRScraper([])
        job1 = scraper._to_job({**RAW_JOB, "id": 42})
        job2 = scraper._to_job({**RAW_JOB, "id": 99})

        self.assertIsNotNone(job1)
        self.assertIsNotNone(job2)
        self.assertNotEqual(job1.id, job2.id)

    def test_to_job_location_omits_empty_parts(self) -> None:
        scraper = TalentCRScraper([])
        job = scraper._to_job({**RAW_JOB, "canton": ""})

        self.assertIsNotNone(job)
        self.assertEqual(job.location, "Alajuela")

    def test_from_profile_enabled_for_costa_rica(self) -> None:
        scraper = TalentCRScraper.from_profile(make_profile("costa rica"))
        self.assertIsNotNone(scraper)

    def test_from_profile_returns_none_for_other_country(self) -> None:
        self.assertIsNone(TalentCRScraper.from_profile(make_profile("mexico")))
        self.assertIsNone(TalentCRScraper.from_profile(make_profile("usa")))
        self.assertIsNone(TalentCRScraper.from_profile(make_profile("colombia")))

    def test_search_paginates_through_all_pages(self) -> None:
        calls: list[int] = []
        job_page2 = {**RAW_JOB, "id": 99, "name": "Compras Analyst"}

        def fake_fetch(term: str, page: int) -> tuple[list, int]:
            calls.append(page)
            if page == 1:
                return [RAW_JOB], 2
            return [job_page2], 2

        scraper = TalentCRScraper(["logistica"])
        scraper._fetch_page = fake_fetch
        results = scraper._search("logistica")

        self.assertEqual(len(results), 2)
        self.assertIn(1, calls)
        self.assertIn(2, calls)
        self.assertNotIn(3, calls, "Should stop at last_page")

    def test_search_stops_on_empty_first_page(self) -> None:
        calls: list[int] = []

        def fake_fetch(term: str, page: int) -> tuple[list, int]:
            calls.append(page)
            return [], 1

        scraper = TalentCRScraper(["logistica"])
        scraper._fetch_page = fake_fetch
        results = scraper._search("logistica")

        self.assertEqual(results, [])
        self.assertEqual(len(calls), 1, "Should not fetch more pages when first is empty")

    def test_scrape_deduplicates_across_terms(self) -> None:
        def fake_fetch(term: str, page: int) -> tuple[list, int]:
            return ([RAW_JOB], 1) if page == 1 else ([], 1)

        scraper = TalentCRScraper(["logistica", "compras"])
        scraper._fetch_page = fake_fetch
        jobs = list(scraper.scrape())

        self.assertEqual(len(jobs), 1)


if __name__ == "__main__":
    unittest.main()
