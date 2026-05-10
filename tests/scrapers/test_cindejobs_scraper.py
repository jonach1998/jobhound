from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from jobhound.scrapers.cindejobs_scraper import CindeJobsScraper, _FAIR_ID, _MAX_PAGES

RAW_JOB = {
    "uuid": "uuid-001",
    "slug": "supply-chain-analyst",
    "name": "Supply Chain Analyst",
    "companyName": "Acme Corp",
    "companySlug": "acme-corp",
    "officeName": "Zona Franca La Lima, Cartago",
    "description": "<p>We need a <b>supply chain analyst</b> with ERP experience.</p>",
}

GRAPHQL_RESPONSE = {
    "data": {
        "viewJobOffers": [RAW_JOB]
    }
}


def make_profile(country: str = "costa rica", disable_scrapers: tuple[str, ...] = ()) -> MagicMock:
    profile = MagicMock()
    profile.search_terms = ["supply chain", "procurement"]
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
    session.post.return_value = response
    return session


class CindeJobsScraperTest(unittest.TestCase):
    # --- _to_job ---

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

    def test_to_job_handles_none_description(self) -> None:
        scraper = CindeJobsScraper([])
        job = scraper._to_job({**RAW_JOB, "description": None})

        self.assertIsNotNone(job)
        self.assertEqual(job.description, "")

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

    def test_to_job_id_differs_for_different_urls(self) -> None:
        """ID is derived from the URL (not UUID), so different slugs produce different IDs."""
        scraper = CindeJobsScraper([])
        job1 = scraper._to_job({**RAW_JOB, "slug": "job-alpha"})
        job2 = scraper._to_job({**RAW_JOB, "slug": "job-beta"})

        self.assertIsNotNone(job1)
        self.assertIsNotNone(job2)
        self.assertNotEqual(job1.id, job2.id)

    def test_to_job_fallback_url_contains_uuid_when_slugs_missing(self) -> None:
        scraper = CindeJobsScraper([])
        raw = {**RAW_JOB, "companySlug": "", "slug": ""}
        job = scraper._to_job(raw)

        self.assertIsNotNone(job)
        self.assertIn("uuid-001", job.url)

    # --- _fetch_page ---

    def test_fetch_page_returns_jobs_on_success(self) -> None:
        session = make_mock_session(json_data=GRAPHQL_RESPONSE)
        scraper = CindeJobsScraper([], session=session)
        result = scraper._fetch_page("logistics", 1)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Supply Chain Analyst")

    def test_fetch_page_sends_fair_id_variable(self) -> None:
        session = make_mock_session(json_data=GRAPHQL_RESPONSE)
        scraper = CindeJobsScraper([], session=session)
        scraper._fetch_page("logistics", 1)

        _, kwargs = session.post.call_args
        variables = kwargs["json"]["variables"]
        self.assertEqual(variables["fairId"], _FAIR_ID)

    def test_fetch_page_returns_empty_on_http_error(self) -> None:
        session = make_mock_session(raise_for_status_exc=requests.HTTPError("500 Server Error"))
        scraper = CindeJobsScraper([], session=session)
        result = scraper._fetch_page("logistics", 1)

        self.assertEqual(result, [])

    def test_fetch_page_returns_empty_on_network_error(self) -> None:
        session = MagicMock()
        session.post.side_effect = requests.ConnectionError("connection refused")
        scraper = CindeJobsScraper([], session=session)
        result = scraper._fetch_page("logistics", 1)

        self.assertEqual(result, [])

    def test_fetch_page_returns_empty_when_data_is_null(self) -> None:
        """API returning {"data": null} must not crash — AttributeError is caught."""
        session = make_mock_session(json_data={"data": None})
        scraper = CindeJobsScraper([], session=session)
        result = scraper._fetch_page("logistics", 1)

        self.assertEqual(result, [])

    def test_fetch_page_returns_empty_when_view_job_offers_is_null(self) -> None:
        session = make_mock_session(json_data={"data": {"viewJobOffers": None}})
        scraper = CindeJobsScraper([], session=session)
        result = scraper._fetch_page("logistics", 1)

        self.assertEqual(result, [])

    # --- from_profile ---

    def test_from_profile_enabled_for_costa_rica(self) -> None:
        self.assertIsNotNone(CindeJobsScraper.from_profile(make_profile("costa rica")))

    def test_from_profile_returns_none_for_other_country(self) -> None:
        self.assertIsNone(CindeJobsScraper.from_profile(make_profile("mexico")))
        self.assertIsNone(CindeJobsScraper.from_profile(make_profile("usa")))
        self.assertIsNone(CindeJobsScraper.from_profile(make_profile("germany")))

    # --- _search / pagination ---

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
        """When page 1 returns fewer than the limit, no further pages are fetched."""
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

    def test_search_respects_max_pages(self) -> None:
        calls: list[int] = []
        full_page = [
            {**RAW_JOB, "uuid": f"uuid-{i:04d}", "slug": f"job-{i}"}
            for i in range(20)
        ]

        def fake_fetch(term: str, page: int) -> list:
            calls.append(page)
            return full_page  # always returns a full page to force pagination

        scraper = CindeJobsScraper(["supply chain"])
        scraper._fetch_page = fake_fetch
        scraper._search("supply chain")

        self.assertLessEqual(max(calls), _MAX_PAGES, "Should not exceed _MAX_PAGES")

    def test_scrape_deduplicates_across_terms(self) -> None:
        def fake_fetch(term: str, page: int) -> list:
            return [RAW_JOB] if page == 1 else []

        scraper = CindeJobsScraper(["supply chain", "logistics"])
        scraper._fetch_page = fake_fetch
        jobs = list(scraper.scrape())

        self.assertEqual(len(jobs), 1)


if __name__ == "__main__":
    unittest.main()
