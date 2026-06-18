from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import httpx
from openai import APIConnectionError, APIStatusError

from jobhound.models import Job
from jobhound.services.job_scorer import JobScorer, coerce_score

_TEST_URL = "https://api.test"
_MINIMAX_URL = "https://api.minimax.io/v1"


def _job() -> Job:
    return Job(id="1", site="test", title="Customer Service")


def _fake_response(content: str, model_extra: dict | None = None) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.model_extra = model_extra
    return resp


def _make_scorer(responses: list[str], *, base_url: str = _TEST_URL) -> tuple[JobScorer, MagicMock]:
    scorer = JobScorer("key", "model", base_url, "system")
    mock_create = MagicMock(side_effect=[_fake_response(c) for c in responses])
    scorer._client.chat.completions.create = mock_create
    return scorer, mock_create


class JobScorerTest(unittest.TestCase):
    def test_score_parses_json_after_thinking(self) -> None:
        scorer, _ = _make_scorer(['<think>{"score": 0}</think>\n\n{"score": 88, "pros": "good match", "cons": "missing English"}'])

        score, reason = scorer.score("CV", _job())

        self.assertEqual(score, 88)
        self.assertIn("✔ good match", reason)
        self.assertIn("✘ missing English", reason)

    def test_score_marks_invalid_model_response_as_transient(self) -> None:
        scorer, _ = _make_scorer(["<think>thinking...</think>", "<think>still thinking...</think>"])

        score, reason = scorer.score("CV", _job())

        self.assertEqual(score, 0)
        self.assertIn("no JSON score in response", reason)
        self.assertTrue(reason.startswith("transient:"), f"expected 'transient:' but got: {reason!r}")

    def test_score_retries_on_missing_json_then_succeeds(self) -> None:
        scorer, _ = _make_scorer([
            "Let me analyze this listing...",
            '{"score": 72, "pros": "good match", "cons": "minor gap"}',
        ])

        score, reason = scorer.score("CV", _job())

        self.assertEqual(score, 72)
        self.assertIn("✔ good match", reason)

    def test_payload_includes_reasoning_split_for_minimax(self) -> None:
        scorer, mock_create = _make_scorer(
            ['{"score": 70, "pros": "ok", "cons": "gap"}'],
            base_url=_MINIMAX_URL,
        )

        scorer.score("CV", _job())

        self.assertEqual(mock_create.call_args.kwargs.get("extra_body"), {"reasoning_split": True})

    def test_payload_has_no_extra_body_for_other_providers(self) -> None:
        scorer, mock_create = _make_scorer(['{"score": 70, "pros": "ok", "cons": "gap"}'])

        scorer.score("CV", _job())

        self.assertFalse(mock_create.call_args.kwargs.get("extra_body"))

    def test_minimax_base_error_is_reported(self) -> None:
        scorer = JobScorer("key", "model", _MINIMAX_URL, "system")
        resp = _fake_response(
            '{"score": 70, "pros": "ok", "cons": "gap"}',
            model_extra={"base_resp": {"status_code": 1001, "status_msg": "bad request"}},
        )
        scorer._client.chat.completions.create = MagicMock(return_value=resp)

        score, reason = scorer.score("CV", _job())

        self.assertEqual(score, 0)
        self.assertIn("AI error 1001", reason)

    def test_score_formats_pros_cons_with_symbols(self) -> None:
        scorer, _ = _make_scorer(['{"score": 75, "pros": "transferable experience", "cons": "no direct experience"}'])

        _, reason = scorer.score("CV", _job())

        self.assertTrue(reason.startswith("✔ transferable experience"))
        self.assertIn("✘ no direct experience", reason)

    def test_score_falls_back_to_reason_without_pros_cons(self) -> None:
        scorer, _ = _make_scorer(['{"score": 60, "reason": "legacy format"}'])

        _, reason = scorer.score("CV", _job())

        self.assertEqual(reason, "legacy format")

    def test_coerce_score_accepts_string_score(self) -> None:
        self.assertEqual(coerce_score("82/100"), 82)

    def test_score_marks_network_error_as_transient(self) -> None:
        scorer = JobScorer("key", "model", _TEST_URL, "system")
        scorer._client.chat.completions.create = MagicMock(
            side_effect=APIConnectionError(request=httpx.Request("POST", _TEST_URL))
        )

        score, reason = scorer.score("CV", _job())

        self.assertEqual(score, 0)
        self.assertTrue(reason.startswith("transient:"), f"expected 'transient:' but got: {reason!r}")

    def test_score_marks_4xx_http_error_as_permanent(self) -> None:
        scorer = JobScorer("key", "model", _TEST_URL, "system")
        req = httpx.Request("POST", _TEST_URL)
        scorer._client.chat.completions.create = MagicMock(
            side_effect=APIStatusError("Unauthorized", response=httpx.Response(401, request=req), body=None)
        )

        score, reason = scorer.score("CV", _job())

        self.assertEqual(score, 0)
        self.assertTrue(reason.startswith("error:"), f"expected 'error:' but got: {reason!r}")

    def test_score_marks_5xx_http_error_as_transient(self) -> None:
        scorer = JobScorer("key", "model", _TEST_URL, "system")
        req = httpx.Request("POST", _TEST_URL)
        scorer._client.chat.completions.create = MagicMock(
            side_effect=APIStatusError("Service Unavailable", response=httpx.Response(503, request=req), body=None)
        )

        score, reason = scorer.score("CV", _job())

        self.assertEqual(score, 0)
        self.assertTrue(reason.startswith("transient:"), f"expected 'transient:' but got: {reason!r}")


if __name__ == "__main__":
    unittest.main()
