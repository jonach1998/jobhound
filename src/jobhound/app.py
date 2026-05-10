from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jobhound.config import AppConfig, ProfileConfig
from jobhound.utils.logging_utils import format_list, format_schedule_hours, log_block, log_event, shorten
from jobhound.models import Job
from jobhound.repositories import JobRepository
from jobhound.scrapers import SCRAPERS, BaseScraper
from jobhound.services import JobScorer, TelegramNotifier

log = logging.getLogger(__name__)


@dataclass(slots=True)
class _RunStats:
    new_jobs: int = 0
    already_seen: int = 0
    notified: int = 0
    notification_errors: int = 0
    retried_notifications: int = 0
    low_score: int = 0
    scoring_errors: int = 0


def _build_summary_message(all_stats: list[tuple[ProfileConfig, _RunStats]]) -> str:
    lines = ["📊 <b>Run complete</b>"]
    for profile, stats in all_stats:
        lines.append(f"\n👤 <b>{profile.display_name}</b>")
        lines.append(f"New: {stats.new_jobs} · Already seen: {stats.already_seen}")
        lines.append(f"Notified (≥{profile.score_threshold}): {stats.notified} · Low score: {stats.low_score}")
        if stats.scoring_errors:
            lines.append(f"Scoring errors: {stats.scoring_errors}")
        if stats.notification_errors:
            lines.append(f"Telegram errors: {stats.notification_errors}")
    return "\n".join(lines)


