from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProfileConfig:
    id: str
    display_name: str
    score_threshold: int
    country: str
    location: str
    cv_path: Path
    cv_text: str
    scoring_prompt: str
    search_terms: tuple[str, ...]

    @classmethod
    def from_id(
        cls,
        app_root: Path,
        profile_id: str,
        yaml_filename: str,
        cv_filename: str,
        scoring_prompt_filename: str,
    ) -> ProfileConfig:
        profile_dir = app_root / "profiles" / profile_id
        profile_path = profile_dir / yaml_filename
        if not profile_path.is_file():
            raise RuntimeError(f"Profile not found — {profile_id}: {profile_path}")

        data = _load_profile_yaml(profile_path)
        cv_path = profile_dir / cv_filename
        scoring_prompt_path = profile_dir / scoring_prompt_filename
        _ensure_profile_file(cv_path, profile_id, "CV")
        _ensure_profile_file(scoring_prompt_path, profile_id, "scoring prompt")

        country = _required_text(data, "country").lower()
        location = _optional_text(data, "location") or country.title()

        return cls(
            id=profile_id,
            display_name=_required_text(data, "display_name"),
            score_threshold=_required_score_threshold(data),
            country=country,
            location=location,
            cv_path=cv_path,
            cv_text=cv_path.read_text(encoding="utf-8"),
            scoring_prompt=scoring_prompt_path.read_text(encoding="utf-8"),
            search_terms=_required_string_list(data, "search_terms"),
        )

    @classmethod
    def discover(
        cls,
        app_root: Path,
        yaml_filename: str,
        cv_filename: str,
        scoring_prompt_filename: str,
    ) -> tuple[ProfileConfig, ...]:
        profiles_dir = app_root / "profiles"
        if not profiles_dir.is_dir():
            raise RuntimeError(f"Profiles directory not found: {profiles_dir}")

        all_ids = sorted(
            path.name for path in profiles_dir.iterdir() if (path / yaml_filename).is_file()
        )
        profile_ids = [
            pid for pid in all_ids
            if not _is_example_profile(profiles_dir / pid / yaml_filename)
        ]
        skipped = set(all_ids) - set(profile_ids)
        if skipped:
            log.info("Skipping example profile(s): %s — remove 'example: true' to activate.", ", ".join(sorted(skipped)))
        if not profile_ids:
            raise RuntimeError(f"No profiles found in {profiles_dir}")

        return tuple(
            cls.from_id(app_root, profile_id, yaml_filename, cv_filename, scoring_prompt_filename)
            for profile_id in profile_ids
        )


def _is_example_profile(path: Path) -> bool:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return isinstance(data, dict) and data.get("example") is True
    except Exception:
        return False


def _load_profile_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid profile.yaml: {path}")
    return data


def _ensure_profile_file(path: Path, profile_id: str, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"Profile {profile_id} is missing {label}: {path}")


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"profile.yaml requires {key} as a string")
    return value.strip()


def _optional_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise RuntimeError(f"profile.yaml expects {key} as a string")
    return value.strip()


def _required_score_threshold(data: dict[str, Any]) -> int:
    key = "score_threshold"
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"profile.yaml requires {key} as an integer")
    if not 0 <= value <= 100:
        raise RuntimeError(f"profile.yaml requires {key} between 0 and 100")
    return value


def _required_string_list(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list):
        raise RuntimeError(f"profile.yaml requires {key} as a list")

    values = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    if not values:
        raise RuntimeError(f"profile.yaml requires at least one value in {key}")
    return values
