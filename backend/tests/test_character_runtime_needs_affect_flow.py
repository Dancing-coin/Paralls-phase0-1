from app.character_agent.profile.effective_profile import resolve_effective_profile
from app.character_agent.gateway.prompt_policy import CharacterPromptPolicy
from app.services.character_agent_l2 import CharacterAgentL2Service


def test_effective_profile_applies_drift_reweights_without_mutating_base_profile():
    base_profile = {
        "need_hierarchy_layer": {
            "base_weights": {
                "physiological": 0.2,
                "safety": 0.8,
                "belonging": 0.6,
                "esteem": 0.5,
                "self_actualization": 0.4,
            }
        },
        "long_term_personality_drift_layer": {
            "need_reweights": {"safety": 0.1},
            "trust_reweights": {},
            "expression_reweights": {},
            "stable_shifts": [],
            "reinforced_patterns": [],
            "weakened_patterns": [],
            "drift_policy": {
                "minimum_cross_scene_count": 3,
                "minimum_confirming_events": 8,
                "minimum_time_span": "long_arc",
                "require_non_transient_evidence": True,
            },
        },
    }

    effective = resolve_effective_profile(base_profile)

    assert effective["need_hierarchy_layer"]["effective_weights"]["safety"] == 0.9
    assert base_profile["need_hierarchy_layer"]["base_weights"]["safety"] == 0.8


class _StubProfile:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self) -> dict[str, object]:
        return dict(self._payload)


class _StubProfileLoader:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def load(self, actor_id: str) -> _StubProfile:
        return _StubProfile(self._payload)


def test_l2_reasoning_context_preserves_effective_profile_and_need_tension_state() -> None:
    authored_profile: dict[str, object] = {
        "identity_core": {
            "character_id": "char_a",
            "canonical_name": "Lin Yue",
        }
    }
    effective_profile: dict[str, object] = {
        "identity_core": {
            "character_id": "char_a",
            "canonical_name": "Lin Yue",
        },
        "need_hierarchy_layer": {
            "effective_weights": {
                "safety": 0.9,
            }
        },
    }
    service = CharacterAgentL2Service(profile_loader=_StubProfileLoader(authored_profile))

    context = service._reasoning_context(
        actor_id="char_a",
        snapshot={"actor_id": "char_a"},
        event={"event_type": "background_reappraisal", "perceived_summary": "door remains unsecured"},
        memory_bundle={},
        control_mode="agent_full_auto",
        working_memory_state={},
        current_goal_state=None,
        goal_state_history=None,
        supervision_state=None,
        unresolved_tensions=None,
        background_agenda_state=None,
        effective_profile=effective_profile,
        need_tension_state={"dominant_need": "safety"},
    )

    assert context["profile"] == authored_profile
    assert context["effective_profile"] == effective_profile
    assert context["need_tension_state"] == {"dominant_need": "safety"}


def test_l2_prompt_policy_includes_effective_profile_and_need_tension_state() -> None:
    prompt = CharacterPromptPolicy().build_prompt(
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_a",
            "control_mode": "agent_full_auto",
            "profile": {
                "identity_core": {
                    "character_id": "char_a",
                    "canonical_name": "Lin Yue",
                }
            },
            "effective_profile": {
                "identity_core": {
                    "character_id": "char_a",
                    "canonical_name": "Lin Yue",
                },
                "need_hierarchy_layer": {
                    "effective_weights": {
                        "safety": 0.9,
                    }
                },
            },
            "need_tension_state": {
                "dominant_need": "safety",
            },
            "snapshot": {"attention_targets": ["obj_letter"]},
            "memory": {"working_memory": [], "episodic_memories": [], "relational_memories": []},
            "event": {
                "actor_id": "char_a",
                "event_type": "background_reappraisal",
                "perceived_summary": "door remains unsecured",
            },
        },
        route={"route_mode": "online_default", "provider_kind": "online"},
    )

    user_instruction = str(prompt["user_instruction"])

    assert "effective_profile_summary=" in user_instruction
    assert "character_id=char_a" in user_instruction
    assert "safety=0.9" in user_instruction
    assert "need_tension_state=" in user_instruction
    assert "dominant_need=safety" in user_instruction
