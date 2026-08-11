from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import OwnerAuthorizedFragment
from app.gameplay.p5.contracts import P5ResolutionRequest, P5ResolutionResult
from app.gameplay.p5.registry import P5PolicyRegistry
from app.gameplay.shared_contracts import GameplayCommandEnvelope, SettlementPlan


_PRINCIPAL = "authority:p5:quest-evidence"
_EVIDENCE_EVENT = "gameplay.quest.evidence_registered"
_OBJECTIVE_EVENT = "gameplay.quest.objective_transitioned"
_TRANSITION_REF = "transition:quest:evidence_registered"


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class QuestEvidenceAuthorityResult:
    resolution: P5ResolutionResult
    receipt: Any | None
    settlement_plan: SettlementPlan | None


class QuestEvidenceAuthority:
    def __init__(self, *, registry: P5PolicyRegistry, store: GameplayEventStore) -> None:
        self._registry = registry
        self._store = store

    def resolve(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        reward_fragments: tuple[OwnerAuthorizedFragment, ...] = (),
        now: str,
    ) -> QuestEvidenceAuthorityResult:
        digest = self._request_digest(command=command, request=request, reward_fragments=reward_fragments)
        existing = self._store.get_idempotency_record(_PRINCIPAL, command.idempotency_key)
        if existing is not None:
            if existing.payload_digest == digest:
                receipt = self._store.get_by_idempotency(_PRINCIPAL, command.idempotency_key)
                return self._committed_result(receipt, duplicate=True)
            return self._rejected("idempotency_key_reused")

        try:
            request = self._registry.validate_request(request)
        except ValueError as exc:
            return self._rejected(str(exc))

        payload = dict(command.payload)
        package = self._registry.require_package(request.package_ref, request.package_revision)
        objective = self._require_objective(package=package, objective_ref=str(payload.get("objective_ref", "")))
        provider = self._registry.require_provider(request.evidence_provider_ref)
        failure = self._validate_inputs(
            command=command,
            request=request,
            package=package,
            objective=objective,
            provider=provider,
            payload=payload,
            now=now,
        )
        if failure is not None:
            return self._rejected(failure)

        reward_failure = self._validate_reward_fragments(
            reward_fragments=reward_fragments,
            request=request,
            command=command,
        )
        if reward_failure is not None:
            return self._rejected(reward_failure)

        settlement_plan = SettlementPlan(
            plan_id=f"settlement:{command.command_id}",
            command_id=command.command_id,
            expected_revision_vector=dict(request.expected_revisions.entries),
            proposals=(),
            event_mapping={
                _EVIDENCE_EVENT: payload["evidence_stream_ref"],
                _OBJECTIVE_EVENT: payload["quest_stream_ref"],
            },
            idempotency_key=command.idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
        )
        evidence_event_entry = self._registry.require_event(_EVIDENCE_EVENT, 1)
        evidence_schema_pin = self._registry.require_schema(
            evidence_event_entry.schema_ref,
            evidence_event_entry.schema_version,
        )
        objective_event_entry = self._registry.require_event(_OBJECTIVE_EVENT, 1)
        objective_schema_pin = self._registry.require_schema(
            objective_event_entry.schema_ref,
            objective_event_entry.schema_version,
        )
        satisfied_prerequisites = list(payload.get("satisfied_prerequisite_fact_refs") or ())
        receipt = self._store.append_batch(
            {
                "transaction_id": command.transaction_id or f"transaction:{command.command_id}",
                "command_id": command.command_id,
                "expected_stream_revisions": dict(request.expected_revisions.entries),
                "read_stream_revisions": dict(request.read_set_revisions.entries),
                "pinned_revisions": dict(command.pinned_revisions),
                "events": [
                    {
                        "event_id": f"event:{command.command_id}:evidence_registered",
                        "event_type": _EVIDENCE_EVENT,
                        "schema_version": 1,
                        "stream_id": payload["evidence_stream_ref"],
                        "stream_revision": 0,
                        "global_sequence": 0,
                        "transaction_id": command.transaction_id or f"transaction:{command.command_id}",
                        "command_id": command.command_id,
                        "causation_id": command.causation_id,
                        "correlation_id": command.correlation_id,
                        "visibility_policy": payload["visibility"],
                        "payload": {
                            "request_ref": request.request_ref,
                            "objective_ref": payload["objective_ref"],
                            "evidence_ref": payload["evidence_ref"],
                            "evidence_kind_ref": payload["evidence_kind_ref"],
                            "provider_ref": request.evidence_provider_ref,
                            "provenance_source_ref": request.provenance_source_ref,
                            "subject_ref": request.subject_scope_ref,
                            "visibility": payload["visibility"],
                            "observed_at": payload["observed_at"],
                            "registry_ref": request.registry_ref,
                            "registry_revision": request.registry_revision,
                            "registry_digest": request.registry_digest,
                            "package_ref": package.package_ref,
                            "package_revision": package.package_revision,
                            "package_digest": package.package_digest,
                            "schema_ref": evidence_schema_pin.schema_ref,
                            "schema_version": evidence_schema_pin.schema_version,
                            "schema_digest": evidence_schema_pin.schema_digest,
                            "satisfied_prerequisite_fact_refs": satisfied_prerequisites,
                        },
                    },
                    {
                        "event_id": f"event:{command.command_id}:objective_transitioned",
                        "event_type": _OBJECTIVE_EVENT,
                        "schema_version": 1,
                        "stream_id": payload["quest_stream_ref"],
                        "stream_revision": 0,
                        "global_sequence": 0,
                        "transaction_id": command.transaction_id or f"transaction:{command.command_id}",
                        "command_id": command.command_id,
                        "causation_id": command.causation_id,
                        "correlation_id": command.correlation_id,
                        "visibility_policy": payload["visibility"],
                        "payload": {
                            "request_ref": request.request_ref,
                            "objective_ref": payload["objective_ref"],
                            "quest_instance_ref": payload["quest_instance_ref"],
                            "quest_stream_ref": payload["quest_stream_ref"],
                            "transition_ref": payload["transition_ref"],
                            "evidence_ref": payload["evidence_ref"],
                            "provenance_source_ref": request.provenance_source_ref,
                            "subject_ref": request.subject_scope_ref,
                            "visibility": payload["visibility"],
                            "registry_ref": request.registry_ref,
                            "registry_revision": request.registry_revision,
                            "registry_digest": request.registry_digest,
                            "package_ref": package.package_ref,
                            "package_revision": package.package_revision,
                            "package_digest": package.package_digest,
                            "schema_ref": objective_schema_pin.schema_ref,
                            "schema_version": objective_schema_pin.schema_version,
                            "schema_digest": objective_schema_pin.schema_digest,
                            "satisfied_prerequisite_fact_refs": satisfied_prerequisites,
                        },
                    },
                ],
                "idempotency_record": {
                    "principal_ref": _PRINCIPAL,
                    "idempotency_key": command.idempotency_key,
                    "payload_digest": digest,
                },
                "owner_fragments": [fragment.model_dump(mode="json") for fragment in reward_fragments],
                "outbox_entries": [],
                "result_digest": digest,
                "projection_refresh_hints": [],
            }
        )
        if not receipt.committed:
            return self._rejected(receipt.failure.error_code if receipt.failure is not None else "append_batch_failed")
        return self._committed_result(receipt, duplicate=receipt.idempotency_status == "duplicate_replayed", settlement_plan=settlement_plan)

    def _request_digest(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        reward_fragments: tuple[OwnerAuthorizedFragment, ...],
    ) -> str:
        return _digest(
            {
                "command": command.model_dump(mode="json"),
                "request": request.model_dump(mode="json"),
                "reward_fragments": [
                    fragment.model_dump(mode="json")
                    for fragment in sorted(reward_fragments, key=lambda item: item.fragment_id)
                ],
            }
        )

    def _require_objective(self, *, package, objective_ref: str):
        for objective in package.objectives:
            if objective.objective_ref == objective_ref:
                return objective
        raise ValueError("p5_objective_unknown")

    def _validate_inputs(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        package,
        objective,
        provider,
        payload: dict[str, Any],
        now: str,
    ) -> str | None:
        if payload.get("provider_ref") != request.evidence_provider_ref:
            return "p5_provider_provenance_mismatch"
        if payload.get("provenance_source_ref") != request.provenance_source_ref:
            return "p5_provider_provenance_mismatch"
        if payload.get("subject_ref") != request.subject_scope_ref or command.actor_ref != request.subject_scope_ref:
            return "p5_subject_scope_mismatch"
        if payload.get("evidence_kind_ref") not in objective.accepted_evidence_kind_refs:
            return "p5_evidence_kind_rejected"
        if payload.get("evidence_kind_ref") not in provider.allowed_evidence_kinds:
            return "p5_evidence_kind_rejected"
        if payload.get("package_ref") != package.package_ref or payload.get("package_revision") != package.package_revision:
            return "p5_package_digest_pin_mismatch"
        if payload.get("package_digest") != package.package_digest:
            return "p5_package_digest_pin_mismatch"
        satisfied_prerequisites = set(payload.get("satisfied_prerequisite_fact_refs") or ())
        if not set(objective.prerequisite_fact_refs).issubset(satisfied_prerequisites):
            return "p5_prerequisite_unsatisfied"
        if payload.get("transition_ref") != _TRANSITION_REF:
            return "p5_transition_disallowed"
        if "visibility" not in payload or not payload.get("visibility"):
            return "p5_evidence_visibility_missing"
        if payload["visibility"] != objective.visibility:
            return "p5_evidence_hidden"
        if any(event.visibility != payload["visibility"] for event in request.proposed_events):
            return "p5_evidence_hidden"
        if "expires_at" not in payload:
            return "p5_evidence_expiry_missing"
        expires_at = _parse_time(payload.get("expires_at"))
        now_dt = _parse_time(now)
        if expires_at is not None and now_dt is not None and expires_at <= now_dt:
            return "p5_evidence_expired"
        proposed_events = self._required_proposed_events(request)
        if proposed_events is None:
            return "p5_required_events_invalid"
        canonical_evidence_stream = self._canonical_evidence_stream(str(payload.get("evidence_ref", "")))
        canonical_quest_stream = self._canonical_quest_stream(str(payload.get("quest_instance_ref", "")))
        if payload.get("evidence_stream_ref") != canonical_evidence_stream:
            return "p5_canonical_stream_mismatch"
        if payload.get("quest_stream_ref") != canonical_quest_stream:
            return "p5_canonical_stream_mismatch"
        if dict(command.expected_revisions) != dict(request.expected_revisions.entries):
            return "p5_revision_vector_mismatch"
        if dict(command.read_set_revisions) != dict(request.read_set_revisions.entries):
            return "p5_read_vector_mismatch"
        required_pins = {schema_pin.schema_ref: schema_pin.schema_version for schema_pin in request.required_schema_pins}
        for schema_ref, schema_version in required_pins.items():
            if command.pinned_revisions.get(schema_ref) != schema_version:
                return "p5_schema_pin_mismatch"
        if payload.get("evidence_stream_ref") != proposed_events[_EVIDENCE_EVENT].stream_ref:
            return "p5_proposed_event_mismatch"
        if payload.get("quest_stream_ref") != proposed_events[_OBJECTIVE_EVENT].stream_ref:
            return "p5_proposed_event_mismatch"
        quest_stream = str(payload["quest_stream_ref"])
        failure = self._validate_revision_vector(
            revisions=request.expected_revisions.entries,
            quest_stream=quest_stream,
        )
        if failure is not None:
            return failure
        failure = self._validate_revision_vector(
            revisions=request.read_set_revisions.entries,
            quest_stream=quest_stream,
        )
        if failure is not None:
            return failure
        return None

    def _validate_revision_vector(
        self,
        *,
        revisions: dict[str, int],
        quest_stream: str,
    ) -> str | None:
        quest_expected = revisions.get(quest_stream)
        if quest_expected is not None and self._store.get_stream_head(quest_stream) != quest_expected:
            return "p5_objective_stale"
        for stream_ref, pinned_revision in revisions.items():
            if stream_ref == quest_stream:
                continue
            if self._store.get_stream_head(stream_ref) != pinned_revision:
                return "p5_revision_stale"
        return None

    @staticmethod
    def _required_proposed_events(
        request: P5ResolutionRequest,
    ) -> dict[str, Any] | None:
        if len(request.proposed_events) != 2:
            return None
        event_map = {event.event_name: event for event in request.proposed_events}
        if len(event_map) != 2:
            return None
        if set(event_map) != {_EVIDENCE_EVENT, _OBJECTIVE_EVENT}:
            return None
        return event_map

    def _validate_reward_fragments(
        self,
        *,
        reward_fragments: tuple[OwnerAuthorizedFragment, ...],
        request: P5ResolutionRequest,
        command: GameplayCommandEnvelope,
    ) -> str | None:
        command_visibility = str(command.payload.get("visibility", ""))
        for fragment in reward_fragments:
            if fragment.owner_principal_ref != request.owner_adapter_ref:
                return "p5_reward_owner_rejected"
            try:
                owner = self._registry.require_owner_adapter(fragment.owner_principal_ref)
            except ValueError:
                return "p5_reward_owner_rejected"
            for pin_ref, pin_version in fragment.pinned_revisions.items():
                if command.pinned_revisions.get(pin_ref) != pin_version:
                    return "p5_reward_registry_rejected"
            for stream_ref, expected_revision in fragment.expected_revisions.items():
                if command.expected_revisions.get(stream_ref) != expected_revision:
                    return "p5_reward_registry_rejected"
            for stream_ref, read_revision in fragment.read_set_revisions.items():
                if command.read_set_revisions.get(stream_ref) != read_revision:
                    return "p5_reward_registry_rejected"
            for stream_ref, specs in fragment.event_specs.items():
                policies = fragment.event_visibility_policies.get(stream_ref)
                if policies is None or len(policies) != len(specs):
                    return "p5_reward_visibility_rejected"
                if any(policy != command_visibility for policy in policies):
                    return "p5_reward_visibility_rejected"
                for event_name, _payload in specs:
                    if event_name not in owner.allowed_event_names:
                        return "p5_reward_owner_rejected"
                    try:
                        entry = self._registry.require_event(event_name, 1)
                        if entry.stream_grammar_ref not in owner.allowed_stream_grammar_refs:
                            return "p5_reward_owner_rejected"
                        self._registry.require_stream(stream_ref, entry.stream_grammar_ref)
                    except ValueError:
                        return "p5_reward_registry_rejected"
        return None

    @staticmethod
    def _canonical_evidence_stream(evidence_ref: str) -> str:
        return f"gameplay:evidence:{evidence_ref}"

    @staticmethod
    def _canonical_quest_stream(quest_instance_ref: str) -> str:
        return f"gameplay:quest:{quest_instance_ref}"

    def _rejected(self, failure_code: str) -> QuestEvidenceAuthorityResult:
        return QuestEvidenceAuthorityResult(
            resolution=P5ResolutionResult(
                result_kind="rejected_zero_write",
                registry_ref=self._registry.registry_ref,
                registry_revision=self._registry.registry_revision,
                registry_digest=self._registry.registry_digest,
                committed_event_refs=(),
                failure_code=failure_code,
            ),
            receipt=None,
            settlement_plan=None,
        )

    def _committed_result(
        self,
        receipt,
        *,
        duplicate: bool,
        settlement_plan: SettlementPlan | None = None,
    ) -> QuestEvidenceAuthorityResult:
        normalized_receipt = receipt.model_copy(
            update={"idempotency_status": "duplicate_replayed" if duplicate else receipt.idempotency_status},
            deep=True,
        )
        return QuestEvidenceAuthorityResult(
            resolution=P5ResolutionResult(
                result_kind="committed_success",
                registry_ref=self._registry.registry_ref,
                registry_revision=self._registry.registry_revision,
                registry_digest=self._registry.registry_digest,
                committed_event_refs=tuple(normalized_receipt.committed_event_ids),
                failure_code=None,
            ),
            receipt=normalized_receipt,
            settlement_plan=settlement_plan,
        )


__all__ = ["QuestEvidenceAuthority", "QuestEvidenceAuthorityResult"]
