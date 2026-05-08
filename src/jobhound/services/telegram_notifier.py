from __future__ import annotations

import html
import logging
from datetime import date

import requests

from jobhound.utils.logging_utils import log_event
from jobhound.models import Job

log = logging.getLogger(__name__)

TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
MESSAGE_LIMIT = 4000
REQUEST_TIMEOUT = 30


class TelegramNotifier:
    def __init__(
        self,
        token: str,
        chat_ids: tuple[str, ...],
        session: requests.Session | None = None,
    ) -> None:
        self.token = token
        self.chat_ids = chat_ids
        self.session = session or requests.Session()

    def notify_job(self, job: Job, profile_name: str = "") -> bool:
        return self.send(_job_message(job, profile_name))

    def notify_summary(self, message: str) -> bool:
        return self.send(message)

    @property
    def enabled(self) -> bool:
        return bool(self.chat_ids)

    def send(self, message: str) -> bool:
        if not self.enabled:
            log.warning(log_event("telegram", "send.disabled", reason="chat ids not configured"))
            return False

        any_delivered = False
        for chat_id in self.chat_ids:
            if self._send(chat_id, message):
                any_delivered = True

        return any_delivered

    def _send(self, chat_id: str, message: str) -> bool:
        try:
            response = self.session.post(
                TELEGRAM_URL.format(token=self.token),
                json={
                    "chat_id": chat_id,
                    "text": message[:MESSAGE_LIMIT],
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            log.warning(log_event("telegram", "request.failed", chat_id=chat_id, error=exc))
            return False

        if not response.ok:
            log.warning(
                log_event(
                    "telegram",
                    "send.failed",
                    chat_id=chat_id,
                    status=response.status_code,
                    response=response.text[:300],
                )
            )
            return False

        return True


def _job_message(job: Job, profile_name: str = "") -> str:
    company_suffix = f" ({html.escape(job.company)})" if job.company else ""
    title_line = f"<b>✅ {job.score}/100 — {html.escape(job.title)}{company_suffix}</b>"

    meta: list[str] = []
    if job.location:
        meta.append(f"📍 {html.escape(job.location)}")
    meta.append(f"🌐 {html.escape(job.site)}")
    age = _days_ago(job.posted_date)
    if age:
        meta.append(f"🗓 {age}")
    if profile_name:
        meta.append(f"👤 {html.escape(profile_name)}")

    parts = [title_line, " · ".join(meta), ""]

    for line in job.score_reason.split("\n"):
        line = line.strip()
        if line:
            parts.append(f"<i>{html.escape(line)}</i>")

    parts.append("")
    parts.append(f'<a href="{html.escape(job.url)}">View job and apply →</a>')
    return "\n".join(parts)


def _days_ago(date_str: str) -> str:
    try:
        delta = (date.today() - date.fromisoformat(date_str)).days
    except (ValueError, TypeError):
        return ""
    if delta < 0:
        return ""
    if delta == 0:
        return "today"
    if delta == 1:
        return "1 day ago"
    return f"{delta} days ago"
