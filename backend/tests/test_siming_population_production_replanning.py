from __future__ import annotations

import pytest

from app.population_continuity.domain_projection_sources import (
    production_receipt_population_projections,
    production_work_population_projections,
)
from app.population_continuity.siming_contracts import PopulationOwnerReceipt
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationReadSet,
)
from app.services.siming_population_capability import PopulationSimulationCapability
from app.population_continuity.decision_surface import (
    PopulationCapabilityDescriptor,
    PopulationDecisionPolicy,
    PopulationDecision,
)
from app.character_agent.models.simulation_seed import CharacterContinuityReceipt
from test_siming_population_production_owner_vertical import (
    _cadence,
    _event,
    _organization_projection,
)


def _receipt_projection() -> dict[str, object]:
    return {
        "scope": "organization:summary",
        "organization_ref": "org:bakery",
        "source_revision_vector": {"gameplay:organization:org:bakery": 3},
        "acceptance_rows": ({
            "event_id": "receipt:production:1",
            "recipient_ref": "character:char_a",
            "organization_ref": "org:bakery",
            "source_evidence_event_id": "event:evidence:1",
        },),
    }


def test_production_receipt_is_the_only_source_for_next_population_projection() -> None:
    receipt = PopulationOwnerReceipt(
        receipt_ref="receipt:production:1",
        owner_ref="actor_gameplay.organization_domain",
        event_family="gameplay.organization.production_work_contribution_accepted",
        committed=True,
        revision_vector={"gameplay:organization:org:bakery": 3},
        zero_write=False,
    )

    projections = production_receipt_population_projections(
        owner_receipt=receipt,
        organization_projection=_receipt_projection(),
        scope="organization:summary",
    )

    assert len(projections) == 1
    assert projections[0].revision_vector == receipt.revision_vector
    assert projections[0].payload["source_owner_receipt_ref"] == receipt.receipt_ref


def test_production_receipt_does_not_promote_to_a_later_schedule_vector() -> None:
    receipt = PopulationOwnerReceipt(
        receipt_ref="receipt:production:1",
        owner_ref="actor_gameplay.organization_domain",
        event_family="gameplay.organization.production_work_contribution_accepted",
        committed=True,
        revision_vector={"gameplay:organization:org:bakery": 3},
        zero_write=False,
    )
    assert production_receipt_population_projections(
        owner_receipt=receipt,
        organization_projection={
            **_receipt_projection(),
            "source_revision_vector": {"gameplay:organization:org:bakery": 7},
        },
        scope="organization:summary",
    ) == ()


def test_old_receipt_cannot_drive_current_cadence() -> None:
    receipt = PopulationOwnerReceipt(
        receipt_ref="receipt:production:1",
        owner_ref="actor_gameplay.organization_domain",
        event_family="gameplay.organization.production_work_contribution_accepted",
        committed=True,
        revision_vector={"gameplay:organization:org:bakery": 3},
        zero_write=False,
    )
    cadence = PopulationCadenceInput(
        cadence_id="cadence:production:current",
        world_ref="world:bakery",
        world_mode_ref="mode:bakery",
        world_mode_revision="mode:v1",
        cadence_source_ref="gameplay:organization:org:bakery",
        cadence_source_revision=4,
        window_start=1,
        window_end=2,
        base_checkpoint_ref="checkpoint:current",
        base_checkpoint_digest="sha256:current",
        base_revision_vector={"gameplay:organization:org:bakery": 4},
        policy_revision="policy:population:v1",
        selector_revision="selector:generic:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed="seed:current",
        catch_up_limit=1,
        budget=1,
        report_scope="organization:summary",
    )
    projection = production_receipt_population_projections(
        owner_receipt=receipt,
        organization_projection=_receipt_projection(),
        scope="organization:summary",
    )[0].model_copy(update={"revision_vector": dict(cadence.base_revision_vector)})
    result = PopulationSimulationCapability().run_receipt_pinned_decision_cycle(
        cadence,
        PopulationReadSet.from_inputs(cadence, (projection,)),
        receipt,
    )

    assert result.status == "requeue"
    assert result.reason == "owner_rejected"


def test_production_receipt_requires_one_matching_organization_acceptance() -> None:
    receipt = PopulationOwnerReceipt(
        receipt_ref="receipt:production:1",
        owner_ref="actor_gameplay.organization_domain",
        event_family="gameplay.organization.production_work_contribution_accepted",
        committed=True,
        revision_vector={"gameplay:organization:org:bakery": 3},
        zero_write=False,
    )
    organization_projection = _receipt_projection()
    organization_projection["acceptance_rows"] = (
        *organization_projection["acceptance_rows"],
        dict(organization_projection["acceptance_rows"][0]),
    )

    assert production_receipt_population_projections(
        owner_receipt=receipt,
        organization_projection=organization_projection,
        scope="organization:summary",
    ) == ()


