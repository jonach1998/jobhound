from __future__ import annotations

import json
import re
from contextlib import suppress
from typing import Any

from jobhound.models import Job

DESCRIPTION_MIN_LENGTH = 50
THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
SCORE_RE = re.compile(r'["\']?\bscore\b["\']?\s*[:=]\s*(\d{1,3})', re.IGNORECASE)
REASON_RE = re.compile(r'["\']?\breason\b["\']?\s*[:=]\s*(.+)', re.IGNORECASE | re.DOTALL)

SYSTEM_FORMAT_PREFIX = (
    "OUTPUT FORMAT (mandatory — follow exactly):\n"
    '{"score": <integer 0-100>, "pros": "<one line: what fits>", "cons": "<one line: what does not fit>"}\n\n'
)

JSON_SCHEMA = (
    "Reply with ONLY this JSON — no extra text, no markdown, no explanation:\n"
    '{"score": <integer 0-100>, "pros": "<one line: what fits the candidate>", "cons": "<one line: what does not fit>"}'
)

def user_prompt(cv_text: str, job: Job, description: str) -> str:
    description_hint = ""
    if len(description.strip()) < DESCRIPTION_MIN_LENGTH:
        description_hint = "(not available)"

    return (
        f"CANDIDATE CV:\n{cv_text}\n\n"
        f"JOB LISTING:\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location}\n"
        f"Description:{description_hint}\n{description}\n\n"
        f"{JSON_SCHEMA}"
    )


def parse_json(text: str) -> dict[str, Any]:
    text = THINK_BLOCK_RE.sub("", text).strip()
    return _try_full_json(text) or _try_partial_json(text) or _try_key_value(text) or {}


def _try_full_json(text: str) -> dict[str, Any] | None:
    with suppress(json.JSONDecodeError):
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    return None


def _try_partial_json(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        with suppress(json.JSONDecodeError):
            data, _ = decoder.raw_decode(text[index:])
            if isinstance(data, dict):
                return data
    return None


def _try_key_value(text: str) -> dict[str, Any] | None:
    score_match = SCORE_RE.search(text)
    if not score_match:
        return None
    reason_match = REASON_RE.search(text)
    return {
        "score": int(score_match.group(1)),
        "reason": clean_reason(reason_match.group(1)) if reason_match else "",
    }


def clean_reason(value: str) -> str:
    reason = value.strip().strip(",}").strip()
    return reason.strip("\"'").strip()


def clamp(score: int) -> int:
    return max(0, min(100, score))
