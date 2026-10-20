from collections.abc import Callable, Mapping

from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.config import settings

DialogueContextProvider = Callable[[str], Mapping[str, object]]


class DialogueService:
    def __init__(
        self,
        gateway: CharacterModelGateway | None = None,
        context_provider: DialogueContextProvider | None = None,
    ) -> None:
        self._gateway = gateway or CharacterModelGateway()
        self._context_provider = context_provider

    def prepare_dialogue(self, *, actor_id: str, target_actor_id: str, content: str,
                         agent_initiated: bool = False,
                         cognition_context: Mapping[str, object] | None = None) -> bytes:
        """仅 owner 读取上下文，provider 仅消费冻结请求。"""
        context = self._context(actor_id=actor_id, content=content, target_actor_id=target_actor_id,
            control_mode="agent_initiated_utterance" if agent_initiated else "dialogue_service",
            intent_type="agent_initiated_utterance" if agent_initiated else "dialogue_submit")
        if cognition_context is not None:
            from app.character_agent.cognition.capability_envelope import CapabilityEnvelope
            from app.character_agent.cognition.cognition_policy import CognitionPolicy

            raw_envelope = cognition_context.get("capability_envelope")
            raw_policy = cognition_context.get("cognition_policy")
            for value, digest in ((raw_envelope, "envelope_digest"), (raw_policy, "policy_digest")):
                if not isinstance(value, Mapping) or not isinstance(value.get(digest), str) or not value[digest]:
                    raise ValueError("dialogue_cognition_contract_digest_missing")
            envelope = CapabilityEnvelope.model_validate(raw_envelope)
            policy = CognitionPolicy.model_validate(raw_policy)
            turn_id = cognition_context.get("turn_id")
            if not isinstance(turn_id, str) or not envelope.source_refs:
                raise ValueError("dialogue_cognition_contract_source_missing")
            policy.validate_envelope(envelope, actor_id=actor_id, turn_id=turn_id,
                turn_actor_id=actor_id, policy_revision=envelope.revision_pins.get("policy_revision", ""),
                source_event_ref=envelope.source_refs[0])
            context.update(capability_envelope=envelope.model_dump(mode="json"),
                cognition_policy=policy.model_dump(mode="json"), turn_id=turn_id)
        request = self._gateway.prepare_run_request(
            task_kind="dialogue_generation",
            context=context,
            route_override="local_only" if settings.dialogue_mode == "stub" else None,
        )
        return CharacterModelGateway.freeze_prepared_request(request)

    def generate_reply(self, actor_id: str, content: str) -> tuple[str, str]:
        output = self._gateway.complete_prepared_request(self.prepare_dialogue(
            actor_id=actor_id, target_actor_id=actor_id, content=content))
        return str(output.get("content", "") or ""), str(output.get("tone", "") or "neutral")

    def generate_utterance(self, actor_id: str, target_actor_id: str, content: str) -> tuple[str, str]:
        output = self._gateway.complete_prepared_request(self.prepare_dialogue(
            actor_id=actor_id, target_actor_id=target_actor_id, content=content, agent_initiated=True))
        return str(output.get("content", "") or ""), str(output.get("tone", "") or "neutral")

    def stream_reply(self, actor_id: str, content: str, *, cancelled):
        yield from self._gateway.stream_prepared_request(self.prepare_dialogue(
            actor_id=actor_id, target_actor_id=actor_id, content=content), cancelled=cancelled)

    def stream_utterance(self, actor_id: str, target_actor_id: str, content: str, *, cancelled):
        yield from self._gateway.stream_prepared_request(self.prepare_dialogue(
            actor_id=actor_id, target_actor_id=target_actor_id, content=content, agent_initiated=True), cancelled=cancelled)

    def _context(
        self,
        *,
        actor_id: str,
        content: str,
        target_actor_id: str,
        control_mode: str,
        intent_type: str,
    ) -> dict[str, object]:
        context: dict[str, object] = {
            "actor_id": actor_id,
            "control_mode": control_mode,
            "snapshot": {},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "content": content,
                "target_actor_id": target_actor_id,
                "intent_type": intent_type,
            },
        }
        if self._context_provider is None:
            return context
        runtime_context = self._context_provider(actor_id)
        if not isinstance(runtime_context, Mapping):
            return context
        for key, value in runtime_context.items():
            if key in {"actor_id", "control_mode", "event"}:
                continue
            context[str(key)] = value
        return context
