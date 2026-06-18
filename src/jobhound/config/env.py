from __future__ import annotations

import os

TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off"}


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def optional_csv_env(name: str) -> tuple[str, ...]:
    return _split_csv(os.environ.get(name, ""))


def schedule_hours_env(name: str) -> str:
    hours = []
    for entry in _split_csv(required_env(name)):
        parts = entry.split(":")
        if len(parts) == 2 and parts[1] != "00":
            raise RuntimeError(f"{name} only accepts full hours, e.g. 08:00,20:00")
        try:
            hour = int(parts[0])
        except ValueError as exc:
            raise RuntimeError(f"{name} only accepts full hours, e.g. 08:00,20:00") from exc
        if not 0 <= hour <= 23:
            raise RuntimeError(f"{name} only accepts hours between 0 and 23")
        hours.append(str(hour))

    if not hours:
        raise RuntimeError(f"{name} must have at least one hour")
    return ",".join(hours)


def bool_env(name: str) -> bool:
    value = required_env(name).lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False

    raise RuntimeError(f"{name} must be a boolean: true/false")


def optional_int_env(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def optional_float_env(name: str, default: float) -> float:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in raw.split(",") if value.strip())
