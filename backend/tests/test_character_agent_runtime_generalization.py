from __future__ import annotations

from pathlib import Path

from app.character_agent.runtime import runtime_loop
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime


def _write_profile(
    directory: Path,
    *,
    actor_id: str,
    canonical_name: str,
    default_control_mode: str | None = None,
) -> None:
    runtime_defaults_lines: list[str] = []
    if default_control_mode is not None:
        runtime_defaults_lines = [
            "",
            "runtime_defaults:",
            f"  default_control_mode: {default_control_mode}",
        ]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{actor_id}.yaml").write_text(
        "\n".join(
            [
                "identity_core:",
                f"  character_id: {actor_id}",
                f"  canonical_name: {canonical_name}",
                "  aliases:",
                f"    - {canonical_name}",
                "  occupation_role: tester",
                "",
                "origin_seed:",
                "  homeland: test_harbor",
                "  formative_context: test setup",
                "  current_scene_function: runtime validation",
                "",
                "life_memory_backbone:",
                "  defining_memories:",
                "    - learned to respond inside the runtime loop",
                "  unresolved_knots:",
                "    - none",
                "",
                "virtue_value_layer:",
                "  value_priorities:",
                "    - clarity",
                "  red_lines:",
                "    - break the ingress contract",
                "  forbidden_behaviors:",
                "    - bypass structured results",
                "",
                "trait_vector_layer:",
                "  courage: 0.50",
                "  scheming: 0.50",
                "  empathy: 0.50",
                "  rationality: 0.50",
                "  sociability: 0.50",
                "",
                "capability_constraint_layer:",
                "  skills:",
                "    - observation",
                "  knowledge_domains:",
                "    - testing",
                "  physical_constraints:",
                "    - none",
                "  psychological_constraints:",
                "    - none",
                "  social_constraints:",
                "    - none",
                "",
                "style_expression_bias_layer:",
                "  speech_style: direct",
                "  silence_pattern: measured",
                "  gesture_bias: minimal",
                "  posture_bias: steady",
                "",
                "conversation_personality_layer:",
                "  social_openness: 0.50",
                "  privacy_sensitivity: 0.50",
                "  talk_initiative: 0.50",
                "  deception_control: 0.50",
                "  trust_threshold_for_private_talk: 0.50",
                *runtime_defaults_lines,
                "",
            ]
        ),
        encoding="utf-8",
    )


def _patch_registry_to_directory(monkeypatch, directory: Path) -> None:
    original_from_directory = runtime_loop.CharacterProfileRegistry.from_directory

    monkeypatch.setattr(
        runtime_loop.CharacterProfileRegistry,
        "from_directory",
        classmethod(lambda cls, source_directory: original_from_directory(directory)),
    )


def test_runtime_supports_registered_actor_ids_without_supported_actors_constant(monkeypatch, tmp_path: Path) -> None:
    profiles_directory = tmp_path / "profiles"
    _write_profile(profiles_directory, actor_id="char_registry_only", canonical_name="Registry Only")
    _patch_registry_to_directory(monkeypatch, profiles_directory)

    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_registry_only",
        percept_channel="visual",
        producer_ts=701,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/registry_only_actor",
        source_candidate_event_id="visual_fact:701:char_registry_only",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    commands = runtime.ingest_character_perceived_event(event)
    snapshot = runtime.get_private_snapshot("char_registry_only")

    assert not hasattr(CharacterAgentRuntime, "SUPPORTED_ACTORS")
    assert runtime.supports_actor("char_registry_only")
    assert runtime.supports_actor("char_a") is False
    assert snapshot is not None
    assert snapshot.actor_id == "char_registry_only"
    assert commands


def test_runtime_uses_profile_runtime_defaults_for_control_modes(monkeypatch, tmp_path: Path) -> None:
    profiles_directory = tmp_path / "profiles"
    _write_profile(profiles_directory, actor_id="char_registry_only", canonical_name="Registry Only")
    _write_profile(
        profiles_directory,
        actor_id="char_registry_assisted",
        canonical_name="Registry Assisted",
        default_control_mode="player_priority_assisted",
    )
    _write_profile(profiles_directory, actor_id="char_c", canonical_name="Fixture Without Override")
    _patch_registry_to_directory(monkeypatch, profiles_directory)

    runtime = CharacterAgentRuntime()

    assert not hasattr(CharacterAgentRuntime, "_PLAYER_PRIORITY_ASSISTED_DEFAULT_ACTORS")
    assert runtime.get_control_mode("char_registry_only") == "agent_full_auto"
    assert runtime.get_control_mode("char_registry_assisted") == "player_priority_assisted"
    assert runtime.get_control_mode("char_c") == "agent_full_auto"
