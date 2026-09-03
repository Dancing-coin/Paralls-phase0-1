import pytest

from app.services.harness_failure_adapters import adapt_failure, failure_kind


@pytest.mark.parametrize(
    ("boundary", "code", "expected"),
    [
        ("esm", "distance_constraint", "constraint_conflict"),
        ("esm", "unsupported_change_type", "invalid_input"),
        ("gameplay", "stream_revision_conflict", "stale_revision"),
        ("gameplay", "projection_not_ready", "dependency_missing"),
        ("embodied", "append_batch_failed", "transient"),
        ("transport", "queue_full", "delivery_failed"),
        ("transport", "session_scope_denied", "permission_denied"),
        ("unknown", "unknown", "unknown"),
    ],
)
def test_native_failure_maps_to_common_disposition(boundary: str, code: str, expected: str) -> None:
    disposition = adapt_failure(boundary, code)
    assert failure_kind(boundary, code) == expected
    assert disposition.kind == expected
