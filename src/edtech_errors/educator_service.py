"""Executable HTTP boundary for course delivery attempts."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .course_delivery import DeliveryAttempt, DeliveryResult, deliver_course
from .infrai_client import InfraiClient, InfraiError

service = FastAPI(title="Course delivery error capture")


def send_learning_package(attempt: DeliveryAttempt) -> None:
    """Represent the incumbent course-delivery call in this focused example."""
    if attempt.delivery_stage == "content-package":
        raise ValueError("learning package checksum mismatch")


@service.post("/delivery-attempts", response_model=DeliveryResult)
def record_delivery_attempt(attempt: DeliveryAttempt) -> DeliveryResult:
    client = InfraiClient()
    try:
        return deliver_course(attempt, send_learning_package, client)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.detail) from exc
    finally:
        client.close()

