from fractions import Fraction
from dataclasses import replace

import pytest

from app.world_runtime.simulation_clock import SimulationClock
from app.world_runtime.temporal_contracts import TemporalAuthorization, verify_temporal_authorization


def configured_clock():
    from app.world_runtime.temporal_contracts import ClockMapping, SimulationTimeline, TemporalProfile

    profile = TemporalProfile(
        profile_id="legacy.seconds", revision="1", content_package_ref="legacy",
        advancement_policy="continuous", resolution_quantum="fixed_step",
        scheduling_policy="scheduled_event", settlement_policy="immediate_owner_action",
        time_control_policy="world", determinism_policy="best_effort", rewind_policy="disabled",
        canonical_unit_ref="second", step_duration=Fraction(1), supported_clock_mappings=("physics", "render"),
        rounding_policy="floor", activation_boundary="step", compatibility_constraints=(),
    )
    timeline = SimulationTimeline(
        timeline_id="world:1", world_scope_ref="world:1", advancement_owner_ref="existing-driver",
        profile_ref=profile.profile_id, profile_revision="1", epoch_ref="legacy", current_step=0,
        current_phase=None, authoritative_revision=0, status="active",
    )
    mapping = ClockMapping(
        mapping_id="physics", revision="1", source_clock_ref="physics", source_unit_ref="frame",
        target_timeline_ref="world:1", target_profile_revision="1", source_origin=0,
        target_origin=0, ratio=Fraction(1, 60), rounding_policy="floor",
        valid_source_interval=(0, 600), max_lateness=5, evidence_source_policy_ref="existing-physics",
    )
    return SimulationClock(world_ref="world:1", temporal_profile=profile, timeline=timeline), mapping


def mapped(clock, mapping, **overrides):
    fields = dict(mapping=mapping, source_clock_ref="physics", source_unit_ref="frame",
                  source_revision="1", expected_source_revision="1", mapping_revision="1",
                  sampled_at=125, received_at=127)
    fields.update(overrides)
    return clock.map_source_time(**fields)


def test_clock_maps_rational_units_without_advancing_world():
    clock, mapping = configured_clock()
    result = mapped(clock, mapping)
    assert result.step_index == 2
    assert result.canonical_time_value == Fraction(2)
    assert clock.tick == 0
    advanced = clock.advance_mapped(result, advancement_owner_ref="existing-driver", source_mapping=mapping)
    assert advanced.current_tick == 2


@pytest.mark.parametrize("overrides", [
    {"source_clock_ref": "turn"}, {"source_unit_ref": "second"},
    {"source_revision": "2"}, {"received_at": 140}, {"received_at": 124},
    {"sampled_at": 601, "received_at": 602},
])
def test_clock_rejects_unmapped_stale_or_wrong_source_without_advancing(overrides):
    clock, mapping = configured_clock()
    with pytest.raises(ValueError):
        mapped(clock, mapping, **overrides)
    assert clock.tick == 0


def test_clock_rejects_cross_timeline_and_non_owner_advance():
    clock, mapping = configured_clock()
    time = mapped(clock, mapping)
    with pytest.raises(ValueError, match="owner"):
        clock.advance_mapped(time, advancement_owner_ref="role", source_mapping=mapping)
    with pytest.raises(ValueError, match="timeline"):
        clock.advance_mapped(replace(time, timeline_id="other"), advancement_owner_ref="existing-driver", source_mapping=mapping)
    assert clock.tick == 0


def test_render_mapping_is_projection_only_and_cannot_be_advance_input():
    clock, mapping = configured_clock()
    render = replace(mapping, mapping_id="render", source_clock_ref="render")
    time = mapped(clock, render, source_clock_ref="render")
    assert time.step_index == 2
    with pytest.raises(ValueError, match="projection_only"):
        clock.advance_mapped(time, advancement_owner_ref="existing-driver", source_mapping=render)
    assert clock.tick == 0


def test_profile_activation_is_boundary_bound_and_keeps_existing_time_pins():
    clock, mapping = configured_clock()
    time = mapped(clock, mapping)
    with pytest.raises(ValueError, match="boundary"):
        clock.activate_temporal_profile(replace(clock.temporal_profile, revision="2"),
                                        advancement_owner_ref="existing-driver", boundary="wrong")
    clock.activate_temporal_profile(replace(clock.temporal_profile, revision="2"),
                                    advancement_owner_ref="existing-driver", boundary="step")
    assert clock.timeline.profile_revision == "2"
    assert mapping.target_profile_revision == "1"
    assert time.canonical_time_value == 2
    with pytest.raises(ValueError, match="profile_revision"):
        mapped(clock, mapping)


def test_profile_unit_or_duration_change_requires_consumer_migration():
    clock, _ = configured_clock()
    with pytest.raises(ValueError, match="migration_required"):
        clock.activate_temporal_profile(replace(clock.temporal_profile, revision="2", step_duration=Fraction(1, 2)),
                                        advancement_owner_ref="existing-driver", boundary="step")
    assert clock.timeline.profile_revision == "1"


