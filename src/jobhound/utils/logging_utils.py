from __future__ import annotations

from collections.abc import Iterable
from textwrap import wrap
from typing import Any

BLOCK_WIDTH = 96
EVENT_WIDTH = 20
MAX_FIELD_LENGTH = 220


def log_block(title: str, rows: Iterable[tuple[str, Any]], width: int = BLOCK_WIDTH) -> str:
    clean_rows = [(str(label), _stringify(value)) for label, value in rows]
    label_width = _label_width(clean_rows)
    value_width = width - label_width - 7
    border = _border(label_width, value_width)

    lines = [border, _title(title, len(border)), border]
    for label, value in clean_rows:
        lines.extend(_row_lines(label, value, label_width, value_width))
    lines.append(border)
    return "\n".join(lines)


def log_event(profile_id: str, event: str, **fields: Any) -> str:
    details = " | ".join(
        f"{key}={shorten(value)}" for key, value in fields.items() if value is not None
    )
    prefix = f"[{profile_id}] {event:<{EVENT_WIDTH}}"
    return f"{prefix} | {details}" if details else prefix.rstrip()


def format_list(values: Iterable[Any], separator: str = " | ") -> str:
    return separator.join(_stringify(value) for value in values)


def format_schedule_hours(schedule_hours: str) -> str:
    hours = [hour.strip() for hour in schedule_hours.split(",") if hour.strip()]
    return ", ".join(f"{hour}:00" for hour in hours)


def shorten(value: Any, max_length: int = MAX_FIELD_LENGTH) -> str:
    text = " ".join(_stringify(value).split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _label_width(rows: list[tuple[str, str]]) -> int:
    longest_label = max((len(label) for label, _ in rows), default=12)
    return max(12, min(longest_label, 28))


def _row_lines(label: str, value: str, label_width: int, value_width: int) -> list[str]:
    wrapped_value = wrap(value, width=value_width, break_long_words=False) or [""]
    lines = []
    for index, line in enumerate(wrapped_value):
        label_cell = label if index == 0 else ""
        lines.append(f"| {label_cell:<{label_width}} | {line:<{value_width}} |")
    return lines


def _border(label_width: int, value_width: int) -> str:
    return f"+{'-' * (label_width + 2)}+{'-' * (value_width + 2)}+"


def _title(title: str, border_width: int) -> str:
    inner_width = border_width - 4
    return f"| {shorten(title, inner_width):<{inner_width}} |"


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)
