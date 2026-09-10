from __future__ import annotations

from types import SimpleNamespace

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from app.gameplay.patch_runtime import GameplayPatchRegistry
from app.population_continuity.domain_projection_sources import (
    social_population_signal_population_projections,
)
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationReadSet,
)
from app.population_continuity.social_owner_adapter import SocialPopulationSignalOwnerExecutor
from app.services.siming_population_capability import PopulationSimulationCapability

from test_organization_government_social_descriptor_binding import _manifest


def _authority() -> tuple[GameplayEventStore, SocialFactAuthority]:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(_manifest(family_ref="population_signal_materialization@1"))
    registry.activate(("package:population-materialization:v1",))
    store = GameplayEventStore()
    authority = SocialFactAuthority(
        registry=SimpleNamespace(
            registry_ref="registry:test",
            registry_revision="registry:test@1",
            registry_digest="sha256:" + "f" * 64,
        ),
        store=store,
        package_registry=registry,
    )
    return store, authority


def _read_set(*, private: bool = False) -> PopulationReadSet:
    scope = "actor:self" if private else "public"
    source = {
        "signal_ref": "signal:riverward-workforce@1",
        "provenance_ref": "provenance:population-signal@1",
        "source_revision_pin": 3,
        "source_stream_ref": "gameplay:population:signal-source",
        "materialization_state": "proposed",
        "visibility_scope": "actor_private" if private else "public",
    }
    projections = social_population_signal_population_projections(
        population_signal_projection=source,
        scope=scope,
    )
    cadence = PopulationCadenceInput(
        cadence_id="cadence:social:W0",
        world_ref="world:riverward",
        world_mode_ref="mode:riverward",
        world_mode_revision="mode:riverward:v1",
        cadence_source_ref="gameplay:population:signal-source",
        cadence_source_revision=3,
        window_start=0,
        window_end=1,
        base_checkpoint_ref="checkpoint:social:1",
        base_checkpoint_digest="sha256:social-checkpoint",
        base_revision_vector={"gameplay:population:signal-source": 3},
        policy_revision="policy:social:v1",
        selector_revision="selector:social:v1",
        ruleset_revision="rules:social:v1",
        deterministic_seed="seed:social:W0",
        catch_up_limit=1,
        budget=1,
        report_scope=scope,
    )
    return PopulationReadSet.from_inputs(cadence, projections)


def test_public_signal_can_be_selected_and_settled_by_social_owner() -> None:
    store, authority = _authority()
    read_set = _read_set()
    result = PopulationSimulationCapability(
        owner_executors={
            "population:social-population-signal:v1": SocialPopulationSignalOwnerExecutor(
                authority=authority
            )
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)

    assert result.status == "accepted"
    assert result.owner_receipts[0].owner_ref == "authority:p5:social"
    assert result.owner_receipts[0].event_family == "gameplay.social.population_signal_recorded@1"
    assert store.get_stream_head("gameplay:social:population:signal:riverward-workforce@1") == 1


def test_private_relationship_projection_is_rejected_before_planning() -> None:
    assert _read_set(private=True).projections == ()


def test_social_owner_receipt_is_replayable_without_duplicate_write() -> None:
    _, authority = _authority()
    read_set = _read_set()
    capability = PopulationSimulationCapability(
        owner_executors={
            "population:social-population-signal:v1": SocialPopulationSignalOwnerExecutor(
                authority=authority
            )
        }
    )

    first = capability.run_default_decision_cycle(read_set.cadence, read_set)
    replay = capability.run_default_decision_cycle(read_set.cadence, read_set)

    assert first.owner_receipts[0].committed
    assert replay.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert replay.owner_receipts[0].zero_write


def test_social_owner_rejects_changed_provenance_on_duplicate_signal() -> None:
    store, authority = _authority()
    read_set = _read_set()
    capability = PopulationSimulationCapability(owner_executors={
        "population:social-population-signal:v1": SocialPopulationSignalOwnerExecutor(
            authority=authority
        )
    })
    first = capability.run_default_decision_cycle(read_set.cadence, read_set)
    projection = read_set.projections[0]
    changed = projection.model_copy(update={"payload": {
        **projection.payload, "provenance_ref": "provenance:different-signal@1",
    }})
    replay = capability.run_default_decision_cycle(
        read_set.cadence, PopulationReadSet.from_inputs(read_set.cadence, (changed,)),
    )

    assert first.owner_receipts[0].committed
    assert replay.status == "requeue"
    assert not replay.owner_receipts[0].committed
    assert replay.owner_receipts[0].zero_write
    assert replay.production_append_count == 0
    events = store.read_stream("gameplay:social:population:signal:riverward-workforce@1")
    assert len(events) == 1
    assert events[0].payload["provenance_ref"] == projection.payload["provenance_ref"]


def test_production_runtime_registers_social_population_owner_adapter() -> None:
    import app.main as main

    main.reset_runtime_state()
    executors = main.siming_event_pipeline._runtime._population_capability._owner_executors
    assert "population:social-population-signal:v1" in executors
