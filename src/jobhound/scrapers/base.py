from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence

from jobhound.models import Job


class BaseScraper(ABC):
    """Subclass this and implement scrape(); add the class to SCRAPERS in scrapers/__init__.py."""

    def __init__(self, search_terms: Sequence[str]) -> None:
        self.search_terms = list(search_terms)

    @abstractmethod
    def scrape(self) -> Iterator[Job]:
        """Yield jobs matching the configured search terms."""