class JobHoundApp:
    def __init__(
        self,
        config: AppConfig,
        repository: JobRepository,
        notifier: TelegramNotifier,
    ) -> None:
        self.config = config
        self.repository = repository
        self.notifier = notifier

    @classmethod
    def from_env(cls, app_dir: Path) -> JobHoundApp:
        config = AppConfig.from_env(app_dir)
        return cls(
            config=config,
            repository=JobRepository(app_dir.parent / "data" / "jobs.sqlite"),
            notifier=TelegramNotifier(
                token=config.telegram_bot_token,
                chat_ids=config.telegram_chat_ids,
            ),
        )

    def start(self) -> None:
        self._log_startup_header()

        if self.config.run_on_startup:
            self.run_profiles_once()

        self._start_scheduler()

    def _log_startup_header(self) -> None:
        telegram_status = "enabled" if self.notifier.enabled else "disabled"
        log.info(
            log_block(
                "JobHound — startup configuration",
                (
                    ("profiles", len(self.config.profiles)),
                    ("schedule", format_schedule_hours(self.config.schedule_hours)),
                    ("run_on_startup", self.config.run_on_startup),
                    ("timezone", self.config.timezone),
                    ("yaml_filename", self.config.profile_yaml_filename),
                    ("cv_filename", self.config.profile_cv_filename),
                    ("prompt_filename", self.config.profile_scoring_prompt_filename),
                    ("ai_model", self.config.ai_model),
                    ("ai_base_url", self.config.ai_base_url),
                    ("telegram", f"{telegram_status} ({len(self.config.telegram_chat_ids)} chats)"),
                ),
            )
        )
        for profile in self.config.profiles:
            log.info(
                log_block(
                    f"Profile — {profile.display_name}",
                    (
                        ("profile_id", profile.id),
                        ("threshold", profile.score_threshold),
                        ("search_terms", len(profile.search_terms)),
                        ("terms", format_list(profile.search_terms)),
                        ("cv", profile.cv_path),
                    ),
                )
            )

    def run_profiles_once(self) -> None:
        log.info(
            log_block(
                "Run started",
                (
                    ("started_at", datetime.now().isoformat(timespec="seconds")),
                    ("profiles", format_list(profile.id for profile in self.config.profiles)),
                ),
            )
        )

        all_stats: list[tuple[ProfileConfig, _RunStats]] = []
        for profile in self.config.profiles:
            try:
                stats = self._run_profile_once(profile)
                all_stats.append((profile, stats))
            except Exception:
                log.exception(log_event(profile.id, "profile.failed"))

        self._notify_run_summary(all_stats)

    def _run_profile_once(self, profile: ProfileConfig) -> _RunStats:
        log.info(
            log_block(
                f"Profile run — {profile.display_name}",
                (
                    ("profile_id", profile.id),
                    ("threshold", profile.score_threshold),
                    ("terms", len(profile.search_terms)),
                ),
            )
        )

        scorer = self._scorer_for(profile)
        stats = _RunStats()
        seen_this_run: set[str] = set()
        self._retry_pending_notifications(profile, stats)

        for job in self._scrape_jobs(profile):
            if self.repository.exists(profile.id, job.id):
                stats.already_seen += 1
                continue
            content_key = f"{job.title.lower().strip()}|{job.company.lower().strip()}"
            if content_key in seen_this_run:
                stats.already_seen += 1
                continue
            seen_this_run.add(content_key)
            self._process_job(profile, scorer, job, stats)

        self._finish_run(profile, stats)
        return stats

    def _scrape_jobs(self, profile: ProfileConfig) -> Iterator[Job]:
        for scraper in self._scrapers_for(profile):
            name = type(scraper).__name__.replace("Scraper", "")
            yielded = 0
            for job in scraper.scrape():
                yielded += 1
                yield job
            log.info(f"[{profile.id}] {name} → {yielded} candidates")

    def _retry_pending_notifications(self, profile: ProfileConfig, stats: _RunStats) -> None:
        if not self.notifier.enabled:
            return

        for job in self.repository.unnotified_matches(profile.id, profile.score_threshold):
            log.info(
                log_event(
                    profile.id,
                    "notify.retry",
                    score=job.score,
                    threshold=profile.score_threshold,
                    title=job.title,
                )
            )
            if self.notifier.notify_job(job, profile.display_name):
                self.repository.mark_notified(profile.id, job.id)
                stats.retried_notifications += 1
            else:
                stats.notification_errors += 1

    def _process_job(
        self,
        profile: ProfileConfig,
        scorer: JobScorer,
        job: Job,
        stats: _RunStats,
    ) -> None:
        stats.new_jobs += 1
        job.score, job.score_reason = scorer.score(profile.cv_text, job)

        if job.score_reason.startswith("transient:"):
            # Intentionally not saved: transient failures (network, 5xx) will be retried next run.
            stats.scoring_errors += 1
            _log_job_result(profile.id, "⚠️", job)
            return

        if job.score_reason.startswith("error:"):
            stats.scoring_errors += 1
            _log_job_result(profile.id, "❌", job)
            self.repository.save(profile.id, job)
            return

        if job.score >= profile.score_threshold:
            suffix = ""
            if self.notifier.enabled:
                if self.notifier.notify_job(job, profile.display_name):
                    job.notified = True
                    stats.notified += 1
                    suffix = "→ notified"
                else:
                    stats.notification_errors += 1
                    suffix = "⚠ Telegram failed"
            _log_job_result(profile.id, "✅", job, suffix)
        else:
            stats.low_score += 1
            _log_job_result(profile.id, "❌", job)

        self.repository.save(profile.id, job)

    def _finish_run(self, profile: ProfileConfig, stats: _RunStats) -> None:
        log.info(
            log_block(
                f"Summary — {profile.display_name}",
                (
                    ("profile_id", profile.id),
                    ("threshold", profile.score_threshold),
                    ("new_jobs", stats.new_jobs),
                    ("already_seen", stats.already_seen),
                    ("notified", stats.notified),
                    ("retried_notifications", stats.retried_notifications),
                    ("low_score", stats.low_score),
                    ("scoring_errors", stats.scoring_errors),
                    ("telegram_errors", stats.notification_errors),
                ),
            )
        )

    def _notify_run_summary(self, all_stats: list[tuple[ProfileConfig, _RunStats]]) -> None:
        if not self.notifier.enabled or not all_stats:
            return
        total_new = sum(s.new_jobs for _, s in all_stats)
        total_notified = sum(s.notified + s.retried_notifications for _, s in all_stats)
        if total_new > 0 and total_notified == 0:
            if not self.notifier.notify_summary(_build_summary_message(all_stats)):
                log.warning(log_event("run", "summary.failed"))

    def _scrapers_for(self, profile: ProfileConfig) -> list[BaseScraper]:
        return [
            s for cls in SCRAPERS
            if _scraper_name(cls) not in profile.disable_scrapers
            if (s := cls.from_profile(profile)) is not None
        ]

    def _scorer_for(self, profile: ProfileConfig) -> JobScorer:
        return JobScorer(
            api_key=self.config.ai_api_key,
            model=self.config.ai_model,
            base_url=self.config.ai_base_url,
            system_prompt=profile.scoring_prompt,
        )

    def _start_scheduler(self) -> None:
        from apscheduler.schedulers.blocking import BlockingScheduler

        scheduler = BlockingScheduler(timezone=self.config.timezone)
        scheduler.add_job(
            self.run_profiles_once,
            "cron",
            hour=self.config.schedule_hours,
            minute=0,
            id="hunt",
            misfire_grace_time=600,
            max_instances=1,
        )
        log.info(
            log_block(
                "Scheduler ready",
                (
                    ("profiles", format_list(profile.id for profile in self.config.profiles)),
                    ("hours", format_schedule_hours(self.config.schedule_hours)),
                    ("timezone", self.config.timezone),
                ),
            )
        )
        scheduler.start()


def _scraper_name(cls: type[BaseScraper]) -> str:
    """Derive a stable lowercase name from the class: ComputrabajoScraper → 'computrabajo'."""
    return cls.__name__.lower().removesuffix("scraper")


def _log_job_result(profile_id: str, icon: str, job: Job, suffix: str = "") -> None:
    company = f" — {job.company}" if job.company else ""
    reason = shorten(job.score_reason.replace("\n", "  |  "), 120)
    parts = [f"[{profile_id}] {icon} {job.score:3}/100  {job.title}{company}"]
    if reason:
        parts.append(reason)
    if suffix:
        parts.append(suffix)
    log.info("  |  ".join(parts))
