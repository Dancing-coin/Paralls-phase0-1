from __future__ import annotations

import json

from app.population_continuity.decision_surface import PopulationCapabilityCatalog, PopulationDecisionPlanner, PopulationDecisionPolicy
from app.population_continuity.domain_projection_sources import tax_pressure_population_projections
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationReadSet
from app.services.siming_population_capability import PopulationSimulationCapability


def _read_set() -> PopulationReadSet:
    projections = tax_pressure_population_projections(
        tax_obligation_projection={
            "obligation_ref": "obligation:economy:tax:organization:bakery-a:period:2026-08",
            "actor_ref": "character:bakery-steward",
            "source_stream_ref": "gameplay:economy",
            "source_revision_pin": 2,
            "status": "due",
            "assessed_amount_minor": 27,
            "payer_account_id": "account:bakery-a:tax",
            "authority_only_evidence_refs": ("evidence:taxable:2026-08",),
            "private_source_digest": "sha256:tax-source",
        },
        scope="public",
    )
    cadence = PopulationCadenceInput(
        cadence_id="cadence:tax:W0",
        world_ref="world:bakery",
        world_mode_ref="mode:bakery",
        world_mode_revision="mode:bakery:v1",
        cadence_source_ref="gameplay:economy",
        cadence_source_revision=2,
        window_start=0,
        window_end=1,
        base_checkpoint_ref="checkpoint:tax:1",
        base_checkpoint_digest="sha256:tax-checkpoint",
        base_revision_vector={"gameplay:economy": 2},
        policy_revision="policy:tax:v1",
        selector_revision="selector:tax:v1",
        ruleset_revision="rules:tax:v1",
        deterministic_seed="seed:tax:W0",
        catch_up_limit=1,
        budget=1,
        report_scope="public",
    )
    return PopulationReadSet.from_inputs(cadence, projections)


def _policy() -> PopulationDecisionPolicy:
    return PopulationDecisionPolicy(
        policy_revision="policy:tax:v1",
        default_fidelity_tier="B0",
        budget=1,
        max_candidates=1,
    )


def test_tax_obligation_projection_becomes_redacted_pressure_candidate() -> None:
    read_set = _read_set()
    candidates = PopulationDecisionPlanner().evaluate(
        read_set,
        PopulationCapabilityCatalog.default("policy:tax:v1"),
        _policy(),
    )

    assert len(candidates) == 1
    assert candidates[0].capability_id == "population:tax-pressure:v1"
    assert candidates[0].behavior_kind == "tax_pressure"
    assert candidates[0].allowed_outputs == ("presentation_seed", "activation_candidate", "defer")


def test_tax_amount_and_authority_only_evidence_never_enter_population_read_set() -> None:
    read_set = _read_set()
    serialized = json.dumps(read_set.model_dump(mode="json"), sort_keys=True)

    assert "assessed_amount_minor" not in serialized
    assert "payer_account_id" not in serialized
    assert "authority_only_evidence_refs" not in serialized
    assert "private_source_digest" not in serialized
    assert "evidence:taxable:2026-08" not in serialized
    assert "account:bakery-a:tax" not in serialized


def test_tax_pressure_cannot_produce_owner_bound_intent() -> None:
    read_set = _read_set()
    descriptor = next(
        item
        for item in PopulationCapabilityCatalog.default("policy:tax:v1")
        if item.capability_id == "population:tax-pressure:v1"
    )

    assert descriptor.target_owner == "character_core"
    assert descriptor.owner_contract_ref is None
    assert "owner_bound_intent" not in descriptor.allowed_output_kinds
    assert descriptor.validate_owner_contract()
    result = PopulationSimulationCapability().run_default_decision_cycle(read_set.cadence, read_set)
    assert result.report.owner_bound_intents == ()
