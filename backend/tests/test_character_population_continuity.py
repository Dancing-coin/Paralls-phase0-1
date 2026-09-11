from __future__ import annotations

from app.character_agent.models.simulation_seed import CharacterContinuityCommand
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime


def test_continuity_only_actor_can_receive_dormant_state_without_full_agent_profile() -> None:
    runtime = CharacterAgentRuntime(continuity_actor_ids={"resident_01"})

    receipt = runtime.apply_character_continuity_command(
        CharacterContinuityCommand(
            command_id="continuity:resident_01:1",
            actor_ref="character:resident_01",
            expected_character_revision=0,
            source_revision_vector={"world:test": 1},
            state_delta={
                "dynamic_state": {"stress_load": 0.2},
            },
            exposure_evidence={"presentation_seed": {"task": "commute_to_bakery"}},
            policy_revision="policy:character-continuity:v1",
            idempotency_key="continuity:resident_01:1",
        )
    )

    assert not runtime.supports_actor("resident_01")
    assert runtime.supports_continuity_actor("resident_01")
    assert receipt.status == "committed"
    assert runtime.get_continuity_revision("resident_01") == 1
    assert runtime.get_dynamic_state("resident_01")["stress_load"] == 0.2
