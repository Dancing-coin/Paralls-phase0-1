from __future__ import annotations

import copy
import hashlib
import json

import pytest

from test_population_due_index import _runtime
from app.population_continuity.roster import PopulationRoster


def _sign(state):
    state["state_digest"] = "sha256:" + hashlib.sha256(json.dumps(
        {key: value for key, value in state.items() if key != "state_digest"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def _confirmed():
    world = _runtime(3)
    actor = world.roster.actor_ids[0]
    world.requeue_due_population_work(actor, "b1:work", 5, revision=1)
    world.requeue_due_population_work(actor, "b1:work", 9, revision=2)
    world.requeue_due_population_work(actor, "b1:other", 11, revision=0)
    cadence = world.build_population_cadence(window_start=0, window_end=21_600)
    world.confirm_population_cadence(cadence)
    return world, cadence


def test_recovery_state_restores_all_valid_due_keys_and_continues_exactly():
    source, cadence = _confirmed()
    state = json.loads(json.dumps(source.export_recovery_state()))
    target = _runtime(3)
    before_facts = target.store.export_snapshot()
    target.restore_recovery_state(state)
    assert target.store.export_snapshot() == before_facts
    assert target.export_recovery_state() == state
    assert target._population_due_index.get(source.roster.actor_ids[0], "b1:work") == (9, 2)
    assert len(target._population_due_index._heap) == len(target._population_due_index._entries) == 5
    assert target.confirm_population_cadence(cadence).status == "idempotent_replay"
    assert target.export_recovery_state() == state
    for world in (source, target):
        world.confirm_population_cadence(world.build_population_cadence(window_start=21_600, window_end=43_200))
    assert target.export_recovery_state() == source.export_recovery_state()
    state["actors"][0]["fatigue"] = 0.99
    assert target.population_hot_state.read(source.roster.actor_ids[0])["fatigue"] != 0.99


def test_initial_recovery_state_roundtrips_without_inventing_confirmation():
    world = _runtime(3)
    target = _runtime(3)
    target.restore_recovery_state(world.export_recovery_state())
    assert target.export_recovery_state() == world.export_recovery_state()
    assert target.latest_confirmation is None


@pytest.mark.parametrize("damage", ["digest", "roster", "duplicate_actor", "bool_revision", "nan",
                                    "tick", "due_actor", "duplicate_due", "receipt", "extra"])
def test_corrupt_recovery_state_is_rejected_without_partial_install(damage):
    source, _ = _confirmed()
    state = copy.deepcopy(source.export_recovery_state())
    if damage == "digest":
        state["state_digest"] = "sha256:" + "0" * 64
    elif damage == "roster":
        state["actors"].pop()
    elif damage == "duplicate_actor":
        state["actors"][1] = dict(state["actors"][0])
    elif damage == "bool_revision":
        state["actors"][0]["revision"] = True
    elif damage == "nan":
        state["actors"][0]["fatigue"] = float("nan")
    elif damage == "tick":
        state["actors"][0]["last_update_tick"] += 1
    elif damage == "due_actor":
        state["due_entries"][0]["actor_id"] = "outside-roster"
    elif damage == "duplicate_due":
        state["due_entries"].append(dict(state["due_entries"][0]))
    elif damage == "receipt":
        state["last_receipt"]["window_end"] += 1
    else:
        state["unexpected"] = "must reject"
    if damage != "digest":
        _sign(state)
    target = _runtime(3)
    before = target.export_recovery_state()
    with pytest.raises(ValueError):
        target.restore_recovery_state(state)
    assert target.export_recovery_state() == before


def test_recovery_rejects_changed_mode_configuration_even_with_same_revision():
    source, _ = _confirmed()
    target = _runtime(3)
    target.mode = target.mode.model_copy(update={"wake_budget": 1})
    before = target.export_recovery_state()
    with pytest.raises(ValueError, match="context"):
        target.restore_recovery_state(source.export_recovery_state())
    assert target.export_recovery_state() == before


def test_recovery_pins_roster_order_used_by_rotating_selection():
    source, _ = _confirmed()
    target = _runtime(3)
    target.roster = PopulationRoster(actor_ids=tuple(reversed(target.roster.actor_ids)))
    with pytest.raises(ValueError, match="context"):
        target.restore_recovery_state(source.export_recovery_state())


def test_recovery_canonicalizes_valid_integer_hot_fractions():
    source = _runtime(3)
    source.population_hot_state.upsert(source.roster.actor_ids[0], {"fatigue": 1}, revision=1)
    source.requeue_due_population_work(source.roster.actor_ids[0], "b0:presentation-threshold", 21_600, revision=1)
    target = _runtime(3)
    target.restore_recovery_state(source.export_recovery_state())
    assert target.export_recovery_state() == source.export_recovery_state()


@pytest.mark.parametrize("field", ["last_fingerprint", "projection_digest", "result_digest",
                                   "presentation_due_count", "new_due_count", "due_count",
                                   "deferred_count", "rejected_count", "due_backlog_count"])
def test_resigned_recovery_receipt_damage_is_rejected_without_writes(field):
    source, _ = _confirmed()
    state = copy.deepcopy(source.export_recovery_state())
    if field == "last_fingerprint":
        state[field] = "sha256:" + "0" * 64
    elif field.endswith("digest"):
        state["last_receipt"][field] = "sha256:" + "0" * 64
    else:
        state["last_receipt"][field] += 1
    _sign(state)
    target = _runtime(3)
    before = target.export_recovery_state()
    before_facts = target.store.export_snapshot()
    with pytest.raises(ValueError):
        target.restore_recovery_state(state)
    assert target.export_recovery_state() == before
    assert target.store.export_snapshot() == before_facts
