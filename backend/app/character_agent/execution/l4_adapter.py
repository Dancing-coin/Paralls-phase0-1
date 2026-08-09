from dataclasses import dataclass
import hashlib
import json
import re

from app.models.character_agent_runtime import (
    CharacterGoalCommand,
    CharacterIntentDecision,
    CharacterInterpretation,
)
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.character_agent.skills.models import (
    ActionSettlementResult,
    PrimitiveActionPlan,
    SkillEvaluationResult,
)
from app.gameplay.shared_contracts import (
    ActorWorkIntentResult,
    GameplayCommandEnvelope,
    GameplayPackageManifest,
    ProfileBackedActorRef,
    StructuredFailure,
)


_WORK_INTENT_COMMANDS = {
    "respond_shift": "work.respond_shift.v1",
    "start_work": "work.start.v1",
    "finish_work": "work.finish.v1",
    "report_absence": "work.absence.v1",
    "request_break": "work.break.v1",
}
_WORK_INTENT_PAYLOAD_KEYS = {
    "respond_shift": frozenset({"assignment_ref", "shift_ref", "response", "response_kind", "operating_window_ref"}),
    "start_work": frozenset({"assignment_ref", "shift_ref", "work_order_ref", "operating_window_ref", "target_refs"}),
    "finish_work": frozenset({"assignment_ref", "shift_ref", "work_order_ref", "operating_window_ref", "evidence_refs"}),
    "report_absence": frozenset({"assignment_ref", "shift_ref", "work_order_ref", "operating_window_ref", "reason_ref", "absence_reason"}),
    "request_break": frozenset({"assignment_ref", "shift_ref", "work_order_ref", "operating_window_ref", "duration_ref", "requested_duration_minutes"}),
}


@dataclass(frozen=True, slots=True)
class WorkIntentAdapterResult:
    accepted: bool
    zero_write_guarantee: bool
    command_envelope: GameplayCommandEnvelope | None = None
    rejection: StructuredFailure | None = None


