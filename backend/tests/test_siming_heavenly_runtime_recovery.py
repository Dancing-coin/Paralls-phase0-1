import pytest

import app.config as config_module
import app.main as main
from app.models.authority_event import (
    AuthorityEvent,
    AuthorityEventRouting,
    AuthorityEventSource,
)
from app.models.siming_heavenly_memory import InterventionOutcomeMemoryEntry
from app.models.siming_heavenly_graph import GraphProvenance, GraphValidity
from app.models.siming_event import SimingInput
from app.services.authority_event_bus import AuthorityRecoveryLedger


def _event(event_type: str) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=f"event:{event_type}",
        event_type=event_type,
        producer_ts=100,
        room_id="room:main",
        scene_id="scene:throne",
        zone_id="zone:archive",
        source=AuthorityEventSource(layer="L1", system="test"),
        routing=AuthorityEventRouting(
            audience_mode="broadcast", routing_mode="event_type"
        ),
        priority="p2",
        durability="replayable",
        causation_id="cause:destroy:1",
        correlation_id="corr:destroy:1",
        payload={
            "target_ref": "obj_letter",
            "current_state": "removed_from_surface",
        },
    )


@pytest.mark.parametrize(
    ("state", "expected_dispatch_record"),
    [
        ("unsent", False),
        ("sent_unconfirmed", False),
        ("authority_confirmed", True),
    ],
)
def test_dispatch_ledger_survives_sqlite_restart(
    tmp_path, state: str, expected_dispatch_record: bool
) -> None:
    settings = config_module.Settings(
        siming_heavenly_mode="active",
        heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
    )
    destruction = _event("world_fact_event")
    first_state = main.build_runtime_state(settings)
    try:
        support = first_state.siming_runtime.heavenly_support
        prepared = support.prepare(
            SimingInput(input_type="world_fact_event", source_event=destruction)
        )
        support.record_selection(prepared, "runtime:bridge:proposal:destroy:1")
        if state == "sent_unconfirmed":
            support._record_dispatch_state(
                scope=support._scope_for(destruction),
                recorded_at=destruction.producer_ts,
                correlation_id=destruction.correlation_id,
                dispatch_event_id="siming:dispatch:destroy:1",
                state="sent_unconfirmed",
            )
        if state == "authority_confirmed":
            support.record_dispatch(
                correlation_id=destruction.correlation_id,
                dispatch_event_id="siming:dispatch:destroy:1",
            )
    finally:
        first_state.close()

    second_state = main.build_runtime_state(settings)
    try:
        support = second_state.siming_runtime.heavenly_support
        assert (
            support.has_dispatch(_event("siming_staging_ack"))
            is expected_dispatch_record
        )
    finally:
        second_state.close()


def test_unconfirmed_dispatch_confirms_only_when_authority_ledger_has_its_event(
    tmp_path,
) -> None:
    settings = config_module.Settings(
        siming_heavenly_mode="active",
        heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
    )
    destruction = _event("world_fact_event")
    state = main.build_runtime_state(settings)
    try:
        support = state.siming_runtime.heavenly_support
        support._record_dispatch_state(
            scope=support._scope_for(destruction),
            recorded_at=destruction.producer_ts,
            correlation_id=destruction.correlation_id,
            dispatch_event_id="siming:dispatch:destroy:1",
            state="sent_unconfirmed",
        )

        assert support.has_dispatch(destruction) is False
        assert support.reconcile_dispatch(
            destruction,
            authority_ledger=AuthorityRecoveryLedger(
                event_ids=frozenset({"siming:dispatch:destroy:1"}),
                is_complete_across_restart=False,
            ),
        ) == "authority_confirmed"
        assert support.has_dispatch(destruction) is True
    finally:
        state.close()


def test_unconfirmed_dispatch_stays_nonterminal_without_a_complete_authority_ledger(
    tmp_path,
) -> None:
    settings = config_module.Settings(
        siming_heavenly_mode="active",
        heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
    )
    destruction = _event("world_fact_event")
    state = main.build_runtime_state(settings)
    try:
        support = state.siming_runtime.heavenly_support
        support._record_dispatch_state(
            scope=support._scope_for(destruction),
            recorded_at=destruction.producer_ts,
            correlation_id=destruction.correlation_id,
            dispatch_event_id="siming:dispatch:destroy:1",
            state="sent_unconfirmed",
        )

        assert support.reconcile_dispatch(
            destruction,
            authority_ledger=None,
        ) == "authority_unknown"
        assert support.has_dispatch(destruction) is False
        assert support.reconcile_dispatch(
            destruction,
            authority_ledger=AuthorityRecoveryLedger(
                event_ids=frozenset(),
                is_complete_across_restart=False,
            ),
        ) == "authority_unknown"
        assert support.has_dispatch(destruction) is False
        assert support.reconcile_dispatch(
            destruction,
            authority_ledger=AuthorityRecoveryLedger(
                event_ids=frozenset(),
                is_complete_across_restart=True,
            ),
        ) == "authority_absent"
        assert support.has_dispatch(destruction) is False
    finally:
        state.close()


def test_legacy_dispatch_record_is_treated_as_authority_confirmed(tmp_path) -> None:
    settings = config_module.Settings(
        siming_heavenly_mode="active",
        heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
    )
    destruction = _event("world_fact_event")
    state = main.build_runtime_state(settings)
    try:
        support = state.siming_runtime.heavenly_support
        scope = support._scope_for(destruction)
        entry_id = "heavenly_dispatch:corr:destroy:1:siming:dispatch:destroy:1"
        support._memory.write_entry(
            scope=scope,
            entry=InterventionOutcomeMemoryEntry(
                entry_id=entry_id,
                stage="dispatch",
                correlation_id=destruction.correlation_id,
                authority_result_ref="siming:dispatch:destroy:1",
            ),
            validity=GraphValidity(valid_from=destruction.producer_ts),
            recorded_at=destruction.producer_ts,
            revision=1,
            supersedes_revision=None,
            provenance=GraphProvenance(
                source_kind="siming_projection",
                source_ref=entry_id,
                causation_id=destruction.correlation_id,
                correlation_id=destruction.correlation_id,
                producer_system="legacy_siming_runtime",
            ),
            transaction_id=entry_id,
            idempotency_key=entry_id,
        )

        assert support.has_dispatch(destruction) is True
        assert support.reconcile_dispatch(
            destruction,
            authority_ledger=AuthorityRecoveryLedger(
                event_ids=frozenset(),
                is_complete_across_restart=False,
            ),
        ) == "not_pending"
    finally:
        state.close()
