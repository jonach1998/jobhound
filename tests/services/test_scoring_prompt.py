from __future__ import annotations

import unittest

from jobhound.models import Job
from jobhound.services.scoring_prompt import clamp, parse_json, user_prompt


class ScoringPromptTest(unittest.TestCase):
    def test_clamp_keeps_score_between_zero_and_one_hundred(self) -> None:
        self.assertEqual(clamp(-10), 0)
        self.assertEqual(clamp(50), 50)
        self.assertEqual(clamp(110), 100)

    def test_parse_json_handles_extra_text(self) -> None:
        self.assertEqual(parse_json('texto {"score": 80, "reason": "ok"} fin')["score"], 80)

    def test_parse_json_ignores_minimax_thinking(self) -> None:
        content = '<think>{"score": 0}</think>\n\n{"score": 82, "reason": "good fit"}'

        self.assertEqual(parse_json(content)["score"], 82)

    def test_parse_json_handles_key_value_response(self) -> None:
        content = "Score: 74\nReason: good match for customer service"

        self.assertEqual(parse_json(content)["reason"], "good match for customer service")

    def test_parse_json_recovers_truncated_json_with_quoted_keys(self) -> None:
        content = '{"score": 63, "reason": "Good fit for customer service,'

        self.assertEqual(parse_json(content), {"score": 63, "reason": "Good fit for customer service"})

    def test_user_prompt_marks_short_description_as_missing(self) -> None:
        job = Job(id="1", site="test", title="Agente Call Center", company="Acme", location="CR")

        prompt = user_prompt("CV", job, "short")

        self.assertIn("Description:(not available)", prompt)

    def test_user_prompt_always_ends_with_json_schema(self) -> None:
        from jobhound.services.scoring_prompt import JSON_SCHEMA
        job = Job(id="1", site="test", title="Analyst")

        prompt = user_prompt("CV text", job, "Some job description long enough to pass the minimum.")

        self.assertTrue(prompt.endswith(JSON_SCHEMA))
        self.assertIn('"score"', prompt)
        self.assertIn('"pros"', prompt)
        self.assertIn('"cons"', prompt)


if __name__ == "__main__":
    unittest.main()