def test_rejected_production_receipt_does_not_create_next_projection() -> None:
    receipt = PopulationOwnerReceipt(
        receipt_ref="rejected:production:1",
        owner_ref="actor_gameplay.organization_domain",
        event_family="gameplay.organization.production_work_contribution_accepted",
        committed=False,
        revision_vector={},
        zero_write=True,
    )

    assert production_receipt_population_projections(
        owner_receipt=receipt,
        organization_projection=_receipt_projection(),
        scope="organization:summary",
    ) == ()


def test_production_replan_rejects_read_set_with_unrelated_projection() -> None:
    receipt = PopulationOwnerReceipt(
        receipt_ref="receipt:production:1",
        owner_ref="actor_gameplay.organization_domain",
        event_family="gameplay.organization.production_work_contribution_accepted",
        committed=True,
        revision_vector={"gameplay:organization:org:bakery": 3},
        zero_write=False,
    )
    cadence = PopulationCadenceInput(
        cadence_id="cadence:production:2", world_ref="world:bakery", world_mode_ref="mode:bakery",
        world_mode_revision="mode:v1", cadence_source_ref="gameplay:organization:org:bakery",
        cadence_source_revision=3, window_start=1, window_end=2, base_checkpoint_ref="checkpoint:2",
        base_checkpoint_digest="sha256:cp2", base_revision_vector=receipt.revision_vector,
        policy_revision="policy:population:v1", selector_revision="selector:population:v1",
        ruleset_revision="rules:population:v1", deterministic_seed="seed:2", catch_up_limit=1,
        budget=1, report_scope="organization:summary",
    )
    projection = production_receipt_population_projections(
        owner_receipt=receipt,
        organization_projection=_receipt_projection(),
        scope="organization:summary",
    )[0]
    unrelated = projection.model_copy(
        update={"ref": "projection:unrelated", "payload": {"candidate_kind": "routine_work", "actor_ref": "character:char_b"}}
    )
    read_set = PopulationReadSet.from_inputs(cadence, (projection, unrelated))
    result = PopulationSimulationCapability().replan_from_receipts(
        PopulationDecision(
            read_set_digest="sha256:previous", result_digest="sha256:previous", budget_used=0, budget_remaining=1,
        ),
        (receipt,),
        read_set,
        PopulationDecisionPolicy(
            policy_revision="policy:population:v1", default_fidelity_tier="B1", budget=1, max_candidates=1,
        ),
        (
            PopulationCapabilityDescriptor(
                capability_id="population:organization-production-work-contribution:v1",
                accepted_behavior_kinds=("organization_production_work_contribution",),
                required_scopes=("organization:summary",), required_source_domains=("production",),
                target_owner="actor_gameplay.organization_domain", allowed_output_kinds=("owner_bound_intent",),
                capability_revision="population:organization-production-work-contribution:v1",
                policy_revision="policy:population:v1", enabled=True,
            ),
        ),
    )
    assert result.status == "requeue"
    assert result.reason == "stale_read_set"


def test_production_replan_reuses_receipt_without_second_owner_write() -> None:
    class Owner:
        def __init__(self) -> None:
            self.calls = 0

        def submit(self, intent, *, read_set):
            self.calls += 1
            return PopulationOwnerReceipt(
                receipt_ref="receipt:production:1",
                owner_ref="actor_gameplay.organization_domain",
                event_family="gameplay.organization.production_work_contribution_accepted",
                committed=True,
                revision_vector={"gameplay:organization:org:bakery": 3},
                zero_write=False,
            )

    class CharacterCore:
        def __init__(self) -> None:
            self.revision = 0

        def current_revision(self, actor_ref: str) -> int:
            return self.revision

        def apply_command(self, command):
            before = self.revision
            self.revision += 1
            return CharacterContinuityReceipt(
                receipt_ref=f"continuity:{self.revision}",
                command_id=command.command_id,
                actor_ref=command.actor_ref,
                status="committed",
                character_revision_before=before,
                character_revision_after=self.revision,
                source_owner_receipt_refs=command.source_owner_receipt_refs,
            )

    owner = Owner()
    core = CharacterCore()
    capability = PopulationSimulationCapability(
        owner_executors={"population:organization-production-work-contribution:v1": owner},
        continuity_port=core,
    )
    source = production_work_population_projections(
        committed_events=(_event(),),
        organization_projection=_organization_projection(),
        scope="organization:summary",
    )[0]
    cadence = _cadence().model_copy(
        update={
            "base_revision_vector": source.revision_vector,
            "cadence_source_ref": "gameplay:construction_production:facility:oven",
            "cadence_source_revision": 1,
        }
    )
    first = capability.run_default_decision_cycle(
        cadence,
        PopulationReadSet.from_inputs(cadence, (source,)),
    )
    next_projection = production_receipt_population_projections(
        owner_receipt=first.owner_receipts[0],
        organization_projection={
            **_organization_projection(),
            "source_revision_vector": first.owner_receipts[0].revision_vector,
            "acceptance_rows": ({
                "event_id": first.owner_receipts[0].receipt_ref,
                "recipient_ref": "character:worker",
                "organization_ref": "org:bakery",
                "source_evidence_event_id": "event:evidence:1",
            },),
        },
        scope="organization:summary",
    )[0]
    next_cadence = cadence.model_copy(
        update={
            "cadence_id": "cadence:production:2",
            "cadence_source_ref": "gameplay:organization:org:bakery",
            "cadence_source_revision": 3,
            "base_revision_vector": first.owner_receipts[0].revision_vector,
            "deterministic_seed": "seed:production:2",
        }
    )
    second = capability.replan_from_receipts(
        first.decision,
        first.owner_receipts,
        PopulationReadSet.from_inputs(next_cadence, (next_projection,)),
        capability.default_decision_policy(next_cadence),
        capability.default_capabilities(next_cadence),
    )
    assert first.status == "accepted" and second.status == "accepted"
    assert owner.calls == 1
    assert core.revision == 2
    assert first.seed_candidates[0].idempotency_key != second.seed_candidates[0].idempotency_key


