from __future__ import annotations

from app.gameplay.ecology_runtime import EcologyDroughtProcessPolicy
from app.gameplay.event_store import GameplayEventStore
from test_infra_ecology_process_lifecycle import _envelope, _record


def test_drought_process_commits_existing_ecology_records_and_cursor() -> None:
    store = GameplayEventStore()
    authority = _record(store)

    result = authority.advance_drought_process(
        envelope=_envelope(command_id="command:drought", key="ecology:drought:3", expected_revision=5, tick=3),
        policy=EcologyDroughtProcessPolicy(),
        region_ref="region:process",
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()][-4:] == [
        "gameplay.ecology.environment.recorded",
        "gameplay.ecology.resource.recorded",
        "gameplay.ecology.crop.recorded",
        "gameplay.ecology.drought_process_advanced",
    ]
    projection = authority.regional_projection(scope="authority")
    assert projection["environments"]["region:process"]["moisture_basis_points"] == 2_500
    assert projection["resources"]["resource:process:water"]["quantity"] == 84
    assert projection["crops"]["crop:process:wheat"]["health"] == 85
    assert projection["drought_processes"]["region:process"]["last_tick"] == 3


def test_drought_process_rejects_stale_private_and_forged_commands_without_write() -> None:
    store = GameplayEventStore()
    authority = _record(store)
    before = len(store.read_events())

    stale = authority.advance_drought_process(
        envelope=_envelope(command_id="command:drought:stale", key="ecology:drought:stale", expected_revision=4, tick=3),
        policy=EcologyDroughtProcessPolicy(), region_ref="region:process",
    )
    private = authority.advance_drought_process(
        envelope=_envelope(command_id="command:drought:private", key="ecology:drought:private", expected_revision=5, tick=3, scope="authority_only"),
        policy=EcologyDroughtProcessPolicy(), region_ref="region:process",
    )
    forged = authority.advance_drought_process(
        envelope=_envelope(command_id="command:drought:forged", key="ecology:drought:forged", expected_revision=5, tick=3, principal="client:godot"),
        policy=EcologyDroughtProcessPolicy(), region_ref="region:process",
    )

    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert private.failure is not None and private.failure.error_code == "ecology_process_privacy_scope_denied"
    assert forged.failure is not None and forged.failure.error_code == "ecology_authority_required"
    assert len(store.read_events()) == before


def test_drought_process_replays_exact_duplicate_and_checkpoint_tail() -> None:
    store = GameplayEventStore()
    authority = _record(store)
    command = _envelope(command_id="command:drought:replay", key="ecology:drought:replay", expected_revision=5, tick=3)

    first = authority.advance_drought_process(envelope=command, policy=EcologyDroughtProcessPolicy(), region_ref="region:process")
    duplicate = authority.advance_drought_process(envelope=command, policy=EcologyDroughtProcessPolicy(), region_ref="region:process")

    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert authority.regional_replay().projection_hash == authority.regional_replay(checkpoint_at=6).projection_hash
