from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Job:
    id: str
    site: str
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    description: str = ""
    posted_date: str = ""
    score: int = 0
    score_reason: str = ""
    notified: bool = False
