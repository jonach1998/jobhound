from jobhound.scrapers.base import BaseScraper
from jobhound.scrapers.computrabajo_scraper import ComputrabajoScraper
from jobhound.scrapers.jobspy_scraper import JobSpyScraper

# Add or remove scraper classes here to control which sites are searched.
# Each class must subclass BaseScraper and accept search_terms as its first argument.
SCRAPERS: list[type[BaseScraper]] = [
    JobSpyScraper,
    ComputrabajoScraper,
]

__all__ = ["BaseScraper", "ComputrabajoScraper", "JobSpyScraper", "SCRAPERS"]
