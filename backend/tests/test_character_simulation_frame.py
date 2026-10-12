from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.gameplay.runtime_state import StateGroupDefinition
from app.population_continuity.activation_policy import resolve_participation
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection, PopulationReadSet
from app.population_continuity.simulation_contracts import ModuleDefinition, ParticipationPolicy
from app.population_continuity.simulation_frame import build_simulation_frame


def module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        module_ref="needs", definition_version="1", category="needs", input_selectors=("needs.fatigue",),
        state_schema=StateGroupDefinition(
            group_id="needs", definition_version="1", projection_schema_version=1,
            shared_fields=("fatigue", "tags"), population_allowed_fields=("fatigue",),
        ),
        supported_tiers=("B0", "B1", "B2", "B3"), proposal_kinds=("continuity_delta",),
        aggregation_policy="none", distribution_policy="none", upgrade_triggers=(),
        capability_refs=(), protocol_refs=(), codebook_refs=(),
    )


def read_set() -> PopulationReadSet:
    cadence = PopulationCadenceInput(
        cadence_id="cadence:world:10", world_ref="world:bakery", world_mode_ref="mode:cooperative",
        world_mode_revision="1", cadence_source_ref="population:world:bakery", cadence_source_revision=2,
        window_start=9, window_end=10, base_checkpoint_ref="checkpoint:1", base_checkpoint_digest="sha256:base",
        base_revision_vector={"population:world:bakery": 2}, policy_revision="policy:1",
        selector_revision="selector:1", ruleset_revision="rules:1", deterministic_seed="31",
        catch_up_limit=1, budget=4, report_scope="public",
    )
    projection = PopulationProjection(
        ref="projection:char_a", scope="public", revision_vector={"gameplay:survival:character:char_a": 3},
        payload={"fatigue": 0.2},
    )
    return PopulationReadSet.from_inputs(cadence, (projection,))


def frame(**updates: object):
    values = dict(
        actor_ref="character:char_a", profile_ref="character:char_a", profile_revision="profile:1",
        character_revision=2, tick_cursor=9, read_set=read_set(),
        module_states={"needs": {"fatigue": 0.2, "tags": ["care"]}},
        participation=resolve_participation(policies=(ParticipationPolicy(
            policy_ref="policy:prototype", revision="1", allowed_tiers=("B1", "B3"),
            allowed_modules=("needs",), forbidden_dimensions=("private_memory",),
            upgrade_triggers=(), b0_expiry_tick=20, review_tick=30,
        ),), tick=10),
        codebook_refs=("code:care",), activation_lock_ref=None, module_definitions=(module_definition(),),
    )
    values.update(updates)
    return build_simulation_frame(**values)


def test_late_input_mutation_cannot_change_frame() -> None:
    original = {"needs": {"fatigue": 0.2, "tags": ["care"]}}
    result = frame(module_states=original)
    before = result.frame_digest
    original["needs"]["fatigue"] = 1.0
    original["needs"]["tags"].append("changed")
    assert result.module_states["needs"]["fatigue"] == 0.2
    assert result.module_states["needs"]["tags"] == ("care",)
    assert result.frame_digest == before


def test_frame_nested_values_and_source_pins_cannot_be_modified() -> None:
    result = frame()
    with pytest.raises(TypeError):
        result.module_states["needs"]["fatigue"] = 0.9
    with pytest.raises(TypeError):
        result.source_revision_vector["population:world:bakery"] = 99
    with pytest.raises(ValidationError):
        result.profile_revision = "profile:2"


def test_frame_serialization_is_isolated_and_roundtrips() -> None:
    result = frame()
    raw = json.loads(result.model_dump_json())
    raw["module_states"]["needs"]["fatigue"] = 0.9
    assert result.module_states["needs"]["fatigue"] == 0.2
    assert raw["domain_fact_refs"] == ["projection:char_a"]
    assert result.model_validate_json(result.model_dump_json()) == result


def test_module_key_order_does_not_change_frame_digest() -> None:
    assert frame().frame_digest == frame(module_states={"needs": {"tags": ["care"], "fatigue": 0.2}}).frame_digest


def test_original_read_set_is_not_frozen_or_rewritten() -> None:
    inputs = read_set()
    result = frame(read_set=inputs)
    inputs.projections[0].payload["fatigue"] = 0.7
    inputs.projections[0].revision_vector["gameplay:survival:character:char_a"] = 4
    assert result.source_revision_vector["gameplay:survival:character:char_a"] == 3
    assert result.module_states["needs"]["fatigue"] == 0.2
    with pytest.raises(ValueError, match="frame_read_set_digest_invalid"):
        frame(read_set=inputs)


def test_incompatible_source_versions_are_not_silently_merged() -> None:
    original = read_set()
    other = PopulationProjection(ref="projection:other", scope="public", revision_vector={"population:world:bakery": 99})
    inputs = PopulationReadSet.from_inputs(original.cadence, original.projections + (other,))
    with pytest.raises(ValueError, match="frame_source_revision_conflict"):
        frame(read_set=inputs)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_module_values_are_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        frame(module_states={"needs": {"fatigue": value}})


def test_undeclared_module_or_field_is_rejected() -> None:
    with pytest.raises(ValueError, match="frame_module_not_declared"):
        frame(module_states={"unregistered": {"fatigue": 0.2}})
    with pytest.raises(ValueError, match="frame_module_field_not_declared"):
        frame(module_states={"needs": {"private_memory": "hidden"}})
    with pytest.raises(ValueError, match="frame_module_not_declared"):
        frame(module_definitions=())


def test_unknown_frame_fields_and_boolean_revisions_are_rejected() -> None:
    result = frame()
    with pytest.raises(ValidationError):
        result.model_validate({**result.model_dump(), "arbitrary": True})
    with pytest.raises(ValidationError):
        frame(character_revision=True)


def test_field_permissions_default_to_individual_only() -> None:
    definition = module_definition()
    assert definition.field_policy("fatigue").individual_only
    assert not definition.field_policy("fatigue").distributable
    assert not definition.field_policy("fatigue").aggregatable


def test_frame_does_not_accept_cross_actor_identity() -> None:
    with pytest.raises(ValueError, match="frame_actor_profile_mismatch"):
        frame(profile_ref="character:char_b")


@pytest.mark.parametrize("review_tick", [9, 10])
def test_frame_cannot_reuse_resolution_after_review_deadline(review_tick: int) -> None:
    participation = resolve_participation(policies=(ParticipationPolicy(
        policy_ref="policy:prototype", revision="1", allowed_tiers=("B1",),
        allowed_modules=("needs",), b0_expiry_tick=20, review_tick=review_tick,
    ),), tick=8)
    with pytest.raises(ValueError, match="frame_participation_stale"):
        frame(participation=participation)


def test_frame_cannot_reuse_b0_permission_after_expiry() -> None:
    participation = resolve_participation(policies=(ParticipationPolicy(
        policy_ref="policy:prototype", revision="1", allowed_tiers=("B0", "B1"),
        allowed_modules=("needs",), b0_expiry_tick=10, review_tick=30,
    ),), tick=9)
    with pytest.raises(ValueError, match="frame_participation_stale"):
        frame(participation=participation)


def test_expired_b0_does_not_block_a_newly_resolved_higher_tier() -> None:
    participation = resolve_participation(policies=(ParticipationPolicy(
        policy_ref="policy:prototype", revision="1", allowed_tiers=("B0", "B1"),
        allowed_modules=("needs",), b0_expiry_tick=10, review_tick=30,
    ),), tick=10)
    assert frame(participation=participation).participation_resolution.allowed_tiers == ("B1",)
