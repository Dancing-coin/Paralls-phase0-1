from app.models.character_agent_runtime import (
    CharacterGoalCommand,
    CharacterIntentDecision,
    CharacterInterpretation,
)
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor


class CharacterAgentL4Adapter:
    def __init__(self, executor: CharacterAgentL4Executor | None = None) -> None:
        self._executor = executor or CharacterAgentL4Executor()

    def build_commands(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> list[CharacterGoalCommand]:
        plan = self._executor.build_execution_plan(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
        )
        return self.build_commands_from_execution_plan(plan)

    def command_to_execution_payload(self, command: CharacterGoalCommand) -> dict[str, object]:
        if command.execution_payload is not None:
            return command.execution_payload

        target_ref = command.target_actor_id or command.target_object_id or command.target_environment_id or ""
        snapshot = CharacterPrivateWorldSnapshot(
            actor_id=command.actor_id,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=int(command.producer_ts or 0),
            updated_at=int(command.producer_ts or 0),
            attention_targets=[target_ref] if target_ref else [],
        )
        interpretation = CharacterInterpretation(
            actor_id=command.actor_id,
            interpreted_summary=command.dialogue_text or command.command_type,
            interpretation_type="execution_bridge",
            salience_score=1.0,
            ambiguity_level="low",
            risk_level="low",
            opportunity_level="low",
            attention_target=target_ref or None,
            inner_prompt_candidate=command.command_type,
        )
        decision = CharacterIntentDecision(
            actor_id=command.actor_id,
            selected_intent=command.command_type,
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale=command.command_type,
        )
        return self._executor.build_execution_plan(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
        )

    def build_commands_from_execution_plan(self, plan: dict[str, object]) -> list[CharacterGoalCommand]:
        requested_actions = []
        bundle = plan.get("action_request_bundle", {})
        if isinstance(bundle, dict):
            raw_actions = bundle.get("requested_actions", [])
            if isinstance(raw_actions, list):
                requested_actions = [action for action in raw_actions if isinstance(action, dict)]

        first_frame = {}
        frames = plan.get("actor_control_frames", [])
        if isinstance(frames, list) and frames and isinstance(frames[0], dict):
            first_frame = frames[0]

        actor_id = str(plan.get("actor_id", "") or first_frame.get("actor_id", "") or "")
        producer_ts = int(first_frame.get("producer_ts", 0) or 0)
        causation_id = str(first_frame.get("causation_id", "") or f"character_agent:{producer_ts}")
        correlation_id = str(first_frame.get("correlation_id", "") or f"character_agent:{producer_ts}")
        target_actor_id = None
        target_object_id = None
        target_environment_id = None
        command_type = "observe"
        role_state_hint = self._map_role_state_hint(str(first_frame.get("action", "") or ""))
        physiology_hint = None
        dialogue_text = None

        if requested_actions:
            action = requested_actions[0]
            request_type = str(action.get("request_type", "") or "")
            command_type = self._map_request_type_to_command_type(request_type)
            role_state_hint = self._map_request_type_to_role_state_hint(request_type)
            target_actor_id = action.get("target_actor_id") if str(action.get("target_actor_id", "") or "") else None
            target_object_id = action.get("target_object_id") if str(action.get("target_object_id", "") or "") else None
            target_environment_id = action.get("target_environment_id") if str(action.get("target_environment_id", "") or "") else None
            dialogue_text_value = str(action.get("content", "") or "")
            dialogue_text = dialogue_text_value or None
        else:
            target_ref = str(first_frame.get("target_ref", "") or "")
            command_type = self._map_command_type(str(first_frame.get("action", "") or "observe"))
            if target_ref.startswith("char_"):
                target_actor_id = target_ref
            elif target_ref.startswith("obj_"):
                target_object_id = target_ref
            elif target_ref.startswith("env_"):
                target_environment_id = target_ref

        presentation_plan = plan.get("presentation_plan", {})
        if isinstance(presentation_plan, dict):
            physiology_hint_value = str(presentation_plan.get("physiology_hint", "") or "")
            physiology_hint = physiology_hint_value or None
            if physiology_hint is None:
                physiology_state = presentation_plan.get("physiology_state", {})
                if isinstance(physiology_state, dict):
                    physiology_hint_value = str(physiology_state.get("state_band", "") or "")
                    physiology_hint = physiology_hint_value or None
            if role_state_hint is None:
                role_state_hint = self._map_role_state_hint(str(presentation_plan.get("action_state", {}).get("requested_action", "") or ""))
            if dialogue_text is None:
                speech_state = presentation_plan.get("speech_state", {})
                if isinstance(speech_state, dict):
                    dialogue_text_value = str(speech_state.get("utterance_request", "") or "")
                    dialogue_text = dialogue_text_value or None

        return [
            CharacterGoalCommand(
                actor_id=actor_id,
                command_type=command_type,
                ttl_ms=1000,
                causation_id=causation_id,
                correlation_id=correlation_id,
                producer_ts=producer_ts,
                target_actor_id=target_actor_id,
                target_object_id=target_object_id,
                target_environment_id=target_environment_id,
                dialogue_text=dialogue_text,
                role_state_hint=role_state_hint,
                physiology_hint=physiology_hint,
                execution_payload=plan,
            )
        ]

    def _map_request_type_to_command_type(self, request_type: str) -> str:
        if request_type in {"speak_public", "speak_private", "share_info", "withhold"}:
            return "speak"
        if request_type in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"}:
            return "approach"
        if request_type == "interact":
            return "observe"
        return "observe"

    def _map_request_type_to_role_state_hint(self, request_type: str) -> str | None:
        if request_type == "interact":
            return "inspect"
        if request_type in {"speak_public", "speak_private", "share_info", "withhold"}:
            return "speak"
        if request_type in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"}:
            return "approach"
        return None

    def _map_command_type(self, selected_intent: str) -> str:
        if selected_intent == "brief_dialogue_response":
            return "speak"
        if selected_intent == "reposition_step":
            return "approach"
        if selected_intent in {"attention_shift", "observe_target", "role_state_hint", "physiology_hint"}:
            return "observe"
        if selected_intent in {"speak_public", "speak_private", "share_info", "withhold"}:
            return "speak"
        if selected_intent in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"}:
            return "approach"
        return "observe"

    def _map_role_state_hint(self, action_name: str) -> str | None:
        if action_name in {"observe_target", "observe"}:
            return "observe"
        if action_name in {"attention_shift"}:
            return "alert"
        if action_name in {"physiology_hint"}:
            return "physiology_hint"
        if action_name in {"brief_dialogue_response", "speak_public", "speak_private"}:
            return "speak"
        if action_name in {"inspect_object", "interact"}:
            return "inspect"
        if action_name in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"}:
            return "approach"
        return None
