from __future__ import annotations

import pytest

from app.gameplay.ecology_runtime import EcologyDroughtProcessPolicy, EcologyHazardAuthority
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.ecology_temporal_consumer import EcologyTemporalConsumer
from app.world_runtime.replay_participants import (
    _ecology_temporal_participant,
    _validate_ecology_temporal_participant,
)
from test_infra_ecology_drought_state_obligation import _apply, _seed_process, STREAM
from test_infra_ecology_process_lifecycle import _envelope, _record


def _seed() -> tuple[object, EcologyHazardAuthority]:
    store, authority, source_event_id, source_event_revision = _seed_process()
    assert _apply(
        authority,
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    ).committed
    return store, authority


def _driver(tick: int):
    class World:
        @staticmethod
        def is_paused() -> bool:
            return False

    return type("Driver", (), {"current_tick": tick, "catch_up_limit": 1, "world_runtime": World()})()


def test_ecology_temporal_participant_respects_boundary_and_settlement() -> None:
    store, authority = _seed()
    before = _ecology_temporal_participant(store)
    assert before is not None
    boundary = store.get_last_global_sequence()
    _validate_ecology_temporal_participant(store, before, boundary_sequence=boundary)

    assert EcologyTemporalConsumer(store=store, authority=authority).advance(_driver(6)) is None
    _validate_ecology_temporal_participant(store, before, boundary_sequence=boundary)
    with pytest.raises(ValueError, match="event_ref|projection"):
        _validate_ecology_temporal_participant(store, before)

    after = _ecology_temporal_participant(store)
    assert after is not None
    assert {row["event_type"] for row in after["event_refs"]} >= {
        "gameplay.ecology.drought_state_obligation_opened",
        "gameplay.ecology.drought_state_expired",
        "gameplay.ecology.drought_state_obligation_settled",
    }
    _validate_ecology_temporal_participant(store, after)


def test_ecology_temporal_participant_rejects_changed_payload_digest() -> None:
    store, _authority = _seed()
    saved = _ecology_temporal_participant(store)
    assert saved is not None
    changed = {
        **saved,
        "event_refs": [dict(saved["event_refs"][0], payload_digest="sha256:changed")],
    }
    with pytest.raises(ValueError, match="event_ref"):
        _validate_ecology_temporal_participant(store, changed)


def test_ecology_temporal_participant_survives_durable_reopen(tmp_path) -> None:
    path = tmp_path / "ecology-temporal.db"
    store = DurableGameplayEventStore(path)
    try:
        authority = EcologyHazardAuthority(store=store)
        # Reuse the real owner setup against the durable store.
        # _seed_process creates its own store, so reproduce its source sequence
        # through the helper's authoritative commands on this durable store.
        _record(store)
        source = authority.advance_drought_process(
            envelope=_envelope(
                command_id="durable:ecology:drought", key="durable:ecology:drought", expected_revision=5, tick=3
            ),
            policy=EcologyDroughtProcessPolicy(),
            region_ref="region:process",
        )
        assert source.committed
        source_event = next(event for event in reversed(store.read_events())
                            if event.event_type == "gameplay.ecology.drought_process_advanced")
        assert _apply(
            authority,
            expected_revision=store.get_stream_head(STREAM),
            source_event_id=source_event.event_id,
            source_event_revision=source_event.stream_revision,
        ).committed
        saved = _ecology_temporal_participant(store)
        assert saved is not None
        store.close()
        reopened = DurableGameplayEventStore(path)
        try:
            assert _ecology_temporal_participant(reopened) == saved
            _validate_ecology_temporal_participant(reopened, saved)
        finally:
            reopened.close()
    finally:
        if not store._closed:
            store.close()
