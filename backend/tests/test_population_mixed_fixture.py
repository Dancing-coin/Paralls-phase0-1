import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.population_continuity.organization_due_source import OrganizationWindowDueSource
from app.population_continuity.roster import PopulationRoster
from scripts.verification.population_mixed_load import MixedLoadSchedule
from scripts.verification.population_mixed_fixture import prepare_due_fixture


def test_regular_fixture_is_real_owner_due_and_exact_replay_is_zero_write(tmp_path):
    path = tmp_path / "gameplay.sqlite3"
    store = DurableGameplayEventStore(path)
    actors = tuple(f"worker_{i}" for i in range(100))
    event = next(row for row in MixedLoadSchedule(100, 7, "one_x").events(1) if row.kind == "regular_due")
    first = prepare_due_fixture(store=store, actors=actors, event=event)
    assert len(first) == 28
    before = store.export_snapshot()
    assert prepare_due_fixture(store=DurableGameplayEventStore(path), actors=actors, event=event) == first
    assert store.export_snapshot() == before
    source = OrganizationWindowDueSource(store=store, world_ref="world:test", roster=PopulationRoster(actor_ids=actors))
    rows = source.read(window_end=1, observed_at="2026-09-17T00:00:00Z", scope="organization:summary").projections
    assert len(rows) == 28 and {row.payload["due_tick"] for row in rows} == {1}
    assert {row.payload["closed_event_id"] for row in rows} == {row["closed_event_id"] for row in first}


def test_partial_fixture_failure_resumes_original_owner_prefix_and_peak_is_not_clipped(tmp_path, monkeypatch):
    store = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    actors = tuple(f"worker_{i}" for i in range(1000))
    event = next(row for row in MixedLoadSchedule(1000, 7, "one_x").events(300) if row.kind == "due_peak")
    original, calls = OrganizationAuthority.close_operating_window, []
    def close(owner, **kwargs):
        calls.append(kwargs["window_ref"])
        if len(calls) == 18:
            raise RuntimeError("fixture interrupted")
        return original(owner, **kwargs)
    monkeypatch.setattr(OrganizationAuthority, "close_operating_window", close)
    with pytest.raises(RuntimeError, match="fixture interrupted"):
        prepare_due_fixture(store=store, actors=actors, event=event)
    prefix = store.read_events()
    assert len(prefix) == 16 * 6
    result = prepare_due_fixture(store=store, actors=actors, event=event)
    assert len(result) == 100
    assert store.read_events()[:len(prefix)] == prefix
    assert len(store.read_events()) == 100 * 6
    assert len({row["window_ref"] for row in result}) == 100
    assert {row["due_tick"] for row in result} == {300}


def test_regular_fixture_groups_owner_writes_into_two_durable_commits(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "fixture-commits.db")
    actors = tuple(f"worker_{i}" for i in range(100))
    event = next(row for row in MixedLoadSchedule(100, 7, "one_x").events(1) if row.kind == "regular_due")
    statements = []
    store._database_connection().set_trace_callback(statements.append)

    assert len(prepare_due_fixture(store=store, actors=actors, event=event)) == 28

    assert sum(statement == "COMMIT" for statement in statements) == 2


def test_fixture_same_key_cannot_be_rebound_to_other_actor(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    event = next(row for row in MixedLoadSchedule(100, 7, "one_x").events(1) if row.kind == "regular_due")
    actors = tuple(f"worker_{i}" for i in range(100))
    prepare_due_fixture(store=store, actors=actors, event=event)
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="mixed_fixture_schedule_conflict"):
        prepare_due_fixture(store=store, actors=tuple("other_" + actor for actor in actors), event=event)
    assert store.export_snapshot() == before


def test_conflict_fixture_extends_real_registry_before_pins_and_replays_exact_source(tmp_path):
    from pathlib import Path
    from app.character_agent.profile.registry import CharacterProfileRegistry
    from app.gameplay.production_package_registry import build_production_package_registry, build_production_social_policy_registry
    from scripts.verification.population_mixed_fixture import install_conflict_fixture_package, prepare_conflict_fixture
    root = Path(__file__).resolve().parents[2]
    packages = build_production_package_registry(root)
    original = packages.active_patch_set.patch_revision_ids
    added = install_conflict_fixture_package(packages)
    assert set(packages.active_patch_set.patch_revision_ids) == {*original, added}
    profiles = CharacterProfileRegistry.from_directory(root / "assets/characters/profiles")
    path = tmp_path / "gameplay.sqlite3"
    store = DurableGameplayEventStore(path)
    args = dict(packages=packages, policy_registry=build_production_social_policy_registry(), profiles=profiles,
        actors=("char_a", "char_b", "char_c", "resident_0"), key="mixed:100:17:one_x:siming_model:1")
    wakes = prepare_conflict_fixture(store=store, **args)
    assert [row.actor_id for row in wakes] == ["char_a", "char_b", "char_c"]
    assert len({row.source_event_id for row in wakes}) == 1
    before = store.export_snapshot()
    assert prepare_conflict_fixture(store=DurableGameplayEventStore(path), **args) == wakes
    assert store.export_snapshot() == before
    with pytest.raises(ValueError, match="mixed_fixture_conflict_source_changed"):
        prepare_conflict_fixture(store=store, **{**args, "actors": ("char_a", "char_b")})
    assert store.export_snapshot() == before
