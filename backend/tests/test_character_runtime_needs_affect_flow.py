from copy import deepcopy

from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation
from app.models.character_perceived import CharacterPerceivedEvent
from app.character_agent.profile.effective_profile import resolve_effective_profile
from app.character_agent.gateway.prompt_policy import CharacterPromptPolicy
from app.services.character_agent_l2 import CharacterAgentL2Service
from app.services.character_agent_runtime import CharacterAgentRuntime


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


class _RecordingL2(CharacterAgentL2Service):
    def __init__(self, authored_profile: dict[str, object]) -> None:
        super().__init__(profile_loader=_StubProfileLoader(authored_profile))
        self.prepare_context: dict[str, object] | None = None
        self.interpret_context: dict[str, object] | None = None

    def prepare_reasoning_request(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        event: CharacterPerceivedEvent,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        control_mode: str,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | None = None,
        goal_state_history: list[dict[str, object]] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.prepare_context = self._reasoning_context(
            actor_id=snapshot.actor_id,
            snapshot=snapshot.model_dump(),
            event=event.model_dump(),
            memory_bundle=memory_bundle,
            control_mode=control_mode,
            working_memory_state=working_memory_state,
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=background_agenda_state,
            effective_profile=effective_profile,
            need_tension_state=need_tension_state,
        )
        return {"task_kind": "l2_reasoning", "context": deepcopy(self.prepare_context)}

    def interpret_perceived_event(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        event: CharacterPerceivedEvent,
        *,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | None = None,
        goal_state_history: list[dict[str, object]] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
    ) -> CharacterInterpretation:
        self.interpret_context = self._reasoning_context(
            actor_id=snapshot.actor_id,
            snapshot=snapshot.model_dump(),
            event=event.model_dump(),
            memory_bundle=memory_bundle,
            control_mode=control_mode,
            working_memory_state=working_memory_state,
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=background_agenda_state,
            effective_profile=effective_profile,
            need_tension_state=need_tension_state,
        )
        return CharacterInterpretation(
            actor_id=event.actor_id,
            interpreted_summary="recorded runtime reasoning context",
            interpretation_type="state_change",
            salience_score=0.8,
            ambiguity_level="low",
            risk_level="medium",
            opportunity_level="low",
            attention_target=event.target_environment_id,
        )


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


def test_runtime_ingest_character_perceived_event_updates_need_tension_and_dynamic_state() -> None:
    runtime = CharacterAgentRuntime()

    def interpret_stub(*args, **kwargs) -> CharacterInterpretation:
        return CharacterInterpretation(
            actor_id="char_a",
            interpreted_summary="public dismissal near unstable doorway",
            interpretation_type="social_signal",
            salience_score=0.9,
            ambiguity_level="low",
            risk_level="medium",
            opportunity_level="low",
            attention_target="env_unstable_doorway",
        )

    def select_intent_stub(*args, **kwargs) -> CharacterIntentDecision:
        return CharacterIntentDecision(
            actor_id="char_a",
            selected_intent="observe_target",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="pause and observe after the dismissal",
        )

    runtime._l2.interpret_perceived_event = interpret_stub
    runtime._l3.select_intent = select_intent_stub

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=410,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="public_dismissal near spatial_uncertainty doorway",
            source_candidate_event_id="visual_fact:410:char_a",
            target_environment_id="env_unstable_doorway",
        )
    )

    need_state = runtime.get_need_tension_state("char_a")
    dynamic_state = runtime.get_dynamic_state("char_a")

    assert need_state["pressure_sources"] == ["public_dismissal", "spatial_uncertainty"]
    assert need_state["safety_pressure"] > 0.0
    assert need_state["esteem_pressure"] > 0.0
    assert need_state["dominant_need"] == "safety"
    assert dynamic_state["vigilance_level"] > 0.0
    assert dynamic_state["stress_load"] > 0.0
    assert dynamic_state["affect_valence"] < 0.0


def test_runtime_ingest_character_perceived_event_passes_effective_profile_and_need_tension_state_into_l2() -> None:
    runtime = CharacterAgentRuntime()
    authored_profile = runtime._profile_payload("char_a")
    effective_profile = deepcopy(authored_profile)
    effective_profile["need_hierarchy_layer"] = {
        "effective_weights": {
            "safety": 0.91,
            "esteem": 0.67,
        }
    }

    recording_l2 = _RecordingL2(authored_profile)
    runtime._l2 = recording_l2
    runtime._effective_profile_payload = lambda actor_id: deepcopy(effective_profile)

    def select_intent_stub(*args, **kwargs) -> CharacterIntentDecision:
        return CharacterIntentDecision(
            actor_id="char_a",
            selected_intent="observe_target",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="hold position and observe",
        )

    runtime._l3.select_intent = select_intent_stub

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=411,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="public_dismissal near spatial_uncertainty doorway",
            source_candidate_event_id="visual_fact:411:char_a",
            target_environment_id="env_unstable_doorway",
        )
    )

    need_tension_state = runtime.get_need_tension_state("char_a")

    assert recording_l2.prepare_context is not None
    assert recording_l2.interpret_context is not None
    assert recording_l2.prepare_context["profile"] == authored_profile
    assert recording_l2.interpret_context["profile"] == authored_profile
    assert recording_l2.prepare_context["effective_profile"] == effective_profile
    assert recording_l2.interpret_context["effective_profile"] == effective_profile
    assert recording_l2.prepare_context["need_tension_state"] == need_tension_state
    assert recording_l2.interpret_context["need_tension_state"] == need_tension_state
    assert recording_l2.prepare_context["profile"] != recording_l2.prepare_context["effective_profile"]
