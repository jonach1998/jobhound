from __future__ import annotations

import logging
import re
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI

from jobhound.models import Job
from jobhound.services.scoring_prompt import SYSTEM_FORMAT_PREFIX, clamp, parse_json, user_prompt

log = logging.getLogger(__name__)

DESCRIPTION_LIMIT = 3500
MAX_JSON_RETRIES = 1
INVALID_RESPONSE_SNIPPET_LENGTH = 240
SCORE_NUMBER_RE = re.compile(r"\d{1,3}")


class JobScorer:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        system_prompt: str,
        max_completion_tokens: int = 0,
        temperature: float = 0.1,
    ) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.max_completion_tokens = max_completion_tokens
        self.temperature = temperature
        self._is_minimax = "minimax" in base_url.lower()
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def score(self, cv_text: str, job: Job) -> tuple[int, str]:
        description = job.description[:DESCRIPTION_LIMIT]
        last_json_error: str = ""

        for attempt in range(MAX_JSON_RETRIES + 1):
            try:
                content = self._completion(cv_text, job, description)
                data = parse_json(content)
                if "score" not in data:
                    last_json_error = f"transient: no JSON score in response: {safe_snippet(content)}"
                    if attempt < MAX_JSON_RETRIES:
                        company = f" — {job.company}" if job.company else ""
                        log.info(
                            f"[ai] retrying ({attempt + 1}/{MAX_JSON_RETRIES}) — {job.title}{company}"
                        )
                    continue

                pros = str(data.get("pros", "")).strip()
                cons = str(data.get("cons", "")).strip()
                parts = []
                if pros:
                    parts.append(f"✔ {pros}")
                if cons:
                    parts.append(f"✘ {cons}")
                reason = "\n".join(parts) if parts else str(data.get("reason", "")).strip()
                return clamp(coerce_score(data["score"])), reason
            except APIStatusError as exc:
                if exc.status_code == 429 or exc.status_code >= 500:
                    return 0, f"transient: {exc}"
                return 0, f"error: {exc}"
            except APIConnectionError as exc:
                return 0, f"transient: {exc}"
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                return 0, f"error: {exc}"

        return 0, last_json_error or "transient: no valid response"

    def _completion(self, cv_text: str, job: Job, description: str) -> str:
        extra: dict[str, Any] = {"reasoning_split": True} if self._is_minimax else {}

        optional: dict[str, Any] = {}
        if self.max_completion_tokens > 0:
            optional["max_tokens"] = self.max_completion_tokens

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_FORMAT_PREFIX + self.system_prompt},
                {"role": "user", "content": user_prompt(cv_text, job, description)},
            ],
            response_format={"type": "json_object"},
            temperature=self.temperature,
            extra_body=extra or None,
            **optional,
        )

        if self._is_minimax and response.model_extra:
            base_resp = response.model_extra.get("base_resp") or {}
            status_code = base_resp.get("status_code", 0)
            if status_code:
                raise ValueError(
                    f"AI error {status_code}: {base_resp.get('status_msg', 'no detail')}"
                )
            if response.model_extra.get("input_sensitive") or response.model_extra.get(
                "output_sensitive"
            ):
                raise ValueError("AI flagged the request or response as sensitive")

        return response.choices[0].message.content or ""


def coerce_score(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)

    match = SCORE_NUMBER_RE.search(str(value))
    if not match:
        raise ValueError(f"invalid score: {value!r}")

    return int(match.group(0))


def safe_snippet(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= INVALID_RESPONSE_SNIPPET_LENGTH:
        return cleaned

    return f"{cleaned[:INVALID_RESPONSE_SNIPPET_LENGTH]}..."
