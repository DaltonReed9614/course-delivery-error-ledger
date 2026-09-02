"""Domain decision for grouping course delivery failures."""

from __future__ import annotations

import hashlib
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

@dataclass(frozen=True)
class DeliveryAttempt:
    course_id: str
    learner_id: str
    delivery_stage: str
    deadline_at: datetime
    educator_report_id: str

    def __post_init__(self) -> None:
        for field_name in ("course_id", "learner_id", "delivery_stage", "educator_report_id"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True)
class DeliveryResult:
    status: str
    course_id: str
    learner_id: str
    error_event: dict[str, Any] | None = None


class CaptureClient(Protocol):
    def capture(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]: ...


def grouping_fingerprint(attempt: DeliveryAttempt) -> list[str]:
    """Group operationally identical failures without learner-level fan-out."""
    return ["course-delivery", attempt.course_id, attempt.delivery_stage]


def deliver_course(
    attempt: DeliveryAttempt,
    deliver: Callable[[DeliveryAttempt], None],
    infrai: CaptureClient,
) -> DeliveryResult:
    try:
        deliver(attempt)
    except Exception as exc:
        payload = {
            "title": f"Course delivery failed at {attempt.delivery_stage}",
            "message": f"{type(exc).__name__}: {exc}",
            "level": "error",
            "fingerprint": grouping_fingerprint(attempt),
            "exception": traceback.format_exc(),
            "context": {
                "course_id": attempt.course_id,
                "learner_id": attempt.learner_id,
                "delivery_stage": attempt.delivery_stage,
                "deadline_at": attempt.deadline_at.isoformat(),
                "educator_report_id": attempt.educator_report_id,
            },
        }
        request_identity = "|".join(
            [attempt.course_id, attempt.learner_id, attempt.delivery_stage, attempt.deadline_at.isoformat()]
        )
        idempotency_key = hashlib.sha256(request_identity.encode()).hexdigest()
        event = infrai.capture(payload, idempotency_key=idempotency_key)
        return DeliveryResult(
            status="captured",
            course_id=attempt.course_id,
            learner_id=attempt.learner_id,
            error_event=event,
        )

    return DeliveryResult(
        status="delivered",
        course_id=attempt.course_id,
        learner_id=attempt.learner_id,
    )