def test_deterministic_or_rollback_profile_cannot_activate_without_adapter_admission():
    clock, _ = configured_clock()
    with pytest.raises(ValueError, match="adapter_admission_required"):
        clock.activate_temporal_profile(replace(clock.temporal_profile, revision="2", determinism_policy="rollback_deterministic", rewind_policy="unconfirmed_window"),
                                        advancement_owner_ref="existing-driver", boundary="step")
    assert clock.timeline.profile_revision == "1"


def test_pinned_clock_rejects_raw_advance_bypassing_owner_and_mapping():
    clock, _ = configured_clock()
    with pytest.raises(ValueError, match="mapped_advance_required"):
        clock.advance(10)
    assert clock.tick == 0


def test_clock_rejects_float_source_coordinates_without_rounding_them_silently():
    clock, mapping = configured_clock()
    with pytest.raises(ValueError, match="source_coordinate"):
        mapped(clock, mapping, sampled_at=125.5)
    assert clock.tick == 0


def test_source_owner_revision_is_independent_of_clock_mapping_revision():
    clock, mapping = configured_clock()
    result = mapped(clock, mapping, source_revision="physics-owner:8", expected_source_revision="physics-owner:8")
    assert result.step_index == 2
    with pytest.raises(ValueError, match="mapping_revision"):
        mapped(clock, mapping, mapping_revision="stale")


def test_scheduled_work_selection_keeps_budget_deferred_and_rejects_other_timeline():
    from app.world_runtime.temporal_contracts import ScheduledWork
    from app.world_runtime.scheduling import select_temporal_work

    clock, mapping = configured_clock()
    now = mapped(clock, mapping)
    first = ScheduledWork("first", "inventory", now, "event:1", ("a",), (), "existing-inventory")
    second = replace(first, work_ref="second", ordering_key=("b",))
    selected, deferred = select_temporal_work((second, first), now=now, budget=1)
    assert [item.work_ref for item in selected] == ["first"]
    assert [item.work_ref for item in deferred] == ["second"]
    with pytest.raises(ValueError, match="timeline"):
        select_temporal_work((replace(first, due_time=replace(now, timeline_id="other")),), now=now, budget=1)


def test_settlement_window_rejects_cross_timeline_read_boundary():
    from app.world_runtime.temporal_contracts import SettlementWindow

    clock, mapping = configured_clock()
    now = mapped(clock, mapping)
    with pytest.raises(ValueError, match="timeline"):
        SettlementWindow("window:1", "world:1", now, replace(now, timeline_id="other"),
                         ("inventory",), None, now, "reject", now, (), (), "stable", (), "window:1")


@pytest.mark.parametrize(
    ("field", "error"),
    (("cutoff", "settlement_window_cutoff_out_of_bounds"),
     ("confirmation", "settlement_window_confirmation_out_of_bounds")),
)
def test_settlement_window_rejects_boundary_outside_window(field: str, error: str):
    from app.world_runtime.temporal_contracts import SettlementWindow, SimulationTime

    start = SimulationTime("world:1", 10, Fraction(10))
    end = SimulationTime("world:1", 20, Fraction(20))
    outside = SimulationTime("world:1", 21, Fraction(21))
    cutoff = outside if field == "cutoff" else end
    confirmation = outside if field == "confirmation" else end
    with pytest.raises(ValueError, match=error):
        SettlementWindow("window:1", "world:1", start, end, ("owner:1",), None,
                         cutoff, "reject_after_cutoff", confirmation, (), (),
                         "dependency_then_ref", (), "batch:1")


def test_temporal_authorization_digest_and_scope_fail_closed_on_tamper_or_revoke():
    grant = TemporalAuthorization(
        authorization_ref="authorization:test@1", revision="authorization:test@1",
        issuer_ref="population-cadence:world:1", timeline_id="world:1",
        participant_scope=("inventory",), input_cutoff=10, confirmation_boundary=10,
        late_input_policy_ref="reject_after_cutoff", ordering_policy_ref="stable",
        valid_until=10,
    )
    pins = {**grant.payload(), "temporal_authorization_digest": grant.digest,
            "temporal_authorization_ref": grant.authorization_ref,
            "temporal_authorization_revision": grant.revision,
            "temporal_authorization_issuer_ref": grant.issuer_ref,
            "temporal_authorization_valid_until": grant.valid_until,
            "settlement_participant_scope": "inventory",
            "timeline_id": grant.timeline_id}
    assert verify_temporal_authorization(pins=pins, expected_participant="inventory",
                                         expected_cutoff=10, expected_timeline="world:1")
    pins["input_cutoff"] = 11
    assert not verify_temporal_authorization(pins=pins, expected_participant="inventory",
                                             expected_cutoff=10, expected_timeline="world:1")
    with pytest.raises(ValueError, match="temporal_authorization_invalid"):
        TemporalAuthorization(**{**grant.payload(), "revoked": True})


