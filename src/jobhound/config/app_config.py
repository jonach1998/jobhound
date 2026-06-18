from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jobhound.config.env import (
    bool_env,
    optional_csv_env,
    optional_float_env,
    optional_int_env,
    required_env,
    schedule_hours_env,
)
from jobhound.config.profile_config import ProfileConfig


@dataclass(frozen=True, slots=True)
class AppConfig:
    profiles: tuple[ProfileConfig, ...]
    schedule_hours: str
    run_on_startup: bool
    timezone: str
    profile_yaml_filename: str
    profile_cv_filename: str
    profile_scoring_prompt_filename: str
    ai_api_key: str
    ai_model: str
    ai_base_url: str
    ai_max_completion_tokens: int
    ai_temperature: float
    telegram_bot_token: str
    telegram_chat_ids: tuple[str, ...]

    @classmethod
    def from_env(cls, app_dir: Path) -> AppConfig:
        telegram_chat_ids = optional_csv_env("TELEGRAM_CHAT_IDS")
        profile_yaml_filename = required_env("PROFILE_YAML_FILENAME")
        profile_cv_filename = required_env("PROFILE_CV_FILENAME")
        profile_scoring_prompt_filename = required_env("PROFILE_SCORING_PROMPT_FILENAME")
        return cls(
            profiles=ProfileConfig.discover(
                app_dir.parent,
                profile_yaml_filename,
                profile_cv_filename,
                profile_scoring_prompt_filename,
            ),
            schedule_hours=schedule_hours_env("SCHEDULE_HOURS"),
            run_on_startup=bool_env("RUN_ON_STARTUP"),
            timezone=required_env("TZ"),
            profile_yaml_filename=profile_yaml_filename,
            profile_cv_filename=profile_cv_filename,
            profile_scoring_prompt_filename=profile_scoring_prompt_filename,
            ai_api_key=required_env("AI_API_KEY"),
            ai_model=required_env("AI_MODEL"),
            ai_base_url=required_env("AI_BASE_URL"),
            ai_max_completion_tokens=optional_int_env("AI_MAX_COMPLETION_TOKENS", 0),
            ai_temperature=optional_float_env("AI_TEMPERATURE", 0.1),
            telegram_bot_token=required_env("TELEGRAM_BOT_TOKEN") if telegram_chat_ids else "",
            telegram_chat_ids=telegram_chat_ids,
        )
