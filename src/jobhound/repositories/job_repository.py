from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from jobhound.models import Job

DB_PATH = Path("/app/data/jobs.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    profile_id TEXT NOT NULL,
    id TEXT NOT NULL,
    site TEXT,
    title TEXT,
    company TEXT,
    location TEXT,
    url TEXT,
    description TEXT,
    posted_date TEXT,
    score INTEGER,
    score_reason TEXT,
    notified INTEGER DEFAULT 0,
    seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id, id)
);
CREATE INDEX IF NOT EXISTS idx_profile_score ON jobs(profile_id, score);
CREATE INDEX IF NOT EXISTS idx_profile_notified ON jobs(profile_id, notified);
"""

INSERT_JOB = """
INSERT INTO jobs (
    profile_id, id, site, title, company, location, url, description, posted_date,
    score, score_reason, notified
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(profile_id, id) DO UPDATE SET
    site         = excluded.site,
    title        = excluded.title,
    company      = excluded.company,
    location     = excluded.location,
    url          = excluded.url,
    description  = excluded.description,
    posted_date  = excluded.posted_date,
    score        = excluded.score,
    score_reason = excluded.score_reason,
    notified     = excluded.notified
    -- seen_at is intentionally NOT updated: preserves the original discovery timestamp
"""

UNNOTIFIED_MATCHES = """
SELECT
    id, site, title, company, location, url, description, posted_date,
    score, score_reason, notified
FROM jobs
WHERE profile_id = ? AND score >= ? AND notified = 0
ORDER BY score DESC, seen_at ASC
"""

MARK_NOTIFIED = "UPDATE jobs SET notified = 1 WHERE profile_id = ? AND id = ?"


class JobRepository:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.init()

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    def exists(self, profile_id: str, job_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM jobs WHERE profile_id = ? AND id = ?",
                (profile_id, job_id),
            ).fetchone()
            return row is not None

    def save(self, profile_id: str, job: Job) -> None:
        values = (
            profile_id,
            job.id,
            job.site,
            job.title,
            job.company,
            job.location,
            job.url,
            job.description,
            job.posted_date,
            job.score,
            job.score_reason,
            int(job.notified),
        )
        with self._connect() as conn:
            conn.execute(INSERT_JOB, values)

    def unnotified_matches(self, profile_id: str, threshold: int) -> Iterator[Job]:
        with self._connect() as conn:
            rows = conn.execute(UNNOTIFIED_MATCHES, (profile_id, threshold)).fetchall()

        for row in rows:
            yield _row_to_job(row)

    def mark_notified(self, profile_id: str, job_id: str) -> None:
        with self._connect() as conn:
            conn.execute(MARK_NOTIFIED, (profile_id, job_id))

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        site=row["site"],
        title=row["title"],
        company=row["company"],
        location=row["location"],
        url=row["url"],
        description=row["description"],
        posted_date=row["posted_date"],
        score=row["score"],
        score_reason=row["score_reason"],
        notified=bool(row["notified"]),
    )
