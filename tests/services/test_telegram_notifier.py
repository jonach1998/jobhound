from __future__ import annotations

import unittest

from jobhound.models import Job
from jobhound.services import TelegramNotifier
from jobhound.services.telegram_notifier import _days_ago, _job_message


class FakeResponse:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.status_code = 200 if ok else 500
        self.text = "ok" if ok else "error"


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.posts: list[dict] = []

    def post(self, url: str, json: dict, timeout: int) -> FakeResponse:
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        return self.responses.pop(0)


class TelegramNotifierTest(unittest.TestCase):
    def test_send_returns_false_without_chat_ids(self) -> None:
        notifier = TelegramNotifier(token="token", chat_ids=())

        self.assertFalse(notifier.enabled)
        self.assertFalse(notifier.send("hello"))

    def test_send_posts_to_all_chat_ids(self) -> None:
        session = FakeSession([FakeResponse(), FakeResponse()])
        notifier = TelegramNotifier(token="token", chat_ids=("1", "2"), session=session)

        self.assertTrue(notifier.enabled)
        self.assertTrue(notifier.send("hello"))
        self.assertEqual(len(session.posts), 2)

    def test_send_returns_true_if_at_least_one_chat_succeeds(self) -> None:
        session = FakeSession([FakeResponse(), FakeResponse(ok=False)])
        notifier = TelegramNotifier(token="token", chat_ids=("1", "2"), session=session)

        self.assertTrue(notifier.send("hello"))
        self.assertEqual(len(session.posts), 2)

    def test_send_returns_false_if_all_chats_fail(self) -> None:
        session = FakeSession([FakeResponse(ok=False), FakeResponse(ok=False)])
        notifier = TelegramNotifier(token="token", chat_ids=("1", "2"), session=session)

        self.assertFalse(notifier.send("hello"))

    def test_job_message_omits_company_when_empty(self) -> None:
        job = Job(id="1", site="linkedin", title="Dev", score=80, score_reason="ok", url="http://x.co")
        message = _job_message(job)

        self.assertIn("✅ 80/100 — Dev</b>", message)
        self.assertNotIn("(", message.split("</b>")[0])

    def test_job_message_includes_company_in_title_line(self) -> None:
        job = Job(id="1", site="linkedin", title="Dev", company="Acme", score=80, score_reason="ok", url="http://x.co")
        message = _job_message(job)

        self.assertIn("Dev (Acme)", message)
        self.assertNotIn("🏢", message)

    def test_job_message_omits_location_when_empty(self) -> None:
        job = Job(id="1", site="linkedin", title="Dev", company="Acme", score=80, score_reason="ok", url="http://x.co")
        message = _job_message(job)

        self.assertNotIn("📍", message)

    def test_job_message_includes_all_meta_fields(self) -> None:
        job = Job(id="1", site="linkedin", title="Dev", company="Acme", location="CR", score=80, score_reason="ok", url="http://x.co")
        message = _job_message(job, profile_name="Vale")

        self.assertIn("📍 CR", message)
        self.assertIn("🌐 linkedin", message)
        self.assertIn("👤 Vale", message)

    def test_job_message_formats_pros_cons_as_separate_lines(self) -> None:
        job = Job(id="1", site="linkedin", title="Dev", score=80,
                  score_reason="✔ good match\n✘ missing English", url="http://x.co")
        message = _job_message(job)

        self.assertIn("✔ good match", message)
        self.assertIn("✘ missing English", message)

    def test_job_message_includes_posted_date(self) -> None:
        from datetime import date, timedelta
        posted = (date.today() - timedelta(days=3)).isoformat()
        job = Job(id="1", site="linkedin", title="Dev", score=80, score_reason="ok",
                  url="http://x.co", posted_date=posted)
        message = _job_message(job)

        self.assertIn("🗓 3 days ago", message)

    def test_days_ago_today(self) -> None:
        from datetime import date
        self.assertEqual(_days_ago(date.today().isoformat()), "today")

    def test_days_ago_one_day(self) -> None:
        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.assertEqual(_days_ago(yesterday), "1 day ago")

    def test_days_ago_invalid_returns_empty(self) -> None:
        self.assertEqual(_days_ago(""), "")
        self.assertEqual(_days_ago("not-a-date"), "")

    def test_days_ago_future_date_returns_empty(self) -> None:
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(_days_ago(future), "")


if __name__ == "__main__":
    unittest.main()
