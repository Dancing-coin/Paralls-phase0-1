from copy import deepcopy
from pathlib import Path

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


class _RecordingL3:
    def __init__(self) -> None:
        self.select_context: dict[str, object] | None = None

    def select_intent(
        self,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | None = None,
        goal_state_history: list[dict[str, object]] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
    ) -> CharacterIntentDecision:
        self.select_context = {
            "interpretation": interpretation.model_dump(),
            "snapshot": dict(snapshot or {}),
            "profile": dict(profile or {}),
            "effective_profile": dict(effective_profile or {}),
            "memory_bundle": memory_bundle,
            "control_mode": control_mode,
            "working_memory_state": (
                working_memory_state.model_dump()
                if isinstance(working_memory_state, CharacterWorkingMemoryState)
                else dict(working_memory_state or {})
            ),
            "current_goal_state": dict(current_goal_state or {}),
            "goal_state_history": list(goal_state_history or []),
            "supervision_state": dict(supervision_state or {}),
            "unresolved_tensions": list(unresolved_tensions or []),
            "background_agenda_state": dict(background_agenda_state or {}),
            "need_tension_state": dict(need_tension_state or {}),
            "dynamic_state": dict(dynamic_state or {}),
        }
        return CharacterIntentDecision(
            actor_id=interpretation.actor_id,
            selected_intent="observe_target",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="recorded runtime planning context",
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
                "secondary_need": "esteem",
                "motivation_stack": ["safety", "esteem"],
                "pressure_sources": ["public_dismissal", "spatial_uncertainty"],
                "safety_pressure": 0.9,
                "esteem_pressure": 0.4,
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
    assert "secondary_need=esteem" in user_instruction
    assert "motivation_stack=safety|esteem" in user_instruction
    assert "pressure_sources=public_dismissal|spatial_uncertainty" in user_instruction
    assert "pressure_magnitudes=safety=0.9|esteem=0.4" in user_instruction


def test_l2_prompt_policy_includes_positive_affect_state_summary() -> None:
    prompt = CharacterPromptPolicy().build_prompt(
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_a",
            "control_mode": "agent_full_auto",
            "profile": {"identity_core": {"character_id": "char_a"}},
            "snapshot": {"attention_targets": ["char_b"]},
            "memory": {"working_memory": [], "episodic_memories": [], "relational_memories": []},
            "working_memory_state": {
                "dynamic_state": {
                    "actor_id": "char_a",
                    "affect_state": {
                        "trust": 0.6,
                        "gratitude": 0.5,
                        "pride": 0.4,
                        "hope": 0.3,
                    },
                }
            },
            "event": {
                "actor_id": "char_a",
                "event_type": "character_perceived_event",
                "perceived_summary": "char_b thanks char_a",
            },
        },
        route={"route_mode": "online_default", "provider_kind": "online"},
    )

    user_instruction = str(prompt["user_instruction"])

    assert "affect_state=trust=0.6|gratitude=0.5|pride=0.4|hope=0.3" in user_instruction


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
            percept_channel="auditory",
            producer_ts=410,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="char_c speaks from an unclear position",
            source_candidate_event_id="auditory_fact:410:char_c:char_a",
            source_actor_id="char_c",
            target_actor_id="char_a",
            clarity_score=0.72,
            certainty_score=0.68,
        )
    )

    need_state = runtime.get_need_tension_state("char_a")
    dynamic_state = runtime.get_dynamic_state("char_a")

    assert need_state["pressure_sources"] == ["social_engagement", "spatial_uncertainty"]
    assert need_state["safety_pressure"] > 0.0
    assert need_state["dominant_need"] == "safety"
    assert dynamic_state["vigilance_level"] > 0.0
    assert dynamic_state["stress_load"] > 0.0
    assert dynamic_state["affect_valence"] < 0.0


def test_runtime_structured_constraint_snapshot_sets_goal_blocked_need_tension() -> None:
    runtime = CharacterAgentRuntime()

    def interpret_stub(*args, **kwargs) -> CharacterInterpretation:
        return CharacterInterpretation(
            actor_id="char_a",
            interpreted_summary="constraint remains active",
            interpretation_type="state_change",
            salience_score=0.7,
            ambiguity_level="low",
            risk_level="medium",
            opportunity_level="low",
            attention_target="obj_letter",
        )

    def select_intent_stub(*args, **kwargs) -> CharacterIntentDecision:
        return CharacterIntentDecision(
            actor_id="char_a",
            selected_intent="observe_target",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="hold position after the blocked goal",
        )

    runtime._l2.interpret_perceived_event = interpret_stub
    runtime._l3.select_intent = select_intent_stub
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=408,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/fixed_gaze_on_target",
            source_candidate_event_id="visual_fact:408:char_a",
            target_object_id="obj_letter",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )
    runtime.record_settlement_result(
        actor_id="char_a",
        producer_ts=409,
        payload={
            "result_type": "constraint_state_result",
            "constraint_summary": "target is too far away",
            "target_object_id": "obj_letter",
        },
    )

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=411,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/fixed_gaze_on_target",
            source_candidate_event_id="visual_fact:411:char_a",
            target_object_id="obj_letter",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )

    need_state = runtime.get_need_tension_state("char_a")

    assert "goal_blocked" in need_state["pressure_sources"]
    assert need_state["esteem_pressure"] > 0.0


