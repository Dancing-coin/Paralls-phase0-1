import pytest
import json
from pathlib import Path

from app.gameplay.godot_mirror_delivery import GameplayGodotMirrorSyncAdapter
from app.gameplay.godot_mirror_projection import project_godot_runtime_state
from app.population_continuity.presentation import build_population_actor_view
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from test_population_durable_cadence_recovery import _publisher, _runtime


@pytest.mark.parametrize("population", [100, 1000, 10000])
def test_public_view_uses_only_confirmed_whitelisted_fields(tmp_path, population):
    actors = tuple(f"resident_{index}" for index in range(population))
    world = _runtime(tmp_path / "world.sqlite3", actors)
    actor = actors[-1]
    initial = build_population_actor_view(world, actor_id=actor)
    initial_payload = project_godot_runtime_state(initial)["groups"]["population_public"]["payload"]
    assert set(initial_payload) == {"actor_id", "confirmed_tick", "presentation_position", "animation_tag", "public_digest"}
    assert initial_payload["confirmed_tick"] == 0 and initial_payload["animation_tag"] == "idle"
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    cadence = world.build_population_cadence(window_start=0, window_end=86400)
    world.build_population_projections(cadence)
    assert build_population_actor_view(world, actor_id=actor) == initial
    assert publisher(cadence)
    view = build_population_actor_view(world, actor_id=actor)
    payload = view.groups["population_public"].payload
    assert payload["confirmed_tick"] == 86400
    assert tuple(payload["presentation_position"]) == tuple(initial_payload["presentation_position"])
    assert dict(view.source_revision_vector) == {"population-cadence:world": 1}
    row = world.population_hot_state.read(actor)
    world.population_hot_state.upsert(actor, {"fatigue": 0.87, "need_pressure": 0.21}, int(row["revision"]) + 1)
    assert build_population_actor_view(world, actor_id=actor) == view
    with pytest.raises(ValueError, match="population_actor_unknown"):
        build_population_actor_view(world, actor_id="outsider")
    with pytest.raises(TypeError):
        payload["animation_tag"] = "changed"


def test_public_view_waits_for_durable_confirmation_and_survives_restart(tmp_path, monkeypatch):
    path = tmp_path / "world.sqlite3"
    world = _runtime(path)
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    save = world.store.save_projection_checkpoints_atomic
    monkeypatch.setattr(world.store, "save_projection_checkpoints_atomic", lambda _: (_ for _ in ()).throw(RuntimeError("checkpoint_failed")))
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    with pytest.raises(RuntimeError, match="checkpoint_failed"):
        publisher(cadence)
    with pytest.raises(ValueError, match="population_presentation_unconfirmed"):
        build_population_actor_view(world, actor_id="one")
    monkeypatch.setattr(world.store, "save_projection_checkpoints_atomic", save)
    assert publisher(cadence)
    expected = build_population_actor_view(world, actor_id="one")
    restarted = _runtime(path)
    _publisher(restarted, InMemoryAuthorityEventBus())
    assert build_population_actor_view(restarted, actor_id="one") == expected
    adapter = GameplayGodotMirrorSyncAdapter()
    base = adapter.snapshot(expected)
    assert publisher(world.build_population_cadence(window_start=60, window_end=120))
    target = adapter.snapshot(build_population_actor_view(world, actor_id="one"))
    delta = adapter.delta(base, target)
    assert adapter.apply_delta(base, delta) == target
    with pytest.raises(ValueError):
        adapter.apply_delta(target, delta)


def test_external_godot_population_vectors_match_confirmed_runtime_builder(tmp_path):
    vectors = json.loads((Path(__file__).resolve().parents[2] / "scripts/verification/fixtures/population-mirror-vectors.json").read_text(encoding="utf-8"))
    world = _runtime(tmp_path / "vectors.sqlite3")
    sync = GameplayGodotMirrorSyncAdapter()
    base = sync.snapshot(build_population_actor_view(world, actor_id="one"))
    assert sync.snapshot_payload(base) == vectors["base"]
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    assert publisher(world.build_population_cadence(window_start=0, window_end=60))
    target = sync.snapshot(build_population_actor_view(world, actor_id="one"))
    assert sync.snapshot_payload(target) == vectors["target"]
    assert sync.delta_payload(base, sync.delta(base, target)) == vectors["delta"]
