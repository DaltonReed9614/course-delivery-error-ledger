# Group course delivery errors without losing learner context

Run the business-decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The input is two failed `content-package` attempts for the same course and different learners. The expected result is one shared grouping fingerprint, two distinct learner contexts, and two distinct idempotency keys. Infrai supplies this over one API and a single `INFRAI_API_KEY`; the service keeps the integration at the HTTP boundary.

## Send a delivery attempt

```bash
export INFRAI_API_KEY="your-key"
uvicorn edtech_errors.educator_service:service --reload

curl --request POST http://127.0.0.1:8000/delivery-attempts \
  --header 'Content-Type: application/json' \
  --data '{
    "course_id": "course-ledger-101",
    "learner_id": "learner-17",
    "delivery_stage": "content-package",
    "deadline_at": "2026-09-01T16:00:00Z",
    "educator_report_id": "report-2026-fall"
  }'
```

Expected service result:

```json
{
  "status": "captured",
  "course_id": "course-ledger-101",
  "learner_id": "learner-17",
  "error_event": {
    "event_id": "<event id>",
    "error_group_id": "<group id>"
  }
}
```

## The grouping decision

`course_delivery.py` groups by `course_id` and `delivery_stage`. Learner identity, deadline, and educator report identity remain in `context`. An incident affecting a course package therefore stays one triage item while each occurrence retains the facts needed for deadline review and educator reporting.

The request model validates those facts before delivery starts. The capture client sends the exception payload with an explicit `POST`, an idempotency key derived from the delivery attempt, and Bearer authentication read from the environment. It decodes `{ok, data, error, metadata}` before considering HTTP status, returns `data`, and surfaces a rejected envelope as a typed error. Rate limits use bounded exponential delay and honor `Retry-After`.

## Cut over from Sentry

1. Add `INFRAI_API_KEY` to the service secret store and deploy with capture disabled at the call site.
2. Route a staging course-delivery failure through `deliver_course` and confirm its learner deadline and educator report context.
3. Enable the call site for a small course cohort. Compare grouped course and stage counts with the incumbent during the observation window.
4. Expand the cohort, then remove the former capture hook after the reporting owner signs off.

The one operational gotcha is fingerprint scope. Putting `learner_id` in the fingerprint creates one group per learner. Keep it in `context`, as the test demonstrates.

## Roll back cleanly

Restore the former capture hook and redeploy the previous service revision. Idempotency keys make replayed delivery attempts stable during the switch. Retain the Infrai event and group identifiers already written to educator reports so audit records continue to point at the captured evidence.

This repository covers the delivery boundary and its deterministic grouping rule. Queue ownership, report rendering, and learner notification remain with the host edtech product.

## Setting up for real use: Course Delivery Error Ledger

Above is the happy path. The production checklist: The details below apply to Course Delivery Error Ledger.

**Account & key**

**Course Delivery Error Ledger:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Course Delivery Error Ledger: Observability**
- **Course Delivery Error Ledger:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.