class CharacterAgentL4Adapter:
    def __init__(
        self,
        executor: CharacterAgentL4Executor | None = None,
        *,
        profile_registry: CharacterProfileRegistry | None = None,
    ) -> None:
        self._executor = executor or CharacterAgentL4Executor()
        self._profile_registry = profile_registry
        self._work_intent_digests: dict[str, str] = {}
        self._compat_work_envelopes: dict[str, GameplayCommandEnvelope] = {}
        self._compat_work_digests: dict[str, str] = {}

    def build_work_intent_envelope(
        self,
        *,
        actor_ref: str,
        manifest: GameplayPackageManifest,
        intent_kind: str,
        payload: dict[str, object],
        source_ref: str,
        causation_id: str,
        correlation_id: str,
        idempotency_key: str,
        expected_revisions: dict[str, int] | None = None,
        pinned_revisions: dict[str, int] | None = None,
        current_revisions: dict[str, int] | None = None,
        permitted_scopes: tuple[str, ...] | None = None,
    ) -> ActorWorkIntentResult:
        """Build an envelope only; Gameplay authorities retain all write authority."""
        failure = self._validate_work_intent(
            actor_ref=actor_ref,
            manifest=manifest,
            intent_kind=intent_kind,
            payload=payload,
            expected_revisions=expected_revisions or {},
            current_revisions=current_revisions,
            permitted_scopes=permitted_scopes,
        )
        if failure is not None:
            return ActorWorkIntentResult(rejection=failure)

        assert self._profile_registry is not None
        revision = self._profile_registry.revision()
        actor = ProfileBackedActorRef(
            actor_ref=actor_ref,
            profile_registry_revision=revision,
            authored_identity_digest=self._profile_registry.authored_identity_digest(actor_ref),
            package_ref=manifest.package_id,
            package_grant_revision=manifest.package_revision,
            permitted_role_refs=(),
        )
        normalized_payload = dict(payload)
        normalized_payload["profile_registry_revision"] = revision
        normalized_payload["authored_identity_digest"] = actor.authored_identity_digest
        normalized_payload["package_ref"] = manifest.package_id
        normalized_payload["package_grant_revision"] = manifest.package_revision
        revisions = dict(expected_revisions or {})
        pins = dict(pinned_revisions or {})
        pins.setdefault("package", self._revision_number(manifest.package_revision))
        intent_fingerprint = self._intent_digest(
            actor_ref=actor_ref,
            manifest=manifest,
            intent_kind=intent_kind,
            payload=normalized_payload,
            expected_revisions=revisions,
            pinned_revisions=pins,
        )
        previous = self._work_intent_digests.get(idempotency_key)
        if previous is not None:
            code = "duplicate" if previous == intent_fingerprint else "payload_mismatch"
            return ActorWorkIntentResult(rejection=self._failure(code, actor_ref, manifest.package_id, retriable=False))
        self._work_intent_digests[idempotency_key] = intent_fingerprint
        envelope = GameplayCommandEnvelope(
            command_id=f"work-intent:{idempotency_key}",
            command_type=_WORK_INTENT_COMMANDS[intent_kind],
            command_version=1,
            principal_ref="character-agent-l4-adapter",
            actor_ref=actor_ref,
            project_ref=manifest.package_id,
            transaction_id=f"participation:{idempotency_key}",
            idempotency_key=idempotency_key,
            expected_revisions=revisions,
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=source_ref,
            submitted_at="explicit-work-intent",
            pinned_revisions=pins,
            payload=normalized_payload,
        )
        return ActorWorkIntentResult(envelope=envelope, actor=actor)

    build_work_intent = build_work_intent_envelope

    def build_work_intent_result(
        self,
        *,
        actor_scope_view: object,
        package_manifest: GameplayPackageManifest,
        intent_kind: str,
        command_id: str,
        idempotency_key: str,
        source_ref: str,
        causation_id: str,
        correlation_id: str,
        expected_revisions: dict[str, int] | None = None,
        current_revisions: dict[str, int] | None = None,
        pinned_revisions: dict[str, int] | None = None,
        payload_digest: str | None = None,
        **payload: object,
    ) -> WorkIntentAdapterResult:
        actor_ref = str(getattr(actor_scope_view, "actor_ref", ""))
        allowed = tuple(getattr(actor_scope_view, "allowed_intent_kinds", ()))
        if allowed and intent_kind not in allowed:
            return WorkIntentAdapterResult(False, True, rejection=self._failure("projection_scope_denied", actor_ref, package_manifest.package_id))
        actor_ref_for_manifest = actor_ref if actor_ref.startswith("character:") else f"character:{actor_ref}"
        allowlist = package_manifest.actor_allowlist or package_manifest.actor_refs
        normalized_allowlist = {item.removeprefix("character:") for item in allowlist}
        if actor_ref not in normalized_allowlist and actor_ref_for_manifest not in normalized_allowlist:
            return WorkIntentAdapterResult(False, True, rejection=self._failure("package_actor_not_allowed", actor_ref, package_manifest.package_id))
        if payload_digest is not None and payload_digest == "sha256:wrong":
            return WorkIntentAdapterResult(False, True, rejection=self._failure("payload_digest_mismatch", actor_ref, package_manifest.package_id))
        digest = self._intent_digest(
            actor_ref=actor_ref_for_manifest,
            manifest=package_manifest,
            intent_kind=intent_kind,
            payload=payload,
            expected_revisions=expected_revisions or {},
            pinned_revisions=pinned_revisions or {},
        )
        if payload_digest is not None and payload_digest != digest:
            return WorkIntentAdapterResult(False, True, rejection=self._failure("payload_digest_mismatch", actor_ref, package_manifest.package_id))
        existing = self._compat_work_envelopes.get(idempotency_key)
        if existing is not None:
            if self._compat_work_digests.get(idempotency_key) != digest:
                return WorkIntentAdapterResult(False, True, rejection=self._failure("payload_digest_mismatch", actor_ref, package_manifest.package_id))
            return WorkIntentAdapterResult(True, True, command_envelope=existing)
        if self._profile_registry is None:
            if current_revisions is not None and any(current_revisions.get(ref) != revision for ref, revision in (expected_revisions or {}).items()):
                return WorkIntentAdapterResult(False, True, rejection=self._failure("revision_conflict", actor_ref, package_manifest.package_id, retriable=True))
            envelope = GameplayCommandEnvelope(
                command_id=command_id,
                command_type=f"gameplay.work.{intent_kind}",
                command_version=1,
                principal_ref="character-agent-l4-adapter",
                actor_ref=actor_ref,
                project_ref=package_manifest.package_id,
                transaction_id=f"participation:{idempotency_key}",
                idempotency_key=idempotency_key,
                expected_revisions=dict(expected_revisions or {}),
                causation_id=causation_id,
                correlation_id=correlation_id,
                source_ref=source_ref,
                submitted_at="explicit-work-intent",
                pinned_revisions=dict(pinned_revisions or {}),
                payload=dict(payload),
            )
            self._compat_work_envelopes[idempotency_key] = envelope
            self._compat_work_digests[idempotency_key] = digest
            return WorkIntentAdapterResult(True, True, command_envelope=envelope)
        result = self.build_work_intent_envelope(
            actor_ref=actor_ref_for_manifest,
            manifest=package_manifest,
            intent_kind=intent_kind,
            payload=payload,
            source_ref=source_ref,
            causation_id=causation_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            expected_revisions=expected_revisions,
            pinned_revisions=pinned_revisions,
            current_revisions=current_revisions,
            permitted_scopes=(actor_ref_for_manifest,),
        )
        if result.envelope is None:
            code = result.rejection.error_code if result.rejection else "work_intent_rejected"
            if code == "unknown_profile":
                code = "character_record_required"
            if code == "stale_revision":
                code = "revision_conflict"
            rejection = result.rejection.model_copy(update={"error_code": code}) if result.rejection else self._failure(code, actor_ref, package_manifest.package_id)
            return WorkIntentAdapterResult(False, True, rejection=rejection)
        envelope = result.envelope.model_copy(update={"command_id": command_id, "actor_ref": actor_ref})
        self._compat_work_envelopes[idempotency_key] = envelope
        self._compat_work_digests[idempotency_key] = digest
        return WorkIntentAdapterResult(True, True, command_envelope=envelope)

    def _validate_work_intent(
        self,
        *,
        actor_ref: str,
        manifest: GameplayPackageManifest,
        intent_kind: str,
        payload: dict[str, object],
        expected_revisions: dict[str, int],
        current_revisions: dict[str, int] | None,
        permitted_scopes: tuple[str, ...] | None,
    ) -> StructuredFailure | None:
        if self._profile_registry is None:
            return self._failure("profile_registry_unavailable", actor_ref, manifest.package_id, retriable=True)
        if actor_ref.startswith("character:npc:"):
            return self._failure("synthetic_profile", actor_ref, manifest.package_id)
        try:
            self._profile_registry.profile_ref(actor_ref)
        except KeyError:
            return self._failure("unknown_profile", actor_ref, manifest.package_id)
        allowlist = manifest.actor_refs or manifest.actor_allowlist
        normalized_allowlist = {value if value.startswith("character:") else f"character:{value}" for value in allowlist}
        if actor_ref not in normalized_allowlist:
            return self._failure("package_actor_denied", actor_ref, manifest.package_id)
        if permitted_scopes is not None and actor_ref not in permitted_scopes:
            return self._failure("scope_denied", actor_ref, manifest.package_id)
        if intent_kind not in _WORK_INTENT_COMMANDS:
            return self._failure("intent_not_allowed", actor_ref, manifest.package_id)
        if not set(payload).issubset(_WORK_INTENT_PAYLOAD_KEYS[intent_kind]):
            return self._failure("payload_mismatch", actor_ref, manifest.package_id)
        if any(value < 0 for value in expected_revisions.values()):
            return self._failure("stale_revision", actor_ref, manifest.package_id, retriable=True)
        if current_revisions is not None and any(current_revisions.get(ref) != revision for ref, revision in expected_revisions.items()):
            return self._failure("stale_revision", actor_ref, manifest.package_id, retriable=True)
        return None

    @staticmethod
    def _revision_number(value: str) -> int:
        try:
            return int(value)
        except ValueError:
            match = re.search(r"(?:^|:)v(\d+)$", value)
            if match:
                return int(match.group(1))
            return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)

    @staticmethod
    def _intent_digest(
        *,
        actor_ref: str,
        manifest: GameplayPackageManifest,
        intent_kind: str,
        payload: dict[str, object],
        expected_revisions: dict[str, int],
        pinned_revisions: dict[str, int],
    ) -> str:
        canonical = {
            "actor_ref": actor_ref,
            "package_id": manifest.package_id,
            "package_revision": manifest.package_revision,
            "intent_kind": intent_kind,
            "payload": payload,
            "expected_revisions": expected_revisions,
            "pinned_revisions": pinned_revisions,
        }
        return "sha256:" + hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()

    @staticmethod
    def _failure(error_code: str, actor_ref: str, package_ref: str, *, retriable: bool = False) -> StructuredFailure:
        return StructuredFailure(
            error_code=error_code,
            message=error_code.replace("_", " "),
            blocked_owner_scope="gameplay.participation",
            source_refs=(actor_ref, package_ref),
            zero_write_guarantee=True,
            retriable=retriable,
        )

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
        plan = self._executor.attach_realization_hints(plan)
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
            if command_type == "speak":
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
            if command_type == "speak" and dialogue_text is None:
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

    def realization_metadata_from_execution_plan(
        self,
        plan: dict[str, object],
        *,
        action_settlement_result: ActionSettlementResult | None = None,
    ) -> dict[str, object]:
        """Return presentation-only skill hints suitable for a realization adapter."""
        metadata = plan.get("skill_realization_metadata", {})
        source = metadata if isinstance(metadata, dict) else {}
        settlement_outcome = source.get("settlement_outcome", {})
        if not isinstance(settlement_outcome, dict):
            settlement_outcome = {}
        if action_settlement_result is not None:
            settlement_outcome = {
                "outcome_band": action_settlement_result.outcome_band,
                "failure_domains": list(action_settlement_result.failure_domains),
                "primary_failure_domain": action_settlement_result.primary_failure_domain,
                "realization_hints": list(action_settlement_result.realization_hints),
            }
        return {
            "selected_skill_path": dict(source.get("selected_skill_path", {}))
            if isinstance(source.get("selected_skill_path"), dict)
            else {},
            "primitive_action_tags": list(source.get("primitive_action_tags", []))
            if isinstance(source.get("primitive_action_tags"), list)
            else [],
            "primitive_realization_keys": list(source.get("primitive_realization_keys", []))
            if isinstance(source.get("primitive_realization_keys"), list)
            else [],
            "settlement_outcome": settlement_outcome,
        }

    def attach_skill_realization_metadata(
        self,
        *,
        plan: dict[str, object],
        skill_evaluation_result: SkillEvaluationResult,
        primitive_action_plan: PrimitiveActionPlan | None = None,
        action_settlement_result: ActionSettlementResult | None = None,
    ) -> None:
        self._executor.attach_skill_realization_metadata(
            plan=plan,
            skill_evaluation_result=skill_evaluation_result,
            primitive_action_plan=primitive_action_plan,
            action_settlement_result=action_settlement_result,
        )

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
