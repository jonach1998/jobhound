from jobhound.scrapers.base import BaseScraper
from jobhound.scrapers.cindejobs_scraper import CindeJobsScraper
from jobhound.scrapers.computrabajo_scraper import ComputrabajoScraper
from jobhound.scrapers.jobspy_scraper import JobSpyScraper
from jobhound.scrapers.talentcr_scraper import TalentCRScraper

# Add or remove scraper classes here to control which sites are searched.
# Each class must subclass BaseScraper and accept search_terms as its first argument.
SCRAPERS: list[type[BaseScraper]] = [
    JobSpyScraper,
    ComputrabajoScraper,
    CindeJobsScraper,
    TalentCRScraper,
]

__all__ = [
    "BaseScraper",
    "CindeJobsScraper",
    "ComputrabajoScraper",
    "JobSpyScraper",
    "TalentCRScraper",
    "SCRAPERS",
]
