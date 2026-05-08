from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from jobhound.config import ProfileConfig

APP_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = APP_ROOT / "profiles" / "example"


class ProfileLoadTest(unittest.TestCase):
    def test_example_profile_loads_via_from_id(self) -> None:
        profile = ProfileConfig.from_id(
            APP_ROOT, "example", "profile.yaml", "cv.txt", "scoring_prompt.txt"
        )

        self.assertEqual(profile.display_name, "Customer Service - San José, CR")
        self.assertEqual(profile.score_threshold, 70)
        self.assertIn("customer service representative", profile.search_terms)
        self.assertTrue(profile.cv_path.is_file())
        self.assertGreater(len(profile.scoring_prompt), 100)
        self.assertGreater(len(profile.cv_text), 100)

    def test_profile_search_terms_are_non_empty_strings(self) -> None:
        profile = ProfileConfig.from_id(
            APP_ROOT, "example", "profile.yaml", "cv.txt", "scoring_prompt.txt"
        )

        self.assertTrue(all(isinstance(t, str) and t.strip() for t in profile.search_terms))


class ProfileDiscoverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_profile(self, name: str, extra_yaml: str = "") -> None:
        d = self.tmp / "profiles" / name
        d.mkdir(parents=True)
        shutil.copy(EXAMPLE_DIR / "cv.txt", d / "cv.txt")
        shutil.copy(EXAMPLE_DIR / "scoring_prompt.txt", d / "scoring_prompt.txt")
        (d / "profile.yaml").write_text(
            f'display_name: "{name}"\nscore_threshold: 70\nsearch_terms:\n  - "test"\n{extra_yaml}'
        )

    def test_discover_finds_active_profiles(self) -> None:
        self._make_profile("alpha")
        self._make_profile("beta")

        profiles = ProfileConfig.discover(self.tmp, "profile.yaml", "cv.txt", "scoring_prompt.txt")

        self.assertEqual([p.id for p in profiles], ["alpha", "beta"])

    def test_discover_skips_example_profiles(self) -> None:
        self._make_profile("active")
        self._make_profile("template", extra_yaml="example: true\n")

        profiles = ProfileConfig.discover(self.tmp, "profile.yaml", "cv.txt", "scoring_prompt.txt")

        self.assertEqual([p.id for p in profiles], ["active"])

    def test_discover_raises_when_no_active_profiles(self) -> None:
        self._make_profile("template", extra_yaml="example: true\n")

        with self.assertRaises(RuntimeError):
            ProfileConfig.discover(self.tmp, "profile.yaml", "cv.txt", "scoring_prompt.txt")

    def test_discover_raises_when_profiles_dir_missing(self) -> None:
        with self.assertRaises(RuntimeError):
            ProfileConfig.discover(self.tmp, "profile.yaml", "cv.txt", "scoring_prompt.txt")


if __name__ == "__main__":
    unittest.main()
