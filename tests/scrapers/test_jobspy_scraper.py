from __future__ import annotations

import unittest

from jobhound.scrapers.jobspy_scraper import JobSpyScraper, clean_text


def make_row(**overrides: object) -> dict:
    data: dict = {
        "site": "linkedin",
        "job_url": "https://www.linkedin.com/jobs/view/123456",
        "title": "Logistics Analyst",
        "company": "ACME Corp",
        "location": "San José, CR",
        "description": "We are looking for a logistics analyst with supply chain experience.",
        "date_posted": "2024-01-15",
    }
    data.update(overrides)
    return data


class JobSpyScraperTest(unittest.TestCase):
    def test_to_job_extracts_core_fields(self) -> None:
        scraper = JobSpyScraper(["logistica"])
        job = scraper._to_job(make_row())

        self.assertIsNotNone(job)
        self.assertEqual(job.title, "Logistics Analyst")
        self.assertEqual(job.company, "ACME Corp")
        self.assertEqual(job.site, "linkedin")
        self.assertEqual(job.location, "San José, CR")

    def test_to_job_returns_none_when_title_missing(self) -> None:
        scraper = JobSpyScraper(["logistica"])
        self.assertIsNone(scraper._to_job(make_row(title=None)))

    def test_to_job_returns_none_when_url_missing(self) -> None:
        scraper = JobSpyScraper(["logistica"])
        self.assertIsNone(scraper._to_job(make_row(job_url=None)))

    def test_to_job_id_is_stable(self) -> None:
        scraper = JobSpyScraper(["logistica"])
        row = make_row()
        job1 = scraper._to_job(row)
        job2 = scraper._to_job(row)

        self.assertIsNotNone(job1)
        self.assertIsNotNone(job2)
        self.assertEqual(job1.id, job2.id)

    def test_to_job_id_differs_for_different_urls(self) -> None:
        scraper = JobSpyScraper(["logistica"])
        job1 = scraper._to_job(make_row(job_url="https://linkedin.com/jobs/1"))
        job2 = scraper._to_job(make_row(job_url="https://linkedin.com/jobs/2"))

        self.assertIsNotNone(job1)
        self.assertIsNotNone(job2)
        self.assertNotEqual(job1.id, job2.id)

    def test_clean_text_handles_none(self) -> None:
        self.assertEqual(clean_text(None), "")

    def test_clean_text_handles_nan_string(self) -> None:
        self.assertEqual(clean_text("nan"), "")
        self.assertEqual(clean_text("NaN"), "")

    def test_clean_text_strips_whitespace(self) -> None:
        self.assertEqual(clean_text("  hello  "), "hello")

    def test_clean_text_converts_non_string(self) -> None:
        self.assertEqual(clean_text(42), "42")


if __name__ == "__main__":
    unittest.main()
