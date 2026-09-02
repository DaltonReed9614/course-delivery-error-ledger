from datetime import datetime, timezone

from edtech_errors.course_delivery import DeliveryAttempt, deliver_course


class RecordingInfrai:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, str]] = []

    def capture(self, payload: dict, idempotency_key: str) -> dict:
        self.calls.append((payload, idempotency_key))
        return {"event_id": "evt-course-17", "error_group_id": "grp-delivery"}


def attempt(learner_id: str) -> DeliveryAttempt:
    return DeliveryAttempt(
        course_id="course-ledger-101",
        learner_id=learner_id,
        delivery_stage="content-package",
        deadline_at=datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc),
        educator_report_id="report-2026-fall",
    )


def test_failures_group_by_course_and_stage_while_context_keeps_learner() -> None:
    infrai = RecordingInfrai()

    def reject_delivery(_: DeliveryAttempt) -> None:
        raise ValueError("checksum mismatch")

    first = deliver_course(attempt("learner-17"), reject_delivery, infrai)  # type: ignore[arg-type]
    second = deliver_course(attempt("learner-42"), reject_delivery, infrai)  # type: ignore[arg-type]

    first_payload, first_key = infrai.calls[0]
    second_payload, second_key = infrai.calls[1]
    assert first.status == second.status == "captured"
    assert first_payload["fingerprint"] == second_payload["fingerprint"] == [
        "course-delivery",
        "course-ledger-101",
        "content-package",
    ]
    assert first_payload["context"]["learner_id"] == "learner-17"
    assert second_payload["context"]["learner_id"] == "learner-42"
    assert first_key != second_key

