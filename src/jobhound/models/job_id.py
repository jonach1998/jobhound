from __future__ import annotations

import hashlib


def make_job_id(site: str, url: str, title: str, company: str) -> str:
    raw = f"{site}|{url}|{title}|{company}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
