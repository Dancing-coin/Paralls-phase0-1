from __future__ import annotations

from app.character_agent.models.simulation_seed import CharacterContinuityCommand
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime


def test_scheduled_background_cognition_calls_only_wake_budget_actors() -> None:
    runtime = CharacterAgentRuntime()
    runtime.set_background_mode("char_a", "active")
    runtime.set_background_mode("char_b", "active")
    runtime.set_runtime_population_policy(
        max_active_actors_per_tick=1,
        wake_up_batch_size=1,
        degraded_population_threshold=100,
    )
    calls: list[str] = []

    def record_tick(*, actor_id: str, producer_ts: int):
        calls.append(actor_id)
        return (actor_id, producer_ts)

    runtime.run_background_cognition_tick = record_tick  # type: ignore[method-assign]

    results = runtime.run_scheduled_background_cognition_ticks(100)

    assert len(results) == 1
    assert calls == runtime.get_schedulable_actor_ids()
    assert len(calls) <= runtime.get_runtime_population_policy()[
        "max_active_actors_per_tick"
    ]


def _continuity_command(command_id: str, expected_revision: int) -> CharacterContinuityCommand:
    return CharacterContinuityCommand(
        command_id=command_id,
        actor_ref="character:char_a",
        expected_character_revision=expected_revision,
        from_tick=0,
        to_tick=1,
        simulation_tick_cursor=1,
        source_revision_vector={"world:test": 1},
        state_delta={"presentation_seed": {"behavior_kind": "observe"}},
        exposure_evidence={},
        policy_revision="policy:character-continuity:v1",
        idempotency_key=command_id,
    )


def test_delayed_cognition_result_requeues_after_actor_revision_advances(tmp_path) -> None:
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    first = runtime.apply_character_continuity_command(
        _continuity_command("continuity:first", 0)
    )

    delayed = runtime.apply_character_continuity_command(
        _continuity_command("continuity:delayed-provider-result", 0)
    )

    assert first.status == "committed"
    assert delayed.status == "requeued"
    assert delayed.refusal_reason == "character_revision_conflict"
    assert delayed.character_revision_before == 1
    assert delayed.character_revision_after == 1


def test_legacy_continuity_command_does_not_use_source_revision_as_time(tmp_path) -> None:
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    command = CharacterContinuityCommand(
        command_id="continuity:source-is-not-time",
        actor_ref="character:char_a",
        expected_character_revision=0,
        source_revision_vector={"gameplay:test": 99},
        state_delta={},
        exposure_evidence={},
        policy_revision="policy:character-continuity:v1",
        idempotency_key="continuity:source-is-not-time",
    )

    receipt = runtime.apply_character_continuity_command(command)
    event = runtime.get_session_timeline("char_a")[-1]

    assert receipt.status == "committed"
    assert receipt.simulation_tick_cursor == 0
    assert receipt.recorded_at == 0
    assert event["producer_ts"] == 0
