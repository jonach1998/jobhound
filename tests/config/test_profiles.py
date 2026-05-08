from __future__ import annotations

import unittest
from pathlib import Path

from jobhound.config import ProfileConfig

APP_ROOT = Path(__file__).resolve().parents[2]


class ProfilesTest(unittest.TestCase):
    def test_discover_loads_all_profiles(self) -> None:
        profiles = ProfileConfig.discover(APP_ROOT, "profile.yaml", "cv.txt", "scoring_prompt.txt")

        self.assertEqual(
            [profile.id for profile in profiles],
            ["vale-call-center", "vale-logistics"],
        )

    def test_vale_logistics_profile_loads(self) -> None:
        profile = ProfileConfig.from_id(
            APP_ROOT,
            "vale-logistics",
            "profile.yaml",
            "cv.txt",
            "scoring_prompt.txt",
        )

        self.assertEqual(profile.display_name, "Job Hunter Vale Logistics")
        self.assertEqual(profile.score_threshold, 70)
        self.assertIn("compras", profile.search_terms)
        self.assertIn("procurement", profile.search_terms)
        self.assertTrue(profile.cv_path.is_file())
        self.assertIn("coordinadora/analista senior", profile.scoring_prompt.lower())

    def test_vale_call_center_profile_loads(self) -> None:
        profile = ProfileConfig.from_id(
            APP_ROOT,
            "vale-call-center",
            "profile.yaml",
            "cv.txt",
            "scoring_prompt.txt",
        )

        self.assertEqual(profile.display_name, "Job Hunter Vale Call Center")
        self.assertEqual(profile.score_threshold, 70)
        self.assertIn("customer service representative", profile.search_terms)
        self.assertTrue(profile.cv_path.is_file())
        self.assertIn("score máximo 35", profile.scoring_prompt.lower())
        self.assertIn("advanced english", profile.scoring_prompt.lower())


if __name__ == "__main__":
    unittest.main()
