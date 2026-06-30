from app.world_runtime.scheduling import RuntimeCadencePolicy
from app.world_runtime.scheduling import RuntimePopulationPolicy
from app.world_runtime.scheduling import RuntimeWakeUpCandidate
from app.world_runtime.scheduling import select_schedulable_actor_ids


def test_runtime_cadence_policy_tracks_perception_and_cognition_intervals() -> None:
    policy = RuntimeCadencePolicy(
        perception_interval_ms=200,
        cognition_interval_ms=500,
        degraded_mode=False,
    )

    assert policy.perception_interval_ms == 200
    assert policy.cognition_interval_ms == 500
    assert policy.degraded_mode is False


def test_select_schedulable_actor_ids_prioritizes_wake_up_and_recovery_under_population_pressure() -> None:
    policy = RuntimePopulationPolicy(
        max_active_actors_per_tick=4,
        wake_up_batch_size=2,
        degraded_population_threshold=6,
        prioritize_continuity_recovery=True,
    )
    candidates = [
        RuntimeWakeUpCandidate(
            actor_id="char_a",
            wake_up_requested=True,
            continuity_priority=0,
            salience=0.90,
            last_active_ts=5000,
        ),
        RuntimeWakeUpCandidate(
            actor_id="char_b",
            wake_up_requested=False,
            continuity_priority=2,
            salience=0.60,
            last_active_ts=4900,
        ),
        RuntimeWakeUpCandidate(
            actor_id="char_c",
            wake_up_requested=True,
            continuity_priority=3,
            salience=0.75,
            last_active_ts=4800,
        ),
        RuntimeWakeUpCandidate(
            actor_id="char_d",
            wake_up_requested=False,
            continuity_priority=1,
            salience=0.95,
            last_active_ts=4700,
        ),
    ]

    selected = select_schedulable_actor_ids(
        candidates=candidates,
        policy=policy,
        actor_population=7,
    )

    assert selected == ["char_c", "char_b"]
