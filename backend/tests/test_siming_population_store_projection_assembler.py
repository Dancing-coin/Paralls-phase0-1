from __future__ import annotations

from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.siming_contracts import PopulationCadenceInput
from app.population_continuity.store_projection_assembler import (
    assemble_committed_population_projections,
)


def _commit(
    store: GameplayEventStore,
    *,
    event_id: str,
    event_type: str,
    stream_id: str,
    payload: dict[str, Any],
    visibility_policy: str = "project",
) -> None:
    batch = build_atomic_event_batch(
        command_id=f"command:{event_id}",
        principal_ref="test:assembler",
        stream_id=stream_id,
        expected_revision=store.get_stream_head(stream_id),
        event_specs=((event_type, {**payload, "visibility_policy": visibility_policy}),),
        idempotency_key=f"idempotency:{event_id}",
        causation_id=f"causation:{event_id}",
        correlation_id="correlation:assembler",
        read_stream_revisions={stream_id: store.get_stream_head(stream_id)},
    )
    batch = batch.model_copy(
        update={"events": [event.model_copy(update={"visibility_policy": visibility_policy}) for event in batch.events]},
        deep=True,
    )
    result = store.append_batch(batch)
    assert result.committed


def _cadence(*, scope: str, revision_vector: dict[str, int]) -> PopulationCadenceInput:
    source_ref, source_revision = next(iter(revision_vector.items()))
    return PopulationCadenceInput(
        cadence_id="cadence:assembler:1",
        world_ref="world:bakery",
        world_mode_ref="mode:bakery",
        world_mode_revision="mode:bakery:v1",
        cadence_source_ref=source_ref,
        cadence_source_revision=source_revision,
        window_start=0,
        window_end=1,
        base_checkpoint_ref="checkpoint:assembler:1",
        base_checkpoint_digest="sha256:assembler",
        base_revision_vector=revision_vector,
        policy_revision="policy:population:v1",
        selector_revision="selector:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed="seed:assembler:1",
        catch_up_limit=1,
        budget=8,
        report_scope=scope,
    )


def _organization_projection(*, revision: int = 2, scope: str = "organization:summary") -> dict[str, object]:
    return {
        "scope": scope,
        "organization_ref": "org:bakery",
        "source_revision_vector": {"gameplay:organization:org:bakery": revision},
        "schedule_event_id": "event:schedule:1",
        "schedule_event_revision": revision,
        "schedule": {
            "recipient_ref": "character:worker",
            "assignment_ref": "assignment:1",
            "work_order_ref": "work-order:1",
        },
    }


def test_assembler_emits_production_candidate_only_from_committed_evidence() -> None:
    store = GameplayEventStore()
    organization_stream = "gameplay:organization:org:bakery"
    evidence_stream = "gameplay:construction_production:facility:oven"
    _commit(store, event_id="event:org:1", event_type="gameplay.organization.schedule_recorded", stream_id=organization_stream, payload={})
    _commit(store, event_id="event:org:2", event_type="gameplay.organization.schedule_recorded", stream_id=organization_stream, payload={})
    _commit(
        store,
        event_id="event:evidence:1",
        event_type="gameplay.construction_production.work_completion_evidence_recorded",
        stream_id=evidence_stream,
        payload={
            "committed": True,
            "evidence_kind": "production-completed",
            "outcome": "completed",
            "verification_state": "verified",
            "actor_ref": "character:worker",
            "assignment_ref": "assignment:1",
            "work_order_ref": "work-order:1",
            "observed_at": "2026-09-10T12:00:00Z",
        },
    )
    cadence = _cadence(scope="organization:summary", revision_vector={evidence_stream: 1, organization_stream: 2})
    projections = assemble_committed_population_projections(
        store=store, cadence=cadence, organization_projection=_organization_projection()
    )
    assert [item.payload["candidate_kind"] for item in projections] == [
        "organization_production_work_contribution"
    ]


