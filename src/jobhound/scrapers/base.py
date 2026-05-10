from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence

from jobhound.config import ProfileConfig
from jobhound.models import Job


class BaseScraper(ABC):
    """Subclass this and implement scrape() and from_profile().
    Add the class to SCRAPERS in scrapers/__init__.py to register it."""

    def __init__(self, search_terms: Sequence[str]) -> None:
        self.search_terms = list(search_terms)

    @classmethod
    @abstractmethod
    def from_profile(cls, profile: ProfileConfig) -> BaseScraper | None:
        """Build an instance from a profile, or return None to skip for this profile."""

    @abstractmethod
    def scrape(self) -> Iterator[Job]:
        """Yield jobs matching the configured search terms."""
