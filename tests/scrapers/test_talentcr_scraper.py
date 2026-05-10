from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import requests

from jobhound.scrapers.talentcr_scraper import TalentCRScraper, _MAX_PAGES

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

API_RESPONSE = {
    "data": {
        "jobs": {
            "data": [RAW_JOB],
            "current_page": 1,
            "last_page": 1,
            "total": 1,
            "per_page": 10,
        }
    }
}


def make_profile(country: str = "costa rica", disable_scrapers: tuple[str, ...] = ()) -> MagicMock:
    profile = MagicMock()
    profile.search_terms = ["logistica", "compras"]
    profile.country = country
    profile.disable_scrapers = disable_scrapers
    return profile


def make_mock_session(json_data: object = None, raise_for_status_exc: Exception | None = None) -> MagicMock:
    session = MagicMock()
    response = MagicMock()
    if raise_for_status_exc:
        response.raise_for_status.side_effect = raise_for_status_exc
    else:
        response.raise_for_status.return_value = None
        response.json.return_value = json_data
    session.get.return_value = response
    return session


class TalentCRScraperTest(unittest.TestCase):
    # --- _to_job ---

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

    def test_to_job_handles_none_description(self) -> None:
        scraper = TalentCRScraper([])
        job = scraper._to_job({**RAW_JOB, "description": None})

        self.assertIsNotNone(job)
        self.assertEqual(job.description, "")

    def test_to_job_returns_none_when_title_missing(self) -> None:
        scraper = TalentCRScraper([])
        self.assertIsNone(scraper._to_job({**RAW_JOB, "name": ""}))

    def test_to_job_returns_none_when_id_key_absent(self) -> None:
        scraper = TalentCRScraper([])
        raw = {k: v for k, v in RAW_JOB.items() if k != "id"}
        self.assertIsNone(scraper._to_job(raw))

    def test_to_job_returns_none_when_id_is_none(self) -> None:
        scraper = TalentCRScraper([])
        self.assertIsNone(scraper._to_job({**RAW_JOB, "id": None}))

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

    # --- _fetch_page ---

    def test_fetch_page_returns_jobs_and_last_page_on_success(self) -> None:
        session = make_mock_session(json_data=API_RESPONSE)
        scraper = TalentCRScraper([], session=session)
        jobs, last_page = scraper._fetch_page("logistica", 1)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["name"], "Analista de Logística")
        self.assertEqual(last_page, 1)

    def test_fetch_page_returns_empty_on_http_error(self) -> None:
        session = make_mock_session(raise_for_status_exc=requests.HTTPError("500 Server Error"))
        scraper = TalentCRScraper([], session=session)
        jobs, last_page = scraper._fetch_page("logistica", 1)

        self.assertEqual(jobs, [])
        self.assertEqual(last_page, 1)

    def test_fetch_page_returns_empty_on_network_error(self) -> None:
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("connection refused")
        scraper = TalentCRScraper([], session=session)
        jobs, last_page = scraper._fetch_page("logistica", 1)

        self.assertEqual(jobs, [])
        self.assertEqual(last_page, 1)

    def test_fetch_page_returns_empty_when_data_is_null(self) -> None:
        """API returning {"data": null} must not crash — AttributeError is caught."""
        session = make_mock_session(json_data={"data": None})
        scraper = TalentCRScraper([], session=session)
        jobs, last_page = scraper._fetch_page("logistica", 1)

        self.assertEqual(jobs, [])
        self.assertEqual(last_page, 1)

    def test_fetch_page_returns_empty_when_jobs_list_is_null(self) -> None:
        session = make_mock_session(json_data={"data": {"jobs": {"data": None, "last_page": 3}}})
        scraper = TalentCRScraper([], session=session)
        jobs, last_page = scraper._fetch_page("logistica", 1)

        self.assertEqual(jobs, [])
        self.assertEqual(last_page, 3)

    # --- from_profile ---

    def test_from_profile_enabled_for_costa_rica(self) -> None:
        self.assertIsNotNone(TalentCRScraper.from_profile(make_profile("costa rica")))

    def test_from_profile_returns_none_for_other_country(self) -> None:
        self.assertIsNone(TalentCRScraper.from_profile(make_profile("mexico")))
        self.assertIsNone(TalentCRScraper.from_profile(make_profile("usa")))
        self.assertIsNone(TalentCRScraper.from_profile(make_profile("colombia")))

    # --- _search / pagination ---

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

    def test_search_respects_max_pages(self) -> None:
        calls: list[int] = []
        job_counter = [0]

        def fake_fetch(term: str, page: int) -> tuple[list, int]:
            calls.append(page)
            job_counter[0] += 1
            job = {**RAW_JOB, "id": job_counter[0]}
            return [job], 9999  # last_page never reached to force max_pages cap

        scraper = TalentCRScraper(["logistica"])
        scraper._fetch_page = fake_fetch
        scraper._search("logistica")

        self.assertLessEqual(max(calls), _MAX_PAGES, "Should not exceed _MAX_PAGES")

    def test_scrape_deduplicates_across_terms(self) -> None:
        def fake_fetch(term: str, page: int) -> tuple[list, int]:
            return ([RAW_JOB], 1) if page == 1 else ([], 1)

        scraper = TalentCRScraper(["logistica", "compras"])
        scraper._fetch_page = fake_fetch
        jobs = list(scraper.scrape())

        self.assertEqual(len(jobs), 1)


if __name__ == "__main__":
    unittest.main()
