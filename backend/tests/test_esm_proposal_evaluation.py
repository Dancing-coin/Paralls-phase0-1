import copy

import pytest

from app.models.constraint_probe import ConstraintProbe
from app.models.environment_request import EnvironmentRequest
from app.models.environment_proposal import EnvironmentProposal
from app.models.feasibility_response import FeasibilityResponse
from app.services.esm_service import ESMService


def make_esm():
    esm = ESMService()
    esm.register_environment_target("room", "scene", "zone", "env_lamp")
    return esm


def proposal(change_type="light_level_drop"):
    return EnvironmentProposal(
        proposal_id="proposal:1", candidate_ref="candidate:1", decision_ref="decision:1",
        room_id="room", scene_id="scene", zone_id="zone", target_environment_id="env_lamp",
        goal="create_opportunity", requested_change_type=change_type, requested_strength="medium",
        producer_ts=100, causation_id="cause", correlation_id="corr",
    )


def test_evaluation_is_read_only_and_estimate_is_coarse():
    esm = make_esm()
    before = esm.get_repo_local_workbench_snapshot(room_id="room", scene_id="scene", zone_id="zone")
    response = esm.evaluate_proposal(proposal())
    assert response.feasible is True
    assert response.estimated_effect["light_level"] == "low"
    assert esm.get_repo_local_workbench_snapshot(room_id="room", scene_id="scene", zone_id="zone") == before


def test_unsupported_change_is_infeasible_without_execution():
    esm = make_esm()
    response = esm.evaluate_proposal(proposal("material_change"))
    assert response.feasible is False
    assert response.constraints == ["unsupported_change_type"]
    assert esm._latest_environment_request is None


def test_evaluation_preserves_response_fields_and_isolates_mutable_values():
    esm = make_esm()
    first = esm.evaluate_proposal(proposal())
    first.estimated_effect["light_level"] = "changed"
    first.constraints.append("changed")
    first.alternative_suggestions.append({"change_type": "changed"})

    next_proposal = proposal().model_copy(update={
        "proposal_id": "proposal:2", "producer_ts": 200, "correlation_id": "corr:2",
    })
    response = esm.evaluate_proposal(next_proposal)
    expected = FeasibilityResponse(
        response_id="feasibility:proposal:2", proposal_ref="proposal:2",
        feasible=True, constraints=[],
        estimated_effect={
            "temperature": "ambient", "humidity": "stable", "light_level": "low",
            "thermal_level": "warm", "noise_level": "elevated", "smoke_density": "light",
            "visibility_level": "reduced",
        },
        producer_ts=201, causation_id="proposal:2", correlation_id="corr:2",
    )
    assert response == expected
    assert response.model_dump(exclude_unset=True) == expected.model_dump(exclude_unset=True)
    assert FeasibilityResponse.model_validate_json(response.model_dump_json()) == expected


def test_probe_reports_current_constraints_without_mutation():
    esm = make_esm()
    probe = ConstraintProbe(probe_id="probe:1", target_environment_id="env_lamp", constraint_type="all", producer_ts=100, causation_id="cause", correlation_id="corr")
    before = esm.get_repo_local_workbench_snapshot(room_id="room", scene_id="scene", zone_id="zone")
    result = esm.probe_constraints(probe, room_id="room", scene_id="scene", zone_id="zone")
    assert result.active_constraints["cooldown"]["remaining"] == 0
    assert "light_level_drop" in result.active_constraints["material"]["compatible_change_types"]
    assert result.cooldown_remaining == 0
    assert esm.get_repo_local_workbench_snapshot(room_id="room", scene_id="scene", zone_id="zone") == before


@pytest.mark.parametrize("state,code", [
    ({"cooldown_until_ts": 200}, "cooldown_active"),
    ({"compatible_change_types": []}, "material_incompatible"),
    ({"resource_available": 0, "resource_cost": 1}, "resource_insufficient"),
    ({"spatial_allowed": False}, "spatial_blocked"),
])
def test_authoritative_constraints_are_enforced_at_execution(state, code):
    esm = make_esm()
    esm.register_environment_target("room", "scene", "zone", "env_lamp", **state)
    before = copy.deepcopy(esm._environment_targets)
    p = proposal()
    assert esm.evaluate_proposal(p).feasible
    request = EnvironmentRequest(request_id="r", room_id=p.room_id, scene_id=p.scene_id, zone_id=p.zone_id,
        target_entity_refs={"environment_ids": [p.target_environment_id]}, goal=p.goal,
        requested_change_type=p.requested_change_type, producer_ts=p.producer_ts)
    result, field = esm.resolve_environment_request(request)
    assert result.constraint_code == code
    assert field is None
    assert esm._environment_targets == before