def test_scoped_temporal_grant_digest_is_verified_from_serialized_cadence_pins():
    grant = TemporalAuthorization(
        authorization_ref="authorization:economy@1", revision="authorization:temporal@1",
        issuer_ref="population-cadence:world:1", timeline_id="world:1",
        participant_scope=("economy",), input_cutoff=10, confirmation_boundary=10,
        late_input_policy_ref="reject_after_cutoff", ordering_policy_ref="stable", valid_until=10,
    )
    import json
    pins = {
        "timeline_id": "world:1", "temporal_authorization_issuer_ref": grant.issuer_ref,
        "sampled_at": 10, "received_at": 10, "input_cutoff": 10,
        "confirmation_boundary": 10, "temporal_authorizations": json.dumps(
            {"economy": {**grant.payload(), "digest": grant.digest}}, separators=(",", ":"))
    }
    assert verify_temporal_authorization(pins=pins, expected_participant="economy",
                                         expected_cutoff=10, expected_timeline="world:1",
                                         grant_key="economy")
    pins["temporal_authorizations"] = pins["temporal_authorizations"].replace(grant.digest, "sha256:tampered")
    assert not verify_temporal_authorization(pins=pins, expected_participant="economy",
                                             expected_cutoff=10, expected_timeline="world:1",
                                             grant_key="economy")


def test_scoped_temporal_grant_rejects_removed_cadence_issuer_pin():
    grant = TemporalAuthorization(
        authorization_ref="authorization:economy@1", revision="authorization:temporal@1",
        issuer_ref="population-cadence:world:1", timeline_id="world:1",
        participant_scope=("economy",), input_cutoff=10, confirmation_boundary=10,
        late_input_policy_ref="reject_after_cutoff", ordering_policy_ref="stable", valid_until=10,
    )
    import json
    pins = {
        "timeline_id": "world:1", "temporal_authorization_issuer_ref": grant.issuer_ref,
        "sampled_at": 10, "received_at": 10, "input_cutoff": 10,
        "confirmation_boundary": 10,
        "temporal_authorizations": json.dumps(
            {"economy": {**grant.payload(), "digest": grant.digest}}, separators=(",", ":")),
    }
    assert verify_temporal_authorization(pins=pins, expected_participant="economy",
        expected_cutoff=10, expected_timeline="world:1", grant_key="economy")
    del pins["temporal_authorization_issuer_ref"]
    assert not verify_temporal_authorization(pins=pins, expected_participant="economy",
        expected_cutoff=10, expected_timeline="world:1", grant_key="economy")


def test_temporal_authorization_preserves_scope_and_rejects_revoked_or_expired_serialized_grants():
    grant = TemporalAuthorization(
        authorization_ref="authorization:shared@1", revision="authorization:temporal@1",
        issuer_ref="population-cadence:world:1", timeline_id="world:1",
        participant_scope=("economy", "ecology"), input_cutoff=10, confirmation_boundary=10,
        late_input_policy_ref="reject_after_cutoff", ordering_policy_ref="stable", valid_until=10,
    )
    import json
    payload = {**grant.payload(), "digest": grant.digest}
    pins = {"timeline_id": "world:1", "temporal_authorization_issuer_ref": grant.issuer_ref,
            "sampled_at": 10, "received_at": 10, "input_cutoff": 10,
            "confirmation_boundary": 10, "temporal_authorizations": json.dumps(
        {"shared": payload}, separators=(",", ":"))}
    assert verify_temporal_authorization(
        pins=pins, expected_participant="ecology", expected_cutoff=10,
        expected_timeline="world:1", grant_key="shared")
    assert not verify_temporal_authorization(
        pins=pins, expected_participant="economy", expected_cutoff=11,
        expected_timeline="world:1", grant_key="shared")
    revoked = {**payload, "revoked": True}
    pins["temporal_authorizations"] = json.dumps({"shared": revoked}, separators=(",", ":"))
    assert not verify_temporal_authorization(
        pins=pins, expected_participant="ecology", expected_cutoff=10,
        expected_timeline="world:1", grant_key="shared")


@pytest.mark.parametrize("field,value", [("input_cutoff", "10"), ("confirmation_boundary", 10.0), ("valid_until", "10")])
def test_temporal_authorization_rejects_non_integer_time_fields(field, value):
    import json
    grant = TemporalAuthorization(
        authorization_ref="authorization:typed@1", revision="authorization:typed@1",
        issuer_ref="population-cadence:world:1", timeline_id="world:1",
        participant_scope=("economy",), input_cutoff=10, confirmation_boundary=10,
        late_input_policy_ref="reject_after_cutoff", ordering_policy_ref="stable", valid_until=10,
    )
    payload = {**grant.payload(), field: value, "digest": grant.digest}
    pins = {"timeline_id": "world:1", "temporal_authorization_issuer_ref": grant.issuer_ref,
            "sampled_at": 10, "received_at": 10, "input_cutoff": 10,
            "confirmation_boundary": 10, "temporal_authorizations": json.dumps({"shared": payload}, separators=(",", ":"))}
    assert not verify_temporal_authorization(
        pins=pins, expected_participant="economy", expected_cutoff=10,
        expected_timeline="world:1", grant_key="shared")
