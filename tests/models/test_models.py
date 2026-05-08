from __future__ import annotations

import unittest

from jobhound.models import make_job_id


class JobIdTest(unittest.TestCase):
    def test_make_job_id_is_stable(self) -> None:
        first = make_job_id("site", "https://example.test/job", "Buyer", "Acme")
        second = make_job_id("site", "https://example.test/job", "Buyer", "Acme")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 16)


if __name__ == "__main__":
    unittest.main()
