from __future__ import annotations

import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from jobhound.models import Job, make_job_id
from jobhound.scrapers.computrabajo_scraper import ComputrabajoScraper

CARD_HTML = """
<html><body>
<article class="box_offer">
  <h2><a class="js-o-link fc_base" href="/oferta/12345-logistics-analyst#lc=ListOffers-0">Logistics Analyst</a></h2>
  <p class="dFlex vm_fx fs16 fc_base mt5">
    <a class="fc_base t_ellipsis" href="/empresa/acme">ACME Corp</a>
  </p>
  <p class="fs16 fc_base mt5"><span class="mr10">San José, San José</span></p>
</article>
</body></html>
"""

CARD_HTML_WITH_RATING = """
<html><body>
<article class="box_offer">
  <h2><a class="js-o-link fc_base" href="/oferta/99999-operations#lc=ListOffers-1">Operations Analyst</a></h2>
  <p class="dFlex vm_fx fs16 fc_base mt5">
    <span class="fx_none mr10"><span class="fwB">4,5</span></span>
    <a class="fc_base t_ellipsis" href="/empresa/manpower">Manpower Costa Rica</a>
  </p>
  <p class="fs16 fc_base mt5"><span class="mr10">Belén, Heredia</span></p>
</article>
</body></html>
"""

DESCRIPTION_HTML = """
<html><body>
<div class="box_detail">
  <p class="mbB">
    We are looking for a logistics analyst with experience in imports and exports.
    Knowledge of ERP systems and advanced Excel required. Excellent benefits offered.
  </p>
</div>
</body></html>
"""

EMPTY_HTML = "<html><body></body></html>"


class ComputrabajoScraperTest(unittest.TestCase):
    def test_cards_finds_box_offer_articles(self) -> None:
        soup = BeautifulSoup(CARD_HTML, "lxml")
        cards = ComputrabajoScraper([])._cards(soup)
        self.assertEqual(len(cards), 1)

    def test_job_from_card_extracts_title_and_company(self) -> None:
        soup = BeautifulSoup(CARD_HTML, "lxml")
        scraper = ComputrabajoScraper([])
        job = scraper._job_from_card(scraper._cards(soup)[0])

        self.assertIsNotNone(job)
        self.assertEqual(job.title, "Logistics Analyst")
        self.assertEqual(job.company, "ACME Corp")
        self.assertEqual(job.location, "San José, San José")
        self.assertEqual(job.site, "computrabajo")

    def test_job_from_card_strips_rating_from_company(self) -> None:
        soup = BeautifulSoup(CARD_HTML_WITH_RATING, "lxml")
        scraper = ComputrabajoScraper([])
        job = scraper._job_from_card(scraper._cards(soup)[0])

        self.assertIsNotNone(job)
        self.assertEqual(job.company, "Manpower Costa Rica")
        self.assertEqual(job.location, "Belén, Heredia")

    def test_job_from_card_strips_tracking_anchor_from_url(self) -> None:
        soup = BeautifulSoup(CARD_HTML, "lxml")
        scraper = ComputrabajoScraper([])
        job = scraper._job_from_card(scraper._cards(soup)[0])

        self.assertIsNotNone(job)
        self.assertTrue(job.url.startswith("https://www.computrabajo.co.cr"))
        self.assertIn("12345", job.url)
        self.assertNotIn("#", job.url)

    def test_job_from_card_returns_none_on_missing_title(self) -> None:
        html = '<html><body><article class="box_offer"><p>No title here</p></article></body></html>'
        soup = BeautifulSoup(html, "lxml")
        scraper = ComputrabajoScraper([])
        self.assertIsNone(scraper._job_from_card(scraper._cards(soup)[0]))

    def test_description_extracts_text(self) -> None:
        scraper = ComputrabajoScraper([], request_delay=0)
        with patch.object(scraper, "_fetch", return_value=BeautifulSoup(DESCRIPTION_HTML, "lxml")):
            description = scraper._description("https://www.computrabajo.co.cr/oferta/123")

        self.assertIn("logistics", description)
        self.assertGreater(len(description), 50)

    def test_search_fetches_page_two_when_page_one_has_results(self) -> None:
        calls: list[str] = []

        def fake_fetch(url: str) -> BeautifulSoup:
            calls.append(url)
            if "&p=2" in url or "&p=3" in url:
                return BeautifulSoup(EMPTY_HTML, "lxml")
            return BeautifulSoup(CARD_HTML, "lxml")

        scraper = ComputrabajoScraper(["logistica"], request_delay=0)
        with patch.object(scraper, "_fetch", side_effect=fake_fetch):
            results = scraper._search("logistica")

        self.assertEqual(len(results), 1)
        self.assertTrue(any("&p=2" in url for url in calls), "Should fetch page 2")

    def test_search_stops_on_empty_first_page(self) -> None:
        calls: list[str] = []

        def fake_fetch(url: str) -> BeautifulSoup:
            calls.append(url)
            return BeautifulSoup(EMPTY_HTML, "lxml")

        scraper = ComputrabajoScraper(["logistica"], request_delay=0)
        with patch.object(scraper, "_fetch", side_effect=fake_fetch):
            results = scraper._search("logistica")

        self.assertEqual(results, [])
        self.assertEqual(len(calls), 1, "Should not fetch more pages when first page is empty")

    def test_search_respects_max_pages(self) -> None:
        calls: list[str] = []

        def fake_fetch(url: str) -> BeautifulSoup:
            calls.append(url)
            return BeautifulSoup(CARD_HTML, "lxml")

        scraper = ComputrabajoScraper(["logistica"], request_delay=0)
        with patch.object(scraper, "_fetch", side_effect=fake_fetch):
            scraper._search("logistica")

        self.assertLessEqual(len(calls), 3, "Should not exceed MAX_PAGES")

    def test_scrape_deduplicates_across_terms(self) -> None:
        job = Job(
            id=make_job_id("computrabajo", "https://example.com/oferta/1", "Analyst", "ACME"),
            site="computrabajo",
            title="Analyst",
            company="ACME",
        )
        scraper = ComputrabajoScraper(["logistica", "procurement"], request_delay=0)

        with patch.object(scraper, "_search", return_value=[job]):
            with patch.object(scraper, "_with_description", side_effect=lambda j: j):
                jobs = list(scraper.scrape())

        self.assertEqual(len(jobs), 1)


if __name__ == "__main__":
    unittest.main()