def test_runtime_need_tension_ignores_perceived_summary_trigger_phrases() -> None:
    runtime = CharacterAgentRuntime()

    def interpret_stub(*args, **kwargs) -> CharacterInterpretation:
        return CharacterInterpretation(
            actor_id="char_a",
            interpreted_summary="semantic pressure remains model-owned",
            interpretation_type="state_change",
            salience_score=0.7,
            ambiguity_level="low",
            risk_level="low",
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
            rationale="observe without rule-derived semantic pressure",
        )

    runtime._l2.interpret_perceived_event = interpret_stub
    runtime._l3.select_intent = select_intent_stub

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=412,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="public_dismissal near spatial_uncertainty unstable doorway",
            source_candidate_event_id="visual_fact:412:char_a",
            target_environment_id="env_unstable_doorway",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )

    need_state = runtime.get_need_tension_state("char_a")

    assert need_state["pressure_sources"] == []
    assert need_state["safety_pressure"] == 0.0
    assert need_state["esteem_pressure"] == 0.0


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
            percept_channel="auditory",
            producer_ts=411,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="char_c speaks from an unclear position",
            source_candidate_event_id="auditory_fact:411:char_c:char_a",
            source_actor_id="char_c",
            target_actor_id="char_a",
            clarity_score=0.72,
            certainty_score=0.68,
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


def test_runtime_ingest_character_perceived_event_passes_effective_profile_need_tension_and_dynamic_state_into_l3() -> None:
    runtime = CharacterAgentRuntime()
    authored_profile = runtime._profile_payload("char_a")
    effective_profile = deepcopy(authored_profile)
    effective_profile["need_hierarchy_layer"] = {
        "effective_weights": {
            "safety": 0.91,
            "esteem": 0.67,
        }
    }

    runtime._l2 = _RecordingL2(authored_profile)
    recording_l3 = _RecordingL3()
    runtime._l3 = recording_l3
    runtime._effective_profile_payload = lambda actor_id: deepcopy(effective_profile)

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=412,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="char_c speaks from an unclear position",
            source_candidate_event_id="auditory_fact:412:char_c:char_a",
            source_actor_id="char_c",
            target_actor_id="char_a",
            clarity_score=0.72,
            certainty_score=0.68,
        )
    )

    need_tension_state = runtime.get_need_tension_state("char_a")
    dynamic_state = runtime.get_dynamic_state_record("char_a").model_dump()

    assert recording_l3.select_context is not None
    assert recording_l3.select_context["profile"] == authored_profile
    assert recording_l3.select_context["effective_profile"] == effective_profile
    assert recording_l3.select_context["need_tension_state"] == need_tension_state
    assert recording_l3.select_context["dynamic_state"] == dynamic_state
    assert "affect_state" in recording_l3.select_context["dynamic_state"]
    working_dynamic_state = recording_l3.select_context["working_memory_state"]["dynamic_state"]
    for key, value in dynamic_state.items():
        assert working_dynamic_state[key] == value


def test_runtime_persists_and_rehydrates_need_tension_state_from_timeline(tmp_path: Path) -> None:
    storage_root = tmp_path / "runtime_store"
    runtime = CharacterAgentRuntime(storage_root=storage_root)

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

    runtime._l2.interpret_perceived_event = interpret_stub
    runtime._l3 = _RecordingL3()

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=413,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="char_c speaks from an unclear position",
            source_candidate_event_id="auditory_fact:413:char_c:char_a",
            source_actor_id="char_c",
            target_actor_id="char_a",
            clarity_score=0.72,
            certainty_score=0.68,
        )
    )

    before_restart = runtime.get_need_tension_state("char_a")
    timeline = runtime.get_session_timeline("char_a")

    assert any(entry["event_type"] == "need_tension_state_event" for entry in timeline)

    rehydrated = CharacterAgentRuntime(storage_root=storage_root)

    assert rehydrated.get_need_tension_state("char_a") == before_restart