def test_assembler_rejects_private_evidence_and_stale_schedule_vector() -> None:
    store = GameplayEventStore()
    evidence_stream = "gameplay:construction_production:facility:oven"
    _commit(
        store,
        event_id="event:evidence:private",
        event_type="gameplay.construction_production.work_completion_evidence_recorded",
        stream_id=evidence_stream,
        visibility_policy="actor:character:worker",
        payload={
            "committed": True,
            "evidence_kind": "production-completed",
            "outcome": "completed",
            "verification_state": "verified",
            "actor_ref": "character:worker",
            "assignment_ref": "assignment:1",
            "work_order_ref": "work-order:1",
            "observed_at": "2026-09-10T12:00:00Z",
        },
    )
    cadence = _cadence(scope="organization:summary", revision_vector={evidence_stream: 1})
    assert assemble_committed_population_projections(
        store=store,
        cadence=cadence,
        organization_projection=_organization_projection(revision=1),
    ) == ()


def test_assembler_emits_inventory_only_from_project_visible_certification() -> None:
    store = GameplayEventStore()
    stream = "gameplay:construction_production:facility:oven"
    _commit(
        store,
        event_id="event:certification:1",
        event_type="gameplay.construction_production.production_output_certified@1",
        stream_id=stream,
        payload={
            "family_ref": "production_output_certification@1",
            "quantity": 2,
            "actor_ref": "character:worker",
        },
        visibility_policy="project",
    )
    cadence = _cadence(scope="public", revision_vector={stream: 1})
    projections = assemble_committed_population_projections(
        store=store, cadence=cadence, organization_projection={"scope": "public"}
    )
    assert "inventory_output_custody" in {item.payload["candidate_kind"] for item in projections}


def test_assembler_emits_public_social_but_not_private_relationships() -> None:
    store = GameplayEventStore()
    stream = "gameplay:social:population:signal:riverward"
    private_stream = "gameplay:social:population:signal:private"
    _commit(
        store,
        event_id="event:social:public",
        event_type="gameplay.social.population_signal_recorded@1",
        stream_id=stream,
        payload={
            "signal_ref": "signal:riverward-workforce@1",
            "provenance_ref": "provenance:population-signal@1",
            "source_revision_pin": 1,
            "source_stream_ref": stream,
            "materialization_state": "proposed",
            "visibility_scope": "public",
        },
        visibility_policy="public",
    )
    _commit(
        store,
        event_id="event:social:private",
        event_type="gameplay.social.population_signal_recorded@1",
        stream_id=private_stream,
        payload={
            "signal_ref": "signal:private@1",
            "provenance_ref": "provenance:private@1",
            "source_revision_pin": 2,
            "source_stream_ref": private_stream,
            "materialization_state": "proposed",
            "visibility_scope": "actor_private",
            "relationship_ref": "relationship:private",
        },
        visibility_policy="actor:self",
    )
    cadence = _cadence(scope="public", revision_vector={stream: 1})
    projections = assemble_committed_population_projections(
        store=store, cadence=cadence, organization_projection={"scope": "public"}
    )
    assert all(item.scope != "actor:self" for item in projections)
    assert "social_population_signal" in {item.payload["candidate_kind"] for item in projections}
    assert len(projections) == 1


def test_assembler_redacts_tax_before_creating_pressure_candidate() -> None:
    store = GameplayEventStore()
    stream = "gameplay:economy"
    _commit(
        store,
        event_id="event:tax:due",
        event_type="gameplay.economy.tax_obligation_recorded@1",
        stream_id=stream,
        payload={
            "obligation_ref": "obligation:economy:tax:org:bakery:period:2026-09",
            "actor_ref": "character:steward",
            "source_revision_pin": 1,
            "status": "due",
            "amount_minor": 27,
            "payer_account_id": "account:private",
            "authority_only_evidence_refs": ("evidence:private",),
        },
        visibility_policy="public",
    )
    cadence = _cadence(scope="public", revision_vector={stream: 1})
    projections = assemble_committed_population_projections(
        store=store, cadence=cadence, organization_projection={"scope": "public"}
    )
    tax = next(item for item in projections if item.payload["candidate_kind"] == "tax_pressure")
    assert "amount_minor" not in tax.payload
    assert "payer_account_id" not in tax.payload
