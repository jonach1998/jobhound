from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jobhound.models import Job
from jobhound.repositories import JobRepository


class JobRepositoryTest(unittest.TestCase):
    def test_unnotified_matches_returns_high_score_pending_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repository = JobRepository(Path(tmp_dir) / "jobs.sqlite")
            repository.init()
            repository.save(
                "profile-a",
                Job(
                    id="1",
                    site="test",
                    title="Customer Service",
                    score=88,
                    score_reason="Good match.",
                    notified=False,
                )
            )
            repository.save(
                "profile-a",
                Job(
                    id="2",
                    site="test",
                    title="Low score",
                    score=40,
                    score_reason="Not a match.",
                    notified=False,
                )
            )

            pending = list(repository.unnotified_matches("profile-a", 60))

        self.assertEqual([job.id for job in pending], ["1"])

    def test_mark_notified_removes_match_from_pending_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repository = JobRepository(Path(tmp_dir) / "jobs.sqlite")
            repository.init()
            repository.save(
                "profile-a",
                Job(
                    id="1",
                    site="test",
                    title="Customer Service",
                    score=88,
                    score_reason="Good match.",
                    notified=False,
                )
            )
            repository.mark_notified("profile-a", "1")

            pending = list(repository.unnotified_matches("profile-a", 60))

        self.assertEqual(pending, [])

    def test_exists_returns_false_before_save_and_true_after(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repository = JobRepository(Path(tmp_dir) / "jobs.sqlite")
            job = Job(id="new-job", site="test", title="Analyst")

            self.assertFalse(repository.exists("profile-a", "new-job"))
            repository.save("profile-a", job)
            self.assertTrue(repository.exists("profile-a", "new-job"))

    def test_same_job_id_can_exist_in_different_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repository = JobRepository(Path(tmp_dir) / "jobs.sqlite")
            repository.init()
            job = Job(id="1", site="test", title="Customer Service", score=80, notified=False)

            repository.save("profile-a", job)
            repository.save("profile-b", job)

            self.assertTrue(repository.exists("profile-a", "1"))
            self.assertTrue(repository.exists("profile-b", "1"))
            self.assertFalse(repository.exists("profile-c", "1"))


if __name__ == "__main__":
    unittest.main()
