from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jobhound.config import AppConfig

REQUIRED_ENV = {
    "AI_API_KEY": "key",
    "AI_MODEL": "MiniMax-M2.7",
    "AI_BASE_URL": "https://api.minimax.io/v1",
    "SCHEDULE_HOURS": "08:00,20:00",
    "RUN_ON_STARTUP": "true",
    "TZ": "America/Costa_Rica",
    "PROFILE_YAML_FILENAME": "profile.yaml",
    "PROFILE_CV_FILENAME": "cv.txt",
    "PROFILE_SCORING_PROMPT_FILENAME": "scoring_prompt.txt",
}


class AppConfigTest(unittest.TestCase):
    def test_from_env_parses_required_values(self) -> None:
        with self.profile_app_dir() as app_dir, patch.dict(os.environ, REQUIRED_ENV, clear=True):
            config = AppConfig.from_env(app_dir)

        self.assertEqual([profile.id for profile in config.profiles], ["test-profile"])
        profile = config.profiles[0]
        self.assertEqual(config.schedule_hours, "8,20")
        self.assertTrue(config.run_on_startup)
        self.assertEqual(config.profile_yaml_filename, "profile.yaml")
        self.assertEqual(config.profile_cv_filename, "cv.txt")
        self.assertEqual(config.profile_scoring_prompt_filename, "scoring_prompt.txt")
        self.assertEqual(profile.display_name, "Test Profile")
        self.assertEqual(profile.score_threshold, 65)
        self.assertEqual(
            profile.search_terms,
            (
                "entry-level customer service representative",
                "junior customer service representative",
                "call center sin experiencia",
            ),
        )
        self.assertIn("Reply with ONLY the JSON", profile.scoring_prompt)

    def test_missing_profiles_folder_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(os.environ, REQUIRED_ENV, clear=True):
            app_dir = Path(tmp_dir) / "src"
            app_dir.mkdir()

            with self.assertRaisesRegex(RuntimeError, "Profiles directory not found"):
                AppConfig.from_env(app_dir)

    def test_invalid_schedule_hours_fails_fast(self) -> None:
        env = REQUIRED_ENV | {"SCHEDULE_HOURS": "08:00,25:00"}
        with (
            self.profile_app_dir() as app_dir,
            patch.dict(os.environ, env, clear=True),
            self.assertRaisesRegex(RuntimeError, "SCHEDULE_HOURS"),
        ):
            AppConfig.from_env(app_dir)

    def test_schedule_hours_with_minutes_not_zero_fails(self) -> None:
        env = REQUIRED_ENV | {"SCHEDULE_HOURS": "08:30,20:00"}
        with (
            self.profile_app_dir() as app_dir,
            patch.dict(os.environ, env, clear=True),
            self.assertRaisesRegex(RuntimeError, "SCHEDULE_HOURS"),
        ):
            AppConfig.from_env(app_dir)

    def profile_app_dir(self):
        return ProfileFixture()


class ProfileFixture:
    def __enter__(self) -> Path:
        self.tmp_dir = tempfile.TemporaryDirectory()
        root = Path(self.tmp_dir.name)
        app_dir = root / "src"
        profile_dir = root / "profiles" / "test-profile"
        app_dir.mkdir()
        profile_dir.mkdir(parents=True)
        (profile_dir / "cv.txt").write_text("CV", encoding="utf-8")
        (profile_dir / "scoring_prompt.txt").write_text(
            "Reply with ONLY the JSON.",
            encoding="utf-8",
        )
        (profile_dir / "profile.yaml").write_text(
            """
display_name: "Test Profile"
score_threshold: 65
country: "costa rica"
search_terms:
  - "entry-level customer service representative"
  - "junior customer service representative"
  - "call center sin experiencia"
""".strip(),
            encoding="utf-8",
        )
        return app_dir

    def __exit__(self, exc_type, exc, tb) -> None:
        self.tmp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
