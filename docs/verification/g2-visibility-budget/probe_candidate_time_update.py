"""Reproduce current behavior; no decision about time correction authority."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / "backend"), str(root / "backend" / "tests")]
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from test_character_agent_seed_continuity import command_for_char_a


def main():
    runtime = CharacterAgentRuntime(memory_known_time_provider=lambda _: 100)
    try:
        first = command_for_char_a(world_ref="world:bakery")
        evidence = first.model_dump(mode="json")["exposure_evidence"]
        evidence["memory_candidates"][0]["event_valid_at"] = 99
        first = first.model_copy(update={"exposure_evidence": evidence})
        committed = runtime.apply_character_continuity_command(first)
        assert committed.status == "committed"
        assert runtime.materialize_pending_seed_memories("char_a", 100000)[0].refusal_reason == "temporal_knowledge_denied"
        evidence = first.model_dump(mode="json")["exposure_evidence"]
        evidence["memory_candidates"][0]["knowledge_available_at"] = 100
        second = first.model_copy(update={"command_id": "continuity:earlier", "idempotency_key": "continuity:earlier",
            "expected_character_revision": committed.character_revision_after, "exposure_evidence": evidence})
        result = runtime.apply_character_continuity_command(second)
        receipt = runtime.materialize_pending_seed_memories("char_a", 100001)[0]
        assert result.status == "committed" and receipt.status == "committed"
        assert len(runtime.get_memory_bundle("char_a")["event_memories"]) == 1
        print("initial known=101, world clock=100: deferred")
        print("same candidate updated known=100: committed and materialized")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
