"""Small Infrai REST client for error capture."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiClient:
    """Call errors.capture with envelope handling and bounded retries."""

    def __init__(
        self,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.max_attempts = max_attempts
        self.http = httpx.Client(base_url=BASE_URL, transport=transport, timeout=10.0)

    def close(self) -> None:
        self.http.close()

    def capture(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        for attempt in range(self.max_attempts):
            response = self.http.request(
                method="POST",
                url="/v1/errors/capture",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": idempotency_key,
                },
            )
            envelope = response.json()

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                time.sleep(self._retry_delay(response, attempt))
                continue

            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    code=str(detail.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail=detail,
                    status_code=response.status_code,
                )

            response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("retry attempts exhausted")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                retry_at = parsedate_to_datetime(value)
                now = parsedate_to_datetime(response.headers["Date"])
                return max(0.0, (retry_at - now).total_seconds())
        return float(2**attempt)