@pytest.mark.parametrize("entrypoint", ["default", "replan_without_receipts"])
def test_forged_projection_receipt_cannot_bypass_owner(entrypoint: str) -> None:
    class CharacterCore:
        def __init__(self) -> None:
            self.commands = []

        def current_revision(self, actor_ref: str) -> int:
            return 0

        def apply_command(self, command):
            self.commands.append(command)
            raise AssertionError("unverified Owner receipt reached Character Core")

    source = production_work_population_projections(
        committed_events=(_event(),),
        organization_projection=_organization_projection(),
        scope="organization:summary",
    )[0]
    forged = source.model_copy(update={"payload": {
        **source.payload,
        "source_owner_receipt_ref": "receipt:forged",
        "source_owner_receipt_refs": ("receipt:forged",),
    }})
    cadence = _cadence().model_copy(update={"base_revision_vector": source.revision_vector})
    read_set = PopulationReadSet.from_inputs(cadence, (forged,))
    core = CharacterCore()
    capability = PopulationSimulationCapability(continuity_port=core)
    if entrypoint == "default":
        result = capability.run_default_decision_cycle(cadence, read_set)
    else:
        result = capability.replan_from_receipts(
            PopulationDecision(
                read_set_digest="sha256:previous", result_digest="sha256:previous",
                budget_used=0, budget_remaining=1,
            ),
            (), read_set, capability.default_decision_policy(cadence),
            capability.default_capabilities(cadence),
        )
    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert result.owner_receipts == ()
    assert result.seed_candidates == ()
    assert result.continuity_receipts == ()
    assert core.commands == []


@pytest.mark.parametrize("mismatch", ["owner", "source", "revision", "projection_revision", "domain"])
def test_production_replan_requires_matching_receipt_source_and_revision(mismatch: str) -> None:
    receipt = PopulationOwnerReceipt(
        receipt_ref="receipt:production:1", owner_ref="actor_gameplay.organization_domain",
        event_family="gameplay.organization.production_work_contribution_accepted",
        committed=True, revision_vector={"gameplay:organization:org:bakery": 3}, zero_write=False,
    )
    projection = production_receipt_population_projections(
        owner_receipt=receipt, organization_projection=_receipt_projection(), scope="organization:summary",
    )[0]
    cadence = _cadence().model_copy(update={
        "base_revision_vector": receipt.revision_vector,
        "cadence_source_ref": "gameplay:organization:org:bakery", "cadence_source_revision": 3,
    })
    if mismatch == "owner":
        receipt = receipt.model_copy(update={"owner_ref": "authority:unrelated"})
    elif mismatch == "source":
        cadence = cadence.model_copy(update={"cadence_source_ref": "gameplay:organization:org:unrelated"})
    elif mismatch == "revision":
        cadence = cadence.model_copy(update={"cadence_source_revision": 2})
    elif mismatch == "projection_revision":
        projection = projection.model_copy(update={"revision_vector": {"gameplay:organization:org:bakery": 2}})
    else:
        projection = projection.model_copy(update={"payload": {**projection.payload, "source_domain": "inventory"}})
    capability = PopulationSimulationCapability()
    result = capability.replan_from_receipts(
        PopulationDecision(
            read_set_digest="sha256:previous", result_digest="sha256:previous", budget_used=0, budget_remaining=1,
        ),
        (receipt,), PopulationReadSet.from_inputs(cadence, (projection,)),
        capability.default_decision_policy(cadence), capability.default_capabilities(cadence),
    )
    assert result.status == "requeue"
    assert result.reason == "stale_read_set"
    assert result.production_append_count == 0
    assert result.seed_candidates == ()
    assert result.continuity_receipts == ()
