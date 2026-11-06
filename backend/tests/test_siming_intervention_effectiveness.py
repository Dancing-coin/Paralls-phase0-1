from __future__ import annotations

from app.models.siming_event import (
    AuditStatus,
    InterventionEffectiveness,
    SimingAuditRecord,
)
from app.services.siming_audit_writer import SimingAuditWriter


def _audit(**updates: object) -> SimingAuditRecord:
    values: dict[str, object] = {
        "audit_id": "audit:1",
        "room_id": "room:1",
        "correlation_id": "corr:1",
        "causation_id": "cause:1",
        "source_event_id": "event:1",
        "status": "recorded",
        "reason": "intervention dispatched",
    }
    values.update(updates)
    return SimingAuditRecord(**values)


def test_effectiveness_is_a_first_class_audit_field() -> None:
    record = _audit()

    # Dispatch happened, effect unknown: the two answers stay separate.
    assert record.status == "recorded"
    assert record.effectiveness is None


def test_effectiveness_can_be_recorded_after_dispatch() -> None:
    writer = SimingAuditWriter()
    writer.record(_audit())

    updated = writer.observe_effect("audit:1", "partially_effective")

    assert updated is not None
    assert updated.effectiveness == "partially_effective"
    # The dispatch outcome must not be rewritten by an effect observation.
    assert updated.status == "recorded"


def test_observed_effect_is_readable_from_the_writer() -> None:
    writer = SimingAuditWriter()
    writer.record(_audit())
    writer.observe_effect("audit:1", "ineffective")

    record = writer.get_record("audit:1")

    assert record is not None
    assert record.effectiveness == "ineffective"


def test_unknown_audit_id_returns_none_instead_of_creating_a_record() -> None:
    writer = SimingAuditWriter()

    assert writer.observe_effect("audit:missing", "effective") is None
    assert writer.get_record("audit:missing") is None


def test_effectiveness_values_are_closed() -> None:
    allowed = set(InterventionEffectiveness.__args__)

    assert allowed == {
        "effective",
        "partially_effective",
        "ineffective",
        "harmful",
        "rolled_back",
    }


def test_effectiveness_values_are_valid_audit_statuses() -> None:
    # An effect must be expressible as an audit status too, so a single record can
    # report it without inventing a parallel vocabulary.
    allowed = set(AuditStatus.__args__)

    assert set(InterventionEffectiveness.__args__) <= allowed


def test_sqlite_writer_persists_observed_effect(tmp_path) -> None:
    from app.services.siming_audit_writer import SqliteSimingAuditWriter

    writer = SqliteSimingAuditWriter(tmp_path / "audit.db")
    try:
        writer.record(_audit())
        writer.observe_effect("audit:1", "effective")

        record = writer.get_record("audit:1")
        assert record is not None
        assert record.effectiveness == "effective"
        assert record.status == "recorded"
    finally:
        writer.close()