def test_unknown_target_is_detected_by_probe_and_rejected_at_execution():
    esm = make_esm()
    p = proposal().model_copy(update={"target_environment_id": "missing"})
    assert esm.evaluate_proposal(p).feasible
    probe = ConstraintProbe(probe_id="q", target_environment_id="missing", constraint_type="all",
        producer_ts=100, causation_id="cause", correlation_id="corr")
    assert esm.probe_constraints(probe, room_id="room", scene_id="scene", zone_id="zone").active_constraints == {
        "target": {"exists": False},
    }
    result, field = esm.resolve_environment_request(EnvironmentRequest(
        request_id="r", proposal_ref=p.proposal_id, room_id=p.room_id, scene_id=p.scene_id, zone_id=p.zone_id,
        target_entity_refs={"environment_ids": [p.target_environment_id]}, goal=p.goal,
        requested_change_type=p.requested_change_type, producer_ts=p.producer_ts,
    ))
    assert result.constraint_code == "unknown_environment_target"
    assert field is None


def test_cooldown_and_resources_change_only_on_execution():
    esm = make_esm()
    esm.register_environment_target("room", "scene", "zone", "env_lamp", cooldown_ms=1000, resource_available=2, resource_cost=1)
    assert esm.evaluate_proposal(proposal()).feasible
    p = proposal()
    request = EnvironmentRequest(request_id="r", room_id=p.room_id, scene_id=p.scene_id, zone_id=p.zone_id,
        target_entity_refs={"environment_ids": [p.target_environment_id]}, goal=p.goal,
        requested_change_type=p.requested_change_type, producer_ts=p.producer_ts)
    confirmation, field = esm.execute_with_confirmation(request)
    assert confirmation.execution_state == "confirmed"
    assert confirmation.rollback_token is None
    assert field.light_level == "low"
    probe = ConstraintProbe(probe_id="q", target_environment_id="env_lamp", constraint_type="all",
        producer_ts=100, causation_id="cause", correlation_id="corr")
    scope = {"room_id": "room", "scene_id": "scene", "zone_id": "zone"}
    state = esm.probe_constraints(probe, **scope)
    assert state.cooldown_remaining == 1000
    assert state.active_constraints["resource"] == {"available": 1, "cost": 1}
    assert esm.probe_constraints(probe.model_copy(update={"producer_ts": 1100}), **scope).cooldown_remaining == 0


@pytest.mark.parametrize("change_type", sorted(ESMService.SUPPORTED_ENVIRONMENT_CHANGE_TYPES))
def test_estimate_matches_real_coarse_effect(change_type):
    esm = make_esm()
    p = proposal(change_type)
    estimate = esm.evaluate_proposal(p).estimated_effect
    request = EnvironmentRequest(request_id="r", room_id=p.room_id, scene_id=p.scene_id, zone_id=p.zone_id,
        target_entity_refs={"environment_ids": [p.target_environment_id]}, goal=p.goal,
        requested_change_type=p.requested_change_type, producer_ts=p.producer_ts)
    _, result = esm.resolve_environment_request(request)
    assert all(getattr(result, key) == value for key, value in estimate.items())


@pytest.mark.parametrize("kind", ["cooldown", "material", "resource", "spatial"])
def test_probe_scope_and_selected_constraint(kind):
    esm = make_esm()
    probe = ConstraintProbe(probe_id="q", target_environment_id="custom", constraint_type=kind,
        producer_ts=100, causation_id="cause", correlation_id="corr")
    esm.register_environment_target("room", "scene", "zone", "custom")
    assert set(esm.probe_constraints(probe, room_id="room", scene_id="scene", zone_id="zone").active_constraints) == {kind}
    assert esm.probe_constraints(probe, room_id="other", scene_id="scene", zone_id="zone").active_constraints == {"target": {"exists": False}}


def test_failed_execution_confirmation_is_aborted():
    esm = make_esm()
    confirmation, state = esm.execute_with_confirmation(EnvironmentRequest(request_id="r", room_id="room",
        goal="test", requested_change_type="unsupported", producer_ts=100))
    assert confirmation.execution_state == "aborted"
    assert state is None


def test_all_constraints_are_reported_without_state_or_resource_mutation():
    esm = make_esm()
    esm.register_environment_target("room", "scene", "zone", "env_lamp", cooldown_until_ts=200,
        compatible_change_types=[], resource_available=0, resource_cost=1, spatial_allowed=False)
    before = copy.deepcopy(esm._environment_targets)
    probe = ConstraintProbe(probe_id="q", target_environment_id="env_lamp", constraint_type="all",
        producer_ts=100, causation_id="cause", correlation_id="corr")
    result = esm.probe_constraints(probe, room_id="room", scene_id="scene", zone_id="zone")
    assert result.active_constraints == {
        "cooldown": {"remaining": 100},
        "material": {"compatible_change_types": []},
        "resource": {"available": 0, "cost": 1},
        "spatial": {"allowed": False},
    }
    assert esm._environment_targets == before
