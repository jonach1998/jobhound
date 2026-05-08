from __future__ import annotations

import unittest

from jobhound.utils.logging_utils import format_schedule_hours, log_block, log_event, shorten


class LoggingUtilsTest(unittest.TestCase):
    def test_log_block_formats_rows(self) -> None:
        message = log_block("Run started", (("profiles", 2), ("timezone", "America/Costa_Rica")))

        self.assertIn("Run started", message)
        self.assertIn("| profiles", message)
        self.assertIn("| timezone", message)

    def test_log_event_formats_key_values(self) -> None:
        message = log_event("vale-logistics", "job.skipped", score=45, threshold=70)

        self.assertIn("[vale-logistics] job.skipped", message)
        self.assertIn("score=45", message)
        self.assertIn("threshold=70", message)

    def test_shorten_limits_long_text(self) -> None:
        message = shorten("x" * 20, max_length=10)

        self.assertEqual(message, "xxxxxxx...")

    def test_format_schedule_hours_expands_comma_separated_hours(self) -> None:
        self.assertEqual(format_schedule_hours("8,20"), "8:00, 20:00")


if __name__ == "__main__":
    unittest.main()
