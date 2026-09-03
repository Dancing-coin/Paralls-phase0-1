from __future__ import annotations

from app.models.harness_execution import FailureDisposition, FailureKind, classify_failure


_BOUNDARY_CODES: dict[str, dict[str, FailureKind]] = {
    "esm": {
        "unsupported_change_type": "invalid_input",
        "distance_constraint": "constraint_conflict",
        "stale_revision": "stale_revision",
    },
    "gameplay": {
        "projection_not_ready": "dependency_missing",
        "stream_revision_conflict": "stale_revision",
        "idempotency_conflict": "constraint_conflict",
        "event_schema_unregistered": "invalid_input",
    },
    "embodied": {
        "session_exists": "constraint_conflict",
        "session_unknown": "invalid_input",
        "session_not_awaiting_responses": "constraint_conflict",
        "participant_terms_unknown": "invalid_input",
        "session_not_authorized": "constraint_conflict",
        "session_not_realizing": "constraint_conflict",
        "session_terminal": "constraint_conflict",
        "participant_unknown": "invalid_input",
        "append_batch_failed": "transient",
        "source_sequence_gap": "invalid_input",
    },
    "transport": {
        "queue_full": "delivery_failed",
        "connection_closed": "delivery_failed",
        "session_scope_denied": "permission_denied",
    },
}


def adapt_failure(boundary: str, native_code: str) -> FailureDisposition:
    kind = _BOUNDARY_CODES.get(boundary, {}).get(native_code, "unknown")
    return classify_failure(kind)


def failure_kind(boundary: str, native_code: str) -> FailureKind:
    return adapt_failure(boundary, native_code).kind


__all__ = ["adapt_failure", "failure_kind"]
