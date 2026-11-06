from __future__ import annotations

import pytest

from app.population_continuity.decision_surface import (
    PopulationCapabilityCatalog,
    PopulationCapabilityDescriptor,
)


def _descriptor(**updates: object) -> PopulationCapabilityDescriptor:
    values: dict[str, object] = {
        "capability_id": "population:test:v1",
        "accepted_behavior_kinds": ("schedule_gated_supply",),
        "target_owner": "actor_gameplay.organization_domain",
        "allowed_output_kinds": ("owner_bound_intent",),
        "capability_revision": "population:test:v1",
        "policy_revision": "policy:v1",
        "enabled": True,
        "owner_contract_ref": "inf:weather-front-organization-supply@1",
    }
    values.update(updates)
    return PopulationCapabilityDescriptor(**values)


def test_whole_catalog_owner_contracts_validate() -> None:
    # Composition-time check: every registered owner-bound capability resolves.
    PopulationCapabilityCatalog.validate_owner_contracts()


def test_missing_owner_contract_ref_is_rejected_loudly() -> None:
    descriptor = _descriptor(owner_contract_ref=None)

    with pytest.raises(ValueError, match="owner_contract_missing"):
        descriptor.require_owner_contract()
    assert descriptor.validate_owner_contract() is False


def test_unknown_owner_contract_ref_is_rejected_loudly() -> None:
    descriptor = _descriptor(owner_contract_ref="inf:does-not-exist@1")

    with pytest.raises(ValueError, match="owner_contract_unknown"):
        descriptor.require_owner_contract()
    assert descriptor.validate_owner_contract() is False


def test_owner_contract_ref_pointing_at_the_wrong_owner_is_rejected() -> None:
    descriptor = _descriptor(target_owner="character_core")

    with pytest.raises(ValueError, match="owner_contract_mismatch"):
        descriptor.require_owner_contract()
    assert descriptor.validate_owner_contract() is False


def test_descriptor_without_owner_bound_output_needs_no_contract() -> None:
    descriptor = _descriptor(
        allowed_output_kinds=("presentation_seed",),
        owner_contract_ref=None,
    )

    descriptor.require_owner_contract()
    assert descriptor.validate_owner_contract() is True


def test_registered_ownerless_capabilities_are_explicitly_ownerless() -> None:
    # routine-presentation / activation-candidate / tax-pressure settle no owner
    # fact and therefore carry no contract ref on purpose.
    ownerless = [
        item
        for item in PopulationCapabilityCatalog.default("policy:v1")
        if "owner_bound_intent" not in item.allowed_output_kinds
    ]

    assert ownerless
    assert all(item.owner_contract_ref is None for item in ownerless)


def test_fixture_only_capability_declares_its_lack_of_production_source() -> None:
    by_kind = {
        kind: descriptor
        for descriptor in PopulationCapabilityCatalog.default("policy:v1")
        for kind in descriptor.accepted_behavior_kinds
    }

    # relationship_negotiation has no committed owner event producer; the
    # catalog must not present it as production-drivable.
    assert by_kind["relationship_negotiation"].production_source == "fixture_only"
    assert by_kind["routine_work"].production_source == "baseline_projection"
    assert by_kind["schedule_gated_supply"].production_source == "owner_event"

