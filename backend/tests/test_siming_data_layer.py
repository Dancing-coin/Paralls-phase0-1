from __future__ import annotations

import pytest

from app.models.siming_event import (
    FairnessStateSnapshot,
    InterventionCandidate,
    InterventionDecision,
)
from app.services.siming_data_layer import (
    CACHE_KEY_PREFIX,
    TABLE_NAMES,
    SimingDataLayer,
    SimingHotCache,
    auditor_latest_key,
    cooldown_state_key,
    decision_recent_key,
    fairness_latest_key,
    fairness_snapshot_key,
    orchestrator_working_set_key,
    readmodel_latest_key,
)


def _snapshot(snapshot_id: str = "fairness:1") -> FairnessStateSnapshot:
    return FairnessStateSnapshot(
        snapshot_id=snapshot_id,
        room_id="room:1",
        scene_id="scene:1",
        zone_id="zone:1",
        causation_id="cause:1",
        correlation_id="corr:1",
        global_imbalance_score=0.42,
        dominant_imbalance_type="evidence_bottleneck",
    )


def _candidate() -> InterventionCandidate:
    return InterventionCandidate(
        candidate_id="candidate:1",
        room_id="room:1",
        scene_id="scene:1",
        zone_id="zone:1",
        causation_id="cause:1",
        correlation_id="corr:1",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
    )


def _decision() -> InterventionDecision:
    return InterventionDecision(
        decision_id="decision:1",
        room_id="room:1",
        scene_id="scene:1",
        zone_id="zone:1",
        causation_id="cause:1",
        correlation_id="corr:1",
        candidate_id="candidate:1",
        intervention_band="fact_reveal",
        accepted=True,
        selected_path="character_input_path",
    )


def test_six_persistent_tables_are_created(tmp_path) -> None:
    layer = SimingDataLayer(tmp_path / "siming.db")
    try:
        with layer._connection:
            rows = layer._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        names = {row[0] for row in rows}
        assert set(TABLE_NAMES) <= names
        assert len(TABLE_NAMES) == 6
    finally:
        layer.close()


def test_snapshot_persists_and_reads_back(tmp_path) -> None:
    layer = SimingDataLayer(tmp_path / "siming.db")
    try:
        # Previously snapshots were emitted and never stored at all.
        layer.save_snapshot(_snapshot(), sim_tick_ts=10, world_ts=10)

        restored = layer.latest_snapshot("room:1")
        assert restored is not None
        assert restored.snapshot_id == "fairness:1"
        assert restored.dominant_imbalance_type == "evidence_bottleneck"
    finally:
        layer.close()


def test_latest_snapshot_is_room_scoped(tmp_path) -> None:
    layer = SimingDataLayer(tmp_path / "siming.db")
    try:
        layer.save_snapshot(_snapshot("fairness:a"), sim_tick_ts=10, world_ts=10)

        # Room isolation is a core spec principle, not a convenience.
        assert layer.latest_snapshot("room:other") is None
    finally:
        layer.close()


def test_latest_snapshot_returns_the_newest_tick(tmp_path) -> None:
    layer = SimingDataLayer(tmp_path / "siming.db")
    try:
        layer.save_snapshot(_snapshot("fairness:old"), sim_tick_ts=10, world_ts=10)
        layer.save_snapshot(_snapshot("fairness:new"), sim_tick_ts=20, world_ts=20)

        restored = layer.latest_snapshot("room:1")
        assert restored is not None
        assert restored.snapshot_id == "fairness:new"
    finally:
        layer.close()


def test_decision_and_candidate_are_queryable_after_the_fact(tmp_path) -> None:
    layer = SimingDataLayer(tmp_path / "siming.db")
    try:
        layer.save_candidate(_candidate(), room_id="room:1", sim_tick_ts=10, world_ts=10)
        layer.save_decision(_decision(), room_id="room:1", sim_tick_ts=10, world_ts=10)

        decisions = layer.decisions_for_room("room:1")
        assert [d.decision_id for d in decisions] == ["decision:1"]
        assert decisions[0].selected_path == "character_input_path"
    finally:
        layer.close()


def test_saving_the_same_id_twice_updates_instead_of_duplicating(tmp_path) -> None:
    layer = SimingDataLayer(tmp_path / "siming.db")
    try:
        layer.save_snapshot(_snapshot(), sim_tick_ts=10, world_ts=10)
        layer.save_snapshot(_snapshot(), sim_tick_ts=30, world_ts=30)

        assert len(layer.decisions_for_room("room:1")) == 0
        restored = layer.latest_snapshot("room:1")
        assert restored is not None
        assert restored.snapshot_id == "fairness:1"
    finally:
        layer.close()


def test_cache_keys_follow_the_frozen_vocabulary() -> None:
    assert fairness_latest_key("r1") == f"{CACHE_KEY_PREFIX}room:r1:fairness:latest"
    assert fairness_snapshot_key("r1", "s1") == f"{CACHE_KEY_PREFIX}room:r1:fairness:snapshot:s1"
    assert cooldown_state_key("r1") == f"{CACHE_KEY_PREFIX}room:r1:cooldown:state"
    assert readmodel_latest_key("r1") == f"{CACHE_KEY_PREFIX}room:r1:readmodel:latest"
    assert decision_recent_key("r1") == f"{CACHE_KEY_PREFIX}room:r1:decision:recent"
    assert auditor_latest_key("r1", "suspicion_auditor") == (
        f"{CACHE_KEY_PREFIX}room:r1:auditor:suspicion_auditor:latest"
    )
    assert orchestrator_working_set_key("r1") == (
        f"{CACHE_KEY_PREFIX}room:r1:orchestrator:working_set"
    )


def test_hot_cache_round_trips_a_value() -> None:
    cache = SimingHotCache()

    cache.put(fairness_latest_key("r1"), {"snapshot_id": "fairness:1"})

    assert cache.get(fairness_latest_key("r1")) == {"snapshot_id": "fairness:1"}


def test_hot_cache_expires_entries() -> None:
    now = [0.0]
    cache = SimingHotCache(clock=lambda: now[0])
    cache.put("k", {"v": 1}, ttl_seconds=5)

    now[0] = 4.0
    assert cache.get("k") == {"v": 1}

    now[0] = 5.0
    assert cache.get("k") is None


def test_hot_cache_invalidate_removes_the_key() -> None:
    cache = SimingHotCache()
    cache.put("k", {"v": 1})
    cache.invalidate("k")

    assert cache.get("k") is None


def test_missing_cache_key_returns_none_not_an_empty_value() -> None:
    # "no entry" and "cached empty result" must stay distinguishable.
    assert SimingHotCache().get("absent") is None


def test_hot_cache_is_not_a_replay_source() -> None:
    cache = SimingHotCache()
    cache.put("k", {"v": 1}, ttl_seconds=0)

    # Entries are explicitly perishable; nothing may rely on them for history.
    assert cache.get("k") is None
