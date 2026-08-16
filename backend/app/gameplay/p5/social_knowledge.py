from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayOutboxEntry
from app.gameplay.p5.contracts import P5ResolutionRequest, P5ResolutionResult, build_directed_relationship_ref
from app.gameplay.p5.registry import P5PolicyRegistry
from app.gameplay.shared_contracts import GameplayCommandEnvelope, SettlementPlan
from app.gameplay.settlement_plan import SettlementPlan as EventStoreSettlementPlan


_PRINCIPAL = "authority:p5:social"
_RELATIONSHIP_EVENT = "gameplay.social.relationship_fact_recorded"
_KNOWLEDGE_EVENT = "gameplay.social.knowledge_observed"
_REVOCATION_EVENT = "gameplay.social.visibility_revoked"
_HOUSEHOLD_MEMBERSHIP_EVENT = "gameplay.social.household_membership_recorded"


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _projected_confidence(*, confidence: float, decay_rate_per_day: float, observed_at: str, now: str) -> float | None:
    observed = _parse_time(observed_at)
    current = _parse_time(now)
    if observed is None or current is None:
        return None
    if current <= observed:
        return round(max(0.0, confidence), 2)
    days = max(0.0, (current - observed).total_seconds() / 86400)
    return round(max(0.0, confidence - (decay_rate_per_day * days)), 2)


def _is_visible(visibility: str, recipient_ref: str) -> bool:
    if visibility == "public":
        return True
    if visibility == "authority_only":
        return recipient_ref.startswith("authority:")
    return visibility == f"actor:{recipient_ref}"


def _knowledge_stream(*, knower_ref: str, fact_ref: str) -> str:
    payload = {"fact_ref": fact_ref, "knower_ref": knower_ref}
    return "gameplay:knowledge:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _relationship_stream(*, source_ref: str, target_ref: str, relation_kind: str) -> str:
    return build_directed_relationship_ref(
        source_ref=source_ref,
        relation_kind=relation_kind,
        target_ref=target_ref,
    )


@dataclass(frozen=True)
class SocialFactAuthorityResult:
    resolution: P5ResolutionResult
    receipt: Any | None
    settlement_plan: SettlementPlan | None


@dataclass(frozen=True)
class SocialRecipientView:
    relationship_facts: tuple[dict[str, object], ...]
    knowledge_facts: tuple[dict[str, object], ...]
    reputation: dict[str, dict[str, float]]
    source_revision_vector: dict[str, int]
    projection_hash: str


@dataclass(frozen=True)
class HouseholdRecipientView:
    owner_principal_ref: str
    household_memberships: tuple[dict[str, object], ...]
    source_revision_vector: dict[str, int]
    projection_hash: str

    def validate_against(self, *, store: GameplayEventStore):
        for stream_id, expected_revision in self.source_revision_vector.items():
            if store.get_stream_head(stream_id) != expected_revision:
                return SocialInputValidation(accepted=False, error_code="household_source_revision_stale")
        return SocialInputValidation(accepted=True)


@dataclass(frozen=True)
class SocialInputValidation:
    accepted: bool
    error_code: str | None = None


