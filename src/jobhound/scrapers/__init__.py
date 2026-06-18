from jobhound.scrapers.base import BaseScraper
from jobhound.scrapers.cindejobs_scraper import CindeJobsScraper
from jobhound.scrapers.computrabajo_scraper import ComputrabajoScraper
from jobhound.scrapers.jobspy_scraper import JobSpyScraper
from jobhound.scrapers.talentcr_scraper import TalentCRScraper

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