class SocialFactAuthority:
    def __init__(self, *, registry: P5PolicyRegistry, store: GameplayEventStore) -> None:
        self._registry = registry
        self._store = store

    def record_household_membership(
        self,
        *,
        command_id: str,
        household_ref: str,
        member_ref: str,
        relation_kind: str,
        membership_status: str,
        effective_from: str,
        effective_to: str | None,
        residence_ref: str,
        visibility: str,
        recipient_ref: str,
        observed_at: str,
    ):
        if not household_ref.startswith("household:") or not member_ref.startswith("character:"):
            raise ValueError("household_reference_invalid")
        if not relation_kind or not membership_status or not residence_ref:
            raise ValueError("household_membership_invalid")
        if not _is_visible(visibility, recipient_ref) and visibility != "authority_only":
            raise ValueError("household_visibility_invalid")
        stream_id = _relationship_stream(
            source_ref=household_ref,
            target_ref=member_ref,
            relation_kind=relation_kind,
        )
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.social.record_household_membership",
            command_version=1,
            principal_ref=_PRINCIPAL,
            actor_ref=recipient_ref,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=f"idempotency:{command_id}",
            expected_revisions={stream_id: self._store.get_stream_head(stream_id)},
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{household_ref}",
            source_ref="authority:p5:social",
            submitted_at=observed_at,
            pinned_revisions={"social:household": 1},
            payload={
                "stream_ref": stream_id,
                "event_type": _HOUSEHOLD_MEMBERSHIP_EVENT,
                "visibility_policy": visibility,
                "household_ref": household_ref,
                "member_ref": member_ref,
                "relation_kind": relation_kind,
                "membership_status": membership_status,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "residence_ref": residence_ref,
                "visibility": visibility,
                "recipient_ref": recipient_ref,
                "observed_at": observed_at,
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.household.scoped_projection",
                        audience=visibility,
                        payload_projection={"household_ref": household_ref, "member_ref": member_ref},
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def household_view_for(self, *, recipient_ref: str, now: str) -> HouseholdRecipientView:
        memberships: list[dict[str, object]] = []
        source_revision_vector: dict[str, int] = {}
        for event in self._store.read_events():
            if event.event_type != _HOUSEHOLD_MEMBERSHIP_EVENT:
                continue
            visibility = str(event.payload.get("visibility", event.visibility_policy))
            if not _is_visible(visibility, recipient_ref) and not (
                visibility == "authority_only" and recipient_ref.startswith("authority:")
            ):
                continue
            effective_from = str(event.payload.get("effective_from", ""))
            effective_to = event.payload.get("effective_to")
            if effective_from and _parse_time(now) is not None and _parse_time(effective_from) is not None and _parse_time(now) < _parse_time(effective_from):
                continue
            if effective_to and _parse_time(now) is not None and _parse_time(str(effective_to)) is not None and _parse_time(now) >= _parse_time(str(effective_to)):
                continue
            memberships.append(
                {
                    "household_ref": event.payload["household_ref"],
                    "member_ref": event.payload["member_ref"],
                    "relation_kind": event.payload["relation_kind"],
                    "membership_status": event.payload["membership_status"],
                    "residence_ref": event.payload["residence_ref"],
                    "effective_from": effective_from,
                    "effective_to": effective_to,
                    "visibility": visibility,
                }
            )
            source_revision_vector[event.stream_id] = event.stream_revision
        memberships.sort(key=lambda item: (str(item["household_ref"]), str(item["member_ref"]), str(item["effective_from"])))
        projection = {
            "household_memberships": memberships,
            "source_revision_vector": dict(sorted(source_revision_vector.items())),
        }
        return HouseholdRecipientView(
            owner_principal_ref=_PRINCIPAL,
            household_memberships=tuple(memberships),
            source_revision_vector=dict(sorted(source_revision_vector.items())),
            projection_hash=_digest(projection),
        )

    def resolve(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        now: str,
    ) -> SocialFactAuthorityResult:
        digest = self._request_digest(command=command, request=request)
        existing = self._store.get_idempotency_record(_PRINCIPAL, command.idempotency_key)
        if existing is not None:
            if existing.payload_digest == digest:
                receipt = self._store.get_by_idempotency(_PRINCIPAL, command.idempotency_key)
                return self._committed_result(receipt, settlement_plan=None)
            return self._rejected("idempotency_key_reused")

        try:
            request = self._registry.validate_request(request)
        except ValueError as exc:
            return self._rejected(str(exc))

        payload = dict(command.payload)
        failure = self._validate_common(
            command=command,
            request=request,
            payload=payload,
        )
        if failure is not None:
            return self._rejected(failure)
        failure = self._validate_current_revisions(request=request)
        if failure is not None:
            return self._rejected(failure)

        relationship_fact = payload.get("relationship_fact")
        knowledge_fact = payload.get("knowledge_fact")
        revocation = payload.get("revocation")
        if relationship_fact is not None or knowledge_fact is not None:
            return self._resolve_record(
                command=command,
                request=request,
                digest=digest,
                relationship_fact=relationship_fact if isinstance(relationship_fact, dict) else None,
                knowledge_fact=knowledge_fact if isinstance(knowledge_fact, dict) else None,
            )
        if revocation is not None:
            if not isinstance(revocation, dict):
                return self._rejected("p5_required_events_invalid")
            return self._resolve_revocation(
                command=command,
                request=request,
                digest=digest,
                revocation=revocation,
            )
        return self._rejected("p5_required_events_invalid")

    def view_for(self, *, recipient_ref: str, now: str) -> SocialRecipientView:
        relationship_facts: list[dict[str, object]] = []
        knowledge_facts: list[dict[str, object]] = []
        reputation: dict[str, dict[str, list[float]]] = {}
        source_revision_vector: dict[str, int] = {}
        revoked_streams = {
            (
                event.stream_id,
                str(event.payload.get("recipient_ref", "")),
            )
            for event in self._store.read_events()
            if event.event_type == _REVOCATION_EVENT
        }

        for event in self._store.read_events():
            if event.event_type == _RELATIONSHIP_EVENT and _is_visible(event.visibility_policy, recipient_ref):
                projected = _projected_confidence(
                    confidence=float(event.payload["confidence"]),
                    decay_rate_per_day=float(event.payload["decay_rate_per_day"]),
                    observed_at=str(event.payload["observed_at"]),
                    now=now,
                )
                if projected is None:
                    continue
                relationship_facts.append(
                    {
                        "relationship_ref": event.payload["relationship_ref"],
                        "source_ref": event.payload["source_ref"],
                        "target_ref": event.payload["target_ref"],
                        "relation_kind": event.payload["relation_kind"],
                        "projected_confidence": projected,
                        "visibility": event.payload["visibility"],
                    }
                )
                target_ref = str(event.payload["target_ref"])
                relation_kind = str(event.payload["relation_kind"])
                reputation.setdefault(target_ref, {}).setdefault(relation_kind, []).append(projected)
                source_revision_vector[event.stream_id] = event.stream_revision
                continue

            if event.event_type != _KNOWLEDGE_EVENT or not _is_visible(event.visibility_policy, recipient_ref):
                continue
            if (event.stream_id, recipient_ref) in revoked_streams:
                continue
            projected = _projected_confidence(
                confidence=float(event.payload["confidence"]),
                decay_rate_per_day=float(event.payload["decay_rate_per_day"]),
                observed_at=str(event.payload["observed_at"]),
                now=now,
            )
            if projected is None:
                continue
            knowledge_facts.append(
                {
                    "fact_ref": event.payload["fact_ref"],
                    "knower_ref": event.payload["knower_ref"],
                    "subject_ref": event.payload["subject_ref"],
                    "observation_ref": event.payload["observation_ref"],
                    "knowledge_kind": event.payload["knowledge_kind"],
                    "projected_confidence": projected,
                    "visibility": event.payload["visibility"],
                }
            )
            source_revision_vector[event.stream_id] = event.stream_revision

        knowledge_facts.sort(
            key=lambda fact: (
                -float(fact["projected_confidence"]),
                str(fact["observation_ref"]),
            )
        )
        finalized_reputation = {
            target_ref: {
                relation_kind: round(sum(values) / len(values), 2)
                for relation_kind, values in relation_map.items()
            }
            for target_ref, relation_map in reputation.items()
        }
        projection_payload = {
            "relationship_facts": relationship_facts,
            "knowledge_facts": knowledge_facts,
            "reputation": finalized_reputation,
            "source_revision_vector": dict(sorted(source_revision_vector.items())),
        }
        return SocialRecipientView(
            relationship_facts=tuple(relationship_facts),
            knowledge_facts=tuple(knowledge_facts),
            reputation=finalized_reputation,
            source_revision_vector=dict(sorted(source_revision_vector.items())),
            projection_hash=_digest(projection_payload),
        )

    def _resolve_record(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        digest: str,
        relationship_fact: dict[str, object] | None,
        knowledge_fact: dict[str, object] | None,
    ) -> SocialFactAuthorityResult:
        event_specs: list[tuple[str, str, dict[str, object]]] = []
        event_mapping: dict[str, str] = {}
        proposed = {event.event_name: event for event in request.proposed_events}

        if relationship_fact is not None:
            canonical_stream = _relationship_stream(
                source_ref=str(relationship_fact["source_ref"]),
                target_ref=str(relationship_fact["target_ref"]),
                relation_kind=str(relationship_fact["relation_kind"]),
            )
            if str(relationship_fact["relationship_ref"]) != canonical_stream or request.relationship_ref != canonical_stream:
                return self._rejected("p5_canonical_stream_mismatch")
            if _parse_time(str(relationship_fact["observed_at"])) is None:
                return self._rejected("p5_observed_at_invalid")
            event = proposed.get(_RELATIONSHIP_EVENT)
            if event is None or event.stream_ref != canonical_stream or event.visibility != relationship_fact["visibility"]:
                return self._rejected("p5_required_events_invalid")
            schema_pin = self._schema_pin_for(_RELATIONSHIP_EVENT)
            payload = {
                "request_ref": request.request_ref,
                "relationship_ref": canonical_stream,
                "source_ref": relationship_fact["source_ref"],
                "target_ref": relationship_fact["target_ref"],
                "relation_kind": relationship_fact["relation_kind"],
                "confidence": float(relationship_fact["confidence"]),
                "decay_rate_per_day": float(relationship_fact["decay_rate_per_day"]),
                "evidence_ref": relationship_fact["evidence_ref"],
                "provenance_source_ref": relationship_fact["provenance_source_ref"],
                "observed_at": relationship_fact["observed_at"],
                "visibility": relationship_fact["visibility"],
                "registry_ref": request.registry_ref,
                "registry_revision": request.registry_revision,
                "registry_digest": request.registry_digest,
                "schema_ref": schema_pin.schema_ref,
                "schema_version": schema_pin.schema_version,
                "schema_digest": schema_pin.schema_digest,
                "expected_stream_revisions": dict(request.expected_revisions.entries),
                "read_stream_revisions": dict(request.read_set_revisions.entries),
            }
            event_specs.append((_RELATIONSHIP_EVENT, canonical_stream, payload))
            event_mapping[_RELATIONSHIP_EVENT] = canonical_stream

        if knowledge_fact is not None:
            canonical_stream = _knowledge_stream(
                knower_ref=str(knowledge_fact["knower_ref"]),
                fact_ref=str(knowledge_fact["fact_ref"]),
            )
            if _parse_time(str(knowledge_fact["observed_at"])) is None:
                return self._rejected("p5_observed_at_invalid")
            event = proposed.get(_KNOWLEDGE_EVENT)
            if event is None or event.stream_ref != canonical_stream or event.visibility != knowledge_fact["visibility"]:
                return self._rejected("p5_required_events_invalid")
            schema_pin = self._schema_pin_for(_KNOWLEDGE_EVENT)
            payload = {
                "request_ref": request.request_ref,
                "fact_ref": knowledge_fact["fact_ref"],
                "knower_ref": knowledge_fact["knower_ref"],
                "subject_ref": knowledge_fact["subject_ref"],
                "observation_ref": knowledge_fact["observation_ref"],
                "knowledge_kind": knowledge_fact["knowledge_kind"],
                "confidence": float(knowledge_fact["confidence"]),
                "decay_rate_per_day": float(knowledge_fact["decay_rate_per_day"]),
                "evidence_ref": knowledge_fact["evidence_ref"],
                "provenance_source_ref": knowledge_fact["provenance_source_ref"],
                "observed_at": knowledge_fact["observed_at"],
                "visibility": knowledge_fact["visibility"],
                "registry_ref": request.registry_ref,
                "registry_revision": request.registry_revision,
                "registry_digest": request.registry_digest,
                "schema_ref": schema_pin.schema_ref,
                "schema_version": schema_pin.schema_version,
                "schema_digest": schema_pin.schema_digest,
                "expected_stream_revisions": dict(request.expected_revisions.entries),
                "read_stream_revisions": dict(request.read_set_revisions.entries),
            }
            event_specs.append((_KNOWLEDGE_EVENT, canonical_stream, payload))
            event_mapping[_KNOWLEDGE_EVENT] = canonical_stream

        if not event_specs or set(proposed) != set(event_mapping):
            return self._rejected("p5_required_events_invalid")

        settlement_plan = SettlementPlan(
            plan_id=f"settlement:{command.command_id}",
            command_id=command.command_id,
            expected_revision_vector=dict(request.expected_revisions.entries),
            proposals=(),
            event_mapping=event_mapping,
            idempotency_key=command.idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
        )
        receipt = self._append(
            command=command,
            request=request,
            digest=digest,
            event_specs=event_specs,
            projection_refresh_hints=[],
        )
        if not receipt.committed:
            return self._rejected(self._map_failure_code(receipt.failure.error_code if receipt.failure is not None else "append_batch_failed"))
        return self._committed_result(receipt, settlement_plan=settlement_plan)

    def _resolve_revocation(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        digest: str,
        revocation: dict[str, object],
    ) -> SocialFactAuthorityResult:
        canonical_stream = _knowledge_stream(
            knower_ref=str(revocation["knower_ref"]),
            fact_ref=str(revocation["fact_ref"]),
        )
        if _parse_time(str(revocation["observed_at"])) is None:
            return self._rejected("p5_observed_at_invalid")
        proposed = {event.event_name: event for event in request.proposed_events}
        event = proposed.get(_REVOCATION_EVENT)
        if event is None or event.stream_ref != canonical_stream or event.visibility != "authority_only" or len(proposed) != 1:
            return self._rejected("p5_required_events_invalid")

        schema_pin = self._schema_pin_for(_REVOCATION_EVENT)
        payload = {
            "request_ref": request.request_ref,
            "fact_ref": revocation["fact_ref"],
            "knower_ref": revocation["knower_ref"],
            "recipient_ref": revocation["recipient_ref"],
            "prior_visibility": revocation["prior_visibility"],
            "reason_code": revocation["reason_code"],
            "evidence_ref": revocation["evidence_ref"],
            "provenance_source_ref": revocation["provenance_source_ref"],
            "observed_at": revocation["observed_at"],
            "visibility": "authority_only",
            "registry_ref": request.registry_ref,
            "registry_revision": request.registry_revision,
            "registry_digest": request.registry_digest,
            "schema_ref": schema_pin.schema_ref,
            "schema_version": schema_pin.schema_version,
            "schema_digest": schema_pin.schema_digest,
            "expected_stream_revisions": dict(request.expected_revisions.entries),
            "read_stream_revisions": dict(request.read_set_revisions.entries),
        }
        settlement_plan = SettlementPlan(
            plan_id=f"settlement:{command.command_id}",
            command_id=command.command_id,
            expected_revision_vector=dict(request.expected_revisions.entries),
            proposals=(),
            event_mapping={_REVOCATION_EVENT: canonical_stream},
            idempotency_key=command.idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
        )
        receipt = self._append(
            command=command,
            request=request,
            digest=digest,
            event_specs=[(_REVOCATION_EVENT, canonical_stream, payload)],
            projection_refresh_hints=[
                {
                    "projection_id": "godot_mirror",
                    "stream_id": canonical_stream,
                    "reason": "visibility_revoked",
                    "actor_refs": [str(revocation["recipient_ref"])],
                }
            ],
        )
        if not receipt.committed:
            return self._rejected(self._map_failure_code(receipt.failure.error_code if receipt.failure is not None else "append_batch_failed"))
        return self._committed_result(receipt, settlement_plan=settlement_plan)

    def _append(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        digest: str,
        event_specs: list[tuple[str, str, dict[str, object]]],
        projection_refresh_hints: list[dict[str, object]],
    ):
        transaction_id = command.transaction_id or f"tx:{command.command_id}"
        events = []
        for index, (event_name, stream_id, payload) in enumerate(event_specs, start=1):
            events.append(
                {
                    "event_id": f"event:{command.command_id}:{index}",
                    "event_type": event_name,
                    "schema_version": 1,
                    "stream_id": stream_id,
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": transaction_id,
                    "command_id": command.command_id,
                    "causation_id": command.causation_id,
                    "correlation_id": command.correlation_id,
                    "visibility_policy": payload["visibility"],
                    "payload": payload,
                }
            )
        return self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command.command_id,
                "expected_stream_revisions": dict(request.expected_revisions.entries),
                "read_stream_revisions": dict(request.read_set_revisions.entries),
                "pinned_revisions": dict(command.pinned_revisions),
                "events": events,
                "idempotency_record": {
                    "principal_ref": _PRINCIPAL,
                    "idempotency_key": command.idempotency_key,
                    "payload_digest": digest,
                },
                "owner_fragments": [],
                "outbox_entries": [],
                "result_digest": digest,
                "projection_refresh_hints": projection_refresh_hints,
            }
        )

    def _request_digest(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
    ) -> str:
        return _digest(
            {
                "command": command.model_dump(mode="json"),
                "request": request.model_dump(mode="json"),
            }
        )

    def _schema_pin_for(self, event_name: str):
        entry = self._registry.require_event(event_name, 1)
        return self._registry.require_schema(entry.schema_ref, entry.schema_version)

    def _validate_common(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        payload: dict[str, object],
    ) -> str | None:
        if command.actor_ref != request.subject_scope_ref:
            return "p5_subject_scope_mismatch"
        if payload.get("provider_ref") != request.evidence_provider_ref:
            return "p5_provider_untrusted"
        if payload.get("owner_adapter_ref") != request.owner_adapter_ref:
            return "p5_owner_adapter_unregistered"
        if payload.get("package_ref") != request.package_ref or payload.get("package_revision") != request.package_revision:
            return "p5_package_revision_unregistered"
        package = self._registry.require_package(request.package_ref, request.package_revision)
        if payload.get("package_digest") != package.package_digest:
            return "p5_package_digest_pin_mismatch"
        if payload.get("ruleset_revision") != request.ruleset_revision:
            return "p5_ruleset_revision_unregistered"
        if dict(command.expected_revisions) != dict(request.expected_revisions.entries):
            return "p5_revision_vector_mismatch"
        if dict(command.read_set_revisions) != dict(request.read_set_revisions.entries):
            return "p5_read_vector_mismatch"
        for schema_pin in request.required_schema_pins:
            if command.pinned_revisions.get(schema_pin.schema_ref) != schema_pin.schema_version:
                return "p5_schema_pin_mismatch"
        return None

    def _validate_current_revisions(self, *, request: P5ResolutionRequest) -> str | None:
        for revision_vector in (request.expected_revisions.entries, request.read_set_revisions.entries):
            for stream_ref, expected_revision in revision_vector.items():
                if self._store.get_stream_head(stream_ref) != expected_revision:
                    return "p5_revision_stale"
        return None

    def _rejected(self, failure_code: str) -> SocialFactAuthorityResult:
        return SocialFactAuthorityResult(
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

    def _committed_result(self, receipt, *, settlement_plan: SettlementPlan | None) -> SocialFactAuthorityResult:
        return SocialFactAuthorityResult(
            resolution=P5ResolutionResult(
                result_kind="committed_success",
                registry_ref=self._registry.registry_ref,
                registry_revision=self._registry.registry_revision,
                registry_digest=self._registry.registry_digest,
                committed_event_refs=tuple(receipt.committed_event_ids),
                failure_code=None,
            ),
            receipt=receipt,
            settlement_plan=settlement_plan,
        )

    @staticmethod
    def _map_failure_code(error_code: str) -> str:
        if error_code in {"revision_conflict", "missing_expected_revision"}:
            return "p5_revision_stale"
        return error_code


__all__ = [
    "HouseholdRecipientView",
    "SocialFactAuthority",
    "SocialFactAuthorityResult",
    "SocialRecipientView",
]
