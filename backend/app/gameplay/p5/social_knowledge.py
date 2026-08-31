from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import GameplayOutboxEntry
from app.gameplay.patch_runtime import GameplayPatchRegistry
from app.gameplay.p5.contracts import P5ResolutionRequest, P5ResolutionResult, build_directed_relationship_ref
from app.gameplay.p5.registry import P5PolicyRegistry
from app.gameplay.shared_contracts import GameplayCommandEnvelope, SettlementPlan, SettlementReceipt
from app.gameplay.settlement_plan import (
    SettlementPlan as EventStoreSettlementPlan,
    build_multi_stream_atomic_event_batch,
)


_PRINCIPAL = "authority:p5:social"
_RELATIONSHIP_EVENT = "gameplay.social.relationship_fact_recorded"
_KNOWLEDGE_EVENT = "gameplay.social.knowledge_observed"
_REVOCATION_EVENT = "gameplay.social.visibility_revoked"
_HOUSEHOLD_MEMBERSHIP_EVENT = "gameplay.social.household_membership_recorded"
_HANDSHAKE_SHARED_EXPERIENCE_EVENT = "gameplay.social.handshake_shared_experience_recorded"
_HANDSHAKE_COMMITTED_EVENT = "embodied.interaction_session.committed"
_HANDSHAKE_SHARED_EXPERIENCE_POLICY = "policy:social-handshake-shared-experience@1"
_HANDSHAKE_SHARED_EXPERIENCE_DESCRIPTOR = "descriptor:social-handshake-shared-experience@1"
_HANDSHAKE_SHARED_EXPERIENCE_CATALOG = "inf:social-handshake-shared-experience@1"
_PUBLIC_MILLING_ACK_EVENT = "gameplay.social.public_milling_notice_acknowledged"
_PUBLIC_MILLING_ACK_POLICY = "policy:social-public-milling-notice-acknowledgment@1"
_PUBLIC_MILLING_ACK_DESCRIPTOR = "descriptor:social-public-milling-notice-acknowledgment@1"
_PUBLIC_MILLING_ACK_CATALOG = "inf:social-public-milling-notice-acknowledgment@1"
_PUBLIC_MILLING_PROVIDER = "organization:district-milling-cooperative"
_PUBLIC_MILLING_TERMS = "service:industrial-facility-public-milling-session@1"
_PUBLIC_MILLING_PACKAGE = "package:industrial-facilities:v6"


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
class SharedExperienceRecipientView:
    participant_ref: str
    shared_experience_refs: tuple[str, ...]
    experiences: tuple[Mapping[str, object], ...]
    source_revision_vector: dict[str, int]
    projection_hash: str


@dataclass(frozen=True)
class PublicMillingNoticeSocialAcknowledgmentView:
    participant_ref: str
    acknowledgment_refs: tuple[str, ...]
    acknowledgments: tuple[Mapping[str, object], ...]
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
    def __init__(
        self,
        *,
        registry: P5PolicyRegistry,
        store: GameplayEventStore,
        package_registry: GameplayPatchRegistry | None = None,
    ) -> None:
        self._registry = registry
        self._store = store
        self._package_registry = package_registry

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

    def record_completed_handshake_shared_experience(
        self,
        *,
        session_event_id: str,
        expected_session_revision: int,
        expected_target_revisions: tuple[int, int],
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> SocialFactAuthorityResult:
        """Record only the exact completed two-party handshake history pair."""
        if (
            not session_event_id
            or expected_session_revision < 1
            or len(expected_target_revisions) != 2
            or any(value < 0 or isinstance(value, bool) for value in expected_target_revisions)
            or not command_id
            or not idempotency_key
            or not causation_id
            or not correlation_id
        ):
            return self._rejected("handshake_shared_experience_reference_invalid")
        if (
            self._registry.registry_ref != "registry:p5:social"
            or self._registry.registry_revision != "registry:p5:social:v2"
        ):
            return self._rejected("handshake_shared_experience_registry_invalid")
        try:
            event_entry = self._registry.require_event(_HANDSHAKE_SHARED_EXPERIENCE_EVENT, 1)
            self._registry.require_schema(event_entry.schema_ref, event_entry.schema_version)
        except ValueError:
            return self._rejected("handshake_shared_experience_registry_invalid")
        try:
            committed = self._store.get_event(session_event_id)
        except KeyError:
            return self._rejected("handshake_shared_experience_source_missing")
        source_stream = committed.stream_id
        source_events = tuple(sorted(self._store.read_stream(source_stream), key=lambda event: event.stream_revision))
        expected_types = (
            "embodied.interaction_session.proposed",
            "embodied.interaction_session.accepted",
            "embodied.interaction_session.authorized",
            "embodied.interaction_session.realizing",
            "embodied.interaction_session.participant_observed",
            "embodied.interaction_session.participant_observed",
            _HANDSHAKE_COMMITTED_EVENT,
        )
        if (
            committed.event_type != _HANDSHAKE_COMMITTED_EVENT
            or committed.stream_revision != expected_session_revision
            or self._store.get_stream_head(source_stream) != expected_session_revision
            or tuple(event.event_type for event in source_events) != expected_types
            or tuple(event.stream_revision for event in source_events) != tuple(range(1, 8))
            or any(event.visibility_policy != "session_public_safe" for event in source_events)
        ):
            return self._rejected("handshake_shared_experience_source_invalid")
        proposed, accepted, authorized, realizing, first_observed, second_observed, terminal = source_events
        proposal = proposed.payload
        participants = proposal.get("participant_refs")
        if (
            proposal.get("semantic_action") != "handshake"
            or not isinstance(participants, list)
            or len(participants) != 2
            or len(set(participants)) != 2
            or any(not isinstance(ref, str) or not ref.startswith("character:") for ref in participants)
            or proposal.get("initiator_ref") != participants[0]
            or proposal.get("target_refs") != [participants[1]]
            or accepted.payload.get("participant_ref") != participants[1]
            or authorized.payload.get("state") != "authorized"
            or realizing.payload.get("state") != "realizing"
            or terminal.payload.get("state") != "committed"
            or terminal.payload.get("session_id") != proposal.get("session_id")
            or terminal.payload.get("settlement_ref") != f"settlement:{proposal.get('session_id')}"
            or {first_observed.payload.get("participant_ref"), second_observed.payload.get("participant_ref")} != set(participants)
            or first_observed.payload.get("terminal_status") != "completed"
            or second_observed.payload.get("terminal_status") != "completed"
        ):
            return self._rejected("handshake_shared_experience_source_invalid")
        participant_refs = (str(participants[0]), str(participants[1]))
        target_streams = tuple(f"gameplay:social:shared-experience:{participant_ref}" for participant_ref in participant_refs)
        try:
            for stream_id in target_streams:
                self._registry.require_stream(stream_id, event_entry.stream_grammar_ref)
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref=_HANDSHAKE_SHARED_EXPERIENCE_CATALOG,
                contract_kind="contract_admission",
                owner_ref=_PRINCIPAL,
                stream_ids=target_streams,
                event_types=(_HANDSHAKE_SHARED_EXPERIENCE_EVENT,),
                projection_scope="actor_private",
            )
        except (ValueError, GovernedAuthorityContractError):
            return self._rejected("handshake_shared_experience_catalog_invalid")
        canonical_key = (
            f"social:handshake-shared-experience:{session_event_id}:"
            f"{expected_session_revision}:{expected_target_revisions[0]}:{expected_target_revisions[1]}:v1"
        )
        if idempotency_key != canonical_key:
            return self._rejected("handshake_shared_experience_idempotency_key_invalid")
        existing = self._store.get_by_idempotency(_PRINCIPAL, idempotency_key)
        if existing is not None:
            previous_events = tuple(event for event in self._store.read_events() if event.event_id in set(existing.committed_event_ids))
            if (
                len(previous_events) == 2
                and all(event.event_type == _HANDSHAKE_SHARED_EXPERIENCE_EVENT for event in previous_events)
                and all(event.payload.get("session_event_id") == session_event_id for event in previous_events)
                and all(event.causation_id == causation_id and event.correlation_id == correlation_id for event in previous_events)
            ):
                receipt = SettlementReceipt.from_append_result(
                    result=existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
                    audit_refs=(f"social_handshake_shared_experience:{existing.transaction_id}",),
                )
                return self._committed_result(receipt, settlement_plan=None)
            return self._rejected("handshake_shared_experience_idempotency_key_reused")
        if tuple(self._store.get_stream_head(stream_id) for stream_id in target_streams) != expected_target_revisions:
            return self._rejected("handshake_shared_experience_revision_conflict")
        shared_experience_ref = f"shared-experience:{proposal.get('session_id')}"
        event_specs: dict[str, tuple[tuple[str, Mapping[str, object]], ...]] = {}
        visibility: dict[str, tuple[str, ...]] = {}
        for participant_ref, counterpart_ref, target_stream in (
            (participant_refs[0], participant_refs[1], target_streams[0]),
            (participant_refs[1], participant_refs[0], target_streams[1]),
        ):
            event_specs[target_stream] = ((
                _HANDSHAKE_SHARED_EXPERIENCE_EVENT,
                {
                    "shared_experience_ref": shared_experience_ref,
                    "session_id": proposal.get("session_id"),
                    "session_event_id": session_event_id,
                    "session_event_revision": expected_session_revision,
                    "source_stream_id": source_stream,
                    "source_event_ids": [event.event_id for event in source_events],
                    "source_event_revisions": [event.stream_revision for event in source_events],
                    "participant_ref": participant_ref,
                    "counterpart_ref": counterpart_ref,
                    "interaction_kind": "handshake",
                    "status": "completed",
                    "policy_revision": _HANDSHAKE_SHARED_EXPERIENCE_POLICY,
                    "descriptor_ref": _HANDSHAKE_SHARED_EXPERIENCE_DESCRIPTOR,
                    "descriptor_revision": _HANDSHAKE_SHARED_EXPERIENCE_DESCRIPTOR,
                    "catalog_ref": _HANDSHAKE_SHARED_EXPERIENCE_CATALOG,
                    "terminal": "v1_terminal_no_compensation",
                },
            ),)
            visibility[target_stream] = (f"actor:{participant_ref}",)
        envelope = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.social.record_completed_handshake_shared_experience",
            command_version=1,
            principal_ref=_PRINCIPAL,
            actor_ref=participant_refs[0],
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: revision for stream_id, revision in zip(target_streams, expected_target_revisions, strict=True)},
            read_set_revisions={source_stream: expected_session_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=session_event_id,
            submitted_at="interaction-session-committed",
            pinned_revisions={"session": expected_session_revision, "descriptor": 1},
            payload={},
        )
        batch = build_multi_stream_atomic_event_batch(
            command_id=envelope.command_id,
            principal_ref=envelope.principal_ref,
            expected_revisions=envelope.expected_revisions,
            read_stream_revisions=envelope.read_set_revisions,
            event_specs=event_specs,
            event_visibility_policies=visibility,
            idempotency_key=envelope.idempotency_key,
            causation_id=envelope.causation_id,
            correlation_id=envelope.correlation_id,
            pinned_revisions=envelope.pinned_revisions,
        )
        result = self._store.append_batch(batch)
        if not result.committed:
            return self._rejected(result.failure.error_code if result.failure is not None else "append_batch_failed")
        receipt = SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"social_handshake_shared_experience:{result.transaction_id}",),
            pinned_revisions=envelope.pinned_revisions,
        )
        settlement_plan = SettlementPlan(
            plan_id=f"settlement:{command_id}",
            command_id=command_id,
            expected_revision_vector=dict(envelope.expected_revisions),
            proposals=(),
            event_mapping={_HANDSHAKE_SHARED_EXPERIENCE_EVENT: target_streams},
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        return self._committed_result(receipt, settlement_plan=settlement_plan)

    def handshake_shared_experience_view_for(
        self, *, participant_ref: str, checkpoint_at: int | None = None
    ) -> SharedExperienceRecipientView:
        if not participant_ref.startswith("character:"):
            raise ValueError("handshake_shared_experience_participant_invalid")
        if checkpoint_at is not None and checkpoint_at < 0:
            raise ValueError("handshake_shared_experience_checkpoint_invalid")
        stream_id = f"gameplay:social:shared-experience:{participant_ref}"
        events = [
            event
            for event in self._store.read_stream(stream_id)
            if event.event_type == _HANDSHAKE_SHARED_EXPERIENCE_EVENT
            and event.visibility_policy == f"actor:{participant_ref}"
        ]
        max_sequence = max((event.global_sequence for event in self._store.read_events()), default=0)
        if checkpoint_at is not None and checkpoint_at > max_sequence:
            raise ValueError("handshake_shared_experience_checkpoint_invalid")
        ordered = sorted(events, key=lambda event: (event.global_sequence, event.event_id))
        if checkpoint_at is None:
            reduced = ordered
        else:
            prefix = [event for event in ordered if event.global_sequence <= checkpoint_at]
            tail = [event for event in ordered if event.global_sequence > checkpoint_at]
            reduced = [*prefix, *tail]
        experiences = tuple(dict(event.payload) for event in reduced)
        source_revision_vector = {stream_id: self._store.get_stream_head(stream_id)}
        for payload in experiences:
            source_stream = payload.get("source_stream_id")
            source_revision = payload.get("session_event_revision")
            if isinstance(source_stream, str) and isinstance(source_revision, int):
                source_revision_vector[source_stream] = source_revision
        projection = {
            "participant_ref": participant_ref,
            "shared_experience_refs": tuple(str(payload["shared_experience_ref"]) for payload in experiences),
            "experiences": experiences,
            "source_revision_vector": dict(sorted(source_revision_vector.items())),
        }
        return SharedExperienceRecipientView(
            participant_ref=participant_ref,
            shared_experience_refs=tuple(str(payload["shared_experience_ref"]) for payload in experiences),
            experiences=experiences,
            source_revision_vector=dict(sorted(source_revision_vector.items())),
            projection_hash=_digest(projection),
        )

    def record_public_milling_notice_social_acknowledgment(
        self,
        *,
        notice_event_id: str,
        expected_notice_revision: int,
        expected_target_revisions: tuple[int, int],
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        family_ref: str | None = None,
    ) -> SocialFactAuthorityResult:
        """Record exactly one private acknowledgment for each milling party."""
        if (
            not notice_event_id
            or expected_notice_revision < 1
            or len(expected_target_revisions) != 2
            or any(value < 0 or isinstance(value, bool) for value in expected_target_revisions)
            or not command_id
            or not idempotency_key
            or not causation_id
            or not correlation_id
        ):
            return self._rejected("public_milling_notice_social_acknowledgment_reference_invalid")
        if (
            self._registry.registry_ref != "registry:p5:social"
            or self._registry.registry_revision != "registry:p5:social:v3"
        ):
            return self._rejected("public_milling_notice_social_acknowledgment_registry_invalid")
        try:
            event_entry = self._registry.require_event(_PUBLIC_MILLING_ACK_EVENT, 1)
            schema_pin = self._registry.require_schema(event_entry.schema_ref, event_entry.schema_version)
        except ValueError:
            return self._rejected("public_milling_notice_social_acknowledgment_registry_invalid")
        try:
            notice = self._store.get_event(notice_event_id)
        except KeyError:
            return self._rejected("public_milling_notice_social_acknowledgment_source_missing")
        source, failure = self._public_milling_notice_source(notice, expected_notice_revision)
        if failure is not None:
            return self._rejected(failure)
        receiver_ref = str(source["receiver_ref"])
        participant_refs = (_PUBLIC_MILLING_PROVIDER, receiver_ref)
        target_streams = tuple(
            f"gameplay:social:public-milling-notice-acknowledgment:{participant_ref}"
            for participant_ref in participant_refs
        )
        try:
            for target_stream in target_streams:
                self._registry.require_stream(target_stream, event_entry.stream_grammar_ref)
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref=_PUBLIC_MILLING_ACK_CATALOG,
                contract_kind="contract_admission",
                owner_ref=_PRINCIPAL,
                stream_ids=target_streams,
                event_types=(_PUBLIC_MILLING_ACK_EVENT,),
                projection_scope="actor_private",
            )
        except (ValueError, GovernedAuthorityContractError):
            return self._rejected("public_milling_notice_social_acknowledgment_catalog_invalid")
        canonical_key = (
            f"social:public-milling-notice-ack:{notice_event_id}:{expected_notice_revision}:"
            f"{expected_target_revisions[0]}:{expected_target_revisions[1]}:v1"
        )
        if idempotency_key != canonical_key:
            return self._rejected("public_milling_notice_social_acknowledgment_idempotency_key_invalid")
        existing = self._store.get_by_idempotency(_PRINCIPAL, idempotency_key)
        if existing is not None:
            previous_events = tuple(
                event
                for event in self._store.read_events()
                if event.event_id in set(existing.committed_event_ids)
            )
            if (
                len(previous_events) == 2
                and all(event.event_type == _PUBLIC_MILLING_ACK_EVENT for event in previous_events)
                and all(event.payload.get("source_notice_event_id") == notice_event_id for event in previous_events)
                and all(
                    event.causation_id == causation_id and event.correlation_id == correlation_id
                    for event in previous_events
                )
            ):
                receipt = SettlementReceipt.from_append_result(
                    result=existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
                    audit_refs=(f"social_public_milling_notice_ack:{existing.transaction_id}",),
                )
                return self._committed_result(receipt, settlement_plan=None)
            return self._rejected("public_milling_notice_social_acknowledgment_idempotency_key_reused")
        if tuple(self._store.get_stream_head(stream_id) for stream_id in target_streams) != expected_target_revisions:
            return self._rejected("public_milling_notice_social_acknowledgment_revision_conflict")
        event_specs: dict[str, tuple[tuple[str, Mapping[str, object]], ...]] = {}
        visibility: dict[str, tuple[str, ...]] = {}
        for participant_ref, target_stream in zip(participant_refs, target_streams, strict=True):
            acknowledgment_ref = f"social-ack:public-milling-notice:{notice_event_id}:{participant_ref}"
            event_specs[target_stream] = (
                (
                    _PUBLIC_MILLING_ACK_EVENT,
                    {
                        "acknowledgment_ref": acknowledgment_ref,
                        "notice_event_id": notice_event_id,
                        "source_notice_event_id": notice_event_id,
                        "source_notice_revision": expected_notice_revision,
                        "source_notice_stream_id": notice.stream_id,
                        "participant_ref": participant_ref,
                        "status": "acknowledged",
                        "notice_kind": "public_milling_session_completed",
                        "organization_ref": _PUBLIC_MILLING_PROVIDER,
                        "facility_ref": source["facility_ref"],
                        "project_ref": source["project_ref"],
                        "jurisdiction_ref": source["jurisdiction_ref"],
                        "source_activity_event_id": source["source_activity_event_id"],
                        "source_activity_revision": source["source_activity_revision"],
                        "source_contract_created_event_id": source["source_contract_created_event_id"],
                        "source_contract_created_revision": source["source_contract_created_revision"],
                        "source_contract_fulfilled_event_id": source["source_contract_fulfilled_event_id"],
                        "source_contract_fulfilled_revision": source["source_contract_fulfilled_revision"],
                        "source_acquisition_event_id": source["source_acquisition_event_id"],
                        "source_acquisition_revision": source["source_acquisition_revision"],
                        "policy_revision": _PUBLIC_MILLING_ACK_POLICY,
                        "descriptor_ref": _PUBLIC_MILLING_ACK_DESCRIPTOR,
                        "descriptor_revision": _PUBLIC_MILLING_ACK_DESCRIPTOR,
                        "catalog_ref": _PUBLIC_MILLING_ACK_CATALOG,
                        "schema_ref": schema_pin.schema_ref,
                        "schema_version": schema_pin.schema_version,
                        "schema_digest": schema_pin.schema_digest,
                        "registry_ref": self._registry.registry_ref,
                        "registry_revision": self._registry.registry_revision,
                        "registry_digest": self._registry.registry_digest,
                        "terminal": "v1_terminal_no_compensation",
                        **({"family_ref": family_ref} if family_ref is not None else {}),
                    },
                ),
            )
            visibility[target_stream] = (f"actor:{participant_ref}",)
        envelope = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.social.record_public_milling_notice_social_acknowledgment",
            command_version=1,
            principal_ref=_PRINCIPAL,
            actor_ref=participant_refs[0],
            project_ref=str(source["project_ref"]),
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={
                stream_id: revision
                for stream_id, revision in zip(target_streams, expected_target_revisions, strict=True)
            },
            read_set_revisions={
                str(notice.stream_id): expected_notice_revision,
                str(source["source_activity_stream_id"]): int(source["source_activity_revision"]),
                "gameplay:contracts": int(source["contract_head"]),
            },
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=notice_event_id,
            submitted_at="public-milling-notice-recorded",
            pinned_revisions={
                "notice": expected_notice_revision,
                "activity": int(source["source_activity_revision"]),
                "contract_created": int(source["source_contract_created_revision"]),
                "contract_fulfilled": int(source["source_contract_fulfilled_revision"]),
                "acquisition": int(source["source_acquisition_revision"]),
                "descriptor": 1,
                "schema": schema_pin.schema_version,
            },
            payload={},
        )
        batch = build_multi_stream_atomic_event_batch(
            command_id=envelope.command_id,
            principal_ref=envelope.principal_ref,
            expected_revisions=envelope.expected_revisions,
            read_stream_revisions=envelope.read_set_revisions,
            event_specs=event_specs,
            event_visibility_policies=visibility,
            idempotency_key=envelope.idempotency_key,
            causation_id=envelope.causation_id,
            correlation_id=envelope.correlation_id,
            pinned_revisions=envelope.pinned_revisions,
        )
        result = self._store.append_batch(batch)
        if not result.committed:
            return self._rejected(
                result.failure.error_code if result.failure is not None else "append_batch_failed"
            )
        receipt = SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"social_public_milling_notice_ack:{result.transaction_id}",),
            pinned_revisions=envelope.pinned_revisions,
        )
        settlement_plan = SettlementPlan(
            plan_id=f"settlement:{command_id}",
            command_id=command_id,
            expected_revision_vector=dict(envelope.expected_revisions),
            proposals=(),
            event_mapping={_PUBLIC_MILLING_ACK_EVENT: target_streams},
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        return self._committed_result(receipt, settlement_plan=settlement_plan)

    def settle_private_follow_on(self, *, intent: object) -> SocialFactAuthorityResult:
        """Record the fixed two-party actor-private follow-on from a notice."""
        from app.gameplay.closed_generic_gameplay_families import PrivateFollowOnIntent

        try:
            typed_intent = intent if isinstance(intent, PrivateFollowOnIntent) else PrivateFollowOnIntent.model_validate(intent)
            notice = self._store.get_event(typed_intent.notice_event_id)
        except Exception:
            return self._rejected("private_follow_on_source_missing")
        if self._package_registry is not None:
            resolved, failure = self._resolve_private_follow_on_row(
                notice=notice,
                expected_notice_revision=typed_intent.expected_notice_revision,
            )
            if failure is not None or resolved is None:
                return self._rejected(failure or "private_follow_on_source_conflict")
            manifest, declaration, binding, content, source = resolved
            return self._record_private_follow_on_generic(
                notice=notice,
                expected_notice_revision=typed_intent.expected_notice_revision,
                command_id=typed_intent.command_id,
                correlation_id=typed_intent.correlation_id,
                manifest=manifest,
                declaration=declaration,
                binding=binding,
                content=content,
                source=source,
            )
        source, failure = self._public_milling_notice_source(notice, typed_intent.expected_notice_revision)
        if failure is not None or source is None:
            return self._rejected("private_follow_on_source_conflict")
        participants = (_PUBLIC_MILLING_PROVIDER, str(source["receiver_ref"]))
        prior_event = next(
            (
                event for event in self._store.read_events()
                if event.event_type == _PUBLIC_MILLING_ACK_EVENT
                and event.payload.get("family_ref") == "private_follow_on@1"
                and event.payload.get("source_notice_event_id") == notice.event_id
            ),
            None,
        )
        if prior_event is not None:
            prior_batch = next(
                (batch for batch in self._store.read_transactions() if any(item.event_id == prior_event.event_id for item in batch.events)),
                None,
            )
            prior_result = self._store.get_by_idempotency(
                _PRINCIPAL,
                prior_batch.idempotency_record.idempotency_key if prior_batch is not None else "",
            )
            if prior_result is not None and prior_event.correlation_id == typed_intent.correlation_id:
                receipt = SettlementReceipt.from_append_result(
                    result=prior_result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
                    audit_refs=(f"private_follow_on:{prior_result.transaction_id}",),
                )
                return self._committed_result(receipt, settlement_plan=None)
            return self._rejected("private_follow_on_idempotency_key_reused")
        target_revisions = tuple(
            self._store.get_stream_head(f"gameplay:social:public-milling-notice-acknowledgment:{participant}")
            for participant in participants
        )
        key = (
            f"social:public-milling-notice-ack:{notice.event_id}:{notice.stream_revision}:"
            f"{target_revisions[0]}:{target_revisions[1]}:v1"
        )
        result = self.record_public_milling_notice_social_acknowledgment(
            notice_event_id=notice.event_id,
            expected_notice_revision=notice.stream_revision,
            expected_target_revisions=target_revisions,
            command_id=typed_intent.command_id,
            idempotency_key=key,
            causation_id=notice.event_id,
            correlation_id=typed_intent.correlation_id,
            family_ref="private_follow_on@1",
        )
        return result

    def _resolve_private_follow_on_row(
        self,
        *,
        notice: object,
        expected_notice_revision: int,
    ) -> tuple[tuple[object, object, object, object, dict[str, object]] | None, str | None]:
        from app.gameplay.closed_generic_gameplay_families import PrivateFollowOnContent

        active = self._package_registry.active_patch_set if self._package_registry is not None else None
        if active is None:
            return None, "private_follow_on_package_inactive"
        try:
            manifests = self._package_registry.active_manifests(active.active_patch_set_revision)
        except Exception:
            return None, "private_follow_on_package_inactive"
        source, failure = self._private_follow_on_source(notice, expected_notice_revision)
        if failure is not None or source is None:
            return None, "private_follow_on_source_conflict"
        source_family_ref = str(source["source_fact_family_ref"])
        candidates: list[tuple[object, object, object, PrivateFollowOnContent, dict[str, object]]] = []
        for manifest in manifests:
            extension = manifest.platform_extension
            if extension is None:
                continue
            declarations = {item.declaration_ref: item for item in extension.outcome_declarations}
            for request in extension.capability_binding_requests:
                if request.capability_ref != "capability:private-follow-on@1":
                    continue
                declaration = declarations.get(request.declaration_ref)
                if declaration is None or declaration.outcome_family_ref != "outcome:private-follow-on@1":
                    continue
                bindings = tuple(
                    binding
                    for binding in active.capability_bindings
                    if binding.binding_ref == request.binding_ref
                    and binding.package_revision == manifest.patch_revision_id
                    and binding.descriptor_ref == "descriptor:private-follow-on@1"
                    and binding.active_patch_set_revision == active.active_patch_set_revision
                )
                if len(bindings) != 1:
                    continue
                definitions = tuple(
                    item for item in extension.package_definitions
                    if item.definition_ref in declaration.definition_refs
                )
                if len(definitions) != 1:
                    continue
                try:
                    content = PrivateFollowOnContent.model_validate(definitions[0].typed_content)
                except Exception:
                    continue
                if content.source_fact_family_ref != source_family_ref:
                    continue
                candidates.append((manifest, declaration, bindings[0], content, source))
        if not candidates:
            return None, "private_follow_on_content_invalid"
        if len(candidates) != 1:
            return None, "private_follow_on_binding_ambiguous"
        return candidates[0], None

    def _private_follow_on_source(
        self,
        notice: object,
        expected_notice_revision: int,
    ) -> tuple[dict[str, object] | None, str | None]:
        if notice.event_type == "gameplay.government.public_milling_notice_recorded":
            source, failure = self._public_milling_notice_source(notice, expected_notice_revision)
            if source is not None:
                source = {
                    **source,
                    "provider_ref": _PUBLIC_MILLING_PROVIDER,
                    "notice_kind": notice.payload.get("notice_kind"),
                    "source_fact_family_ref": "fact:government-public-milling-notice@1",
                }
            return source, failure
        if notice.event_type == "gameplay.government.public_workshop_notice_recorded":
            return self._public_workshop_notice_source(notice, expected_notice_revision)
        return None, "private_follow_on_source_conflict"

    def _record_private_follow_on_generic(
        self,
        *,
        notice: object,
        expected_notice_revision: int,
        command_id: str,
        correlation_id: str,
        manifest: object,
        declaration: object,
        binding: object,
        content: object,
        source: dict[str, object],
    ) -> SocialFactAuthorityResult:
        participant_refs = (str(source["provider_ref"]), str(source["receiver_ref"]))
        prior_event = next(
            (
                event for event in self._store.read_events()
                if event.event_type == _PUBLIC_MILLING_ACK_EVENT
                and event.payload.get("family_ref") == "private_follow_on@1"
                and event.payload.get("source_notice_event_id") == notice.event_id
            ),
            None,
        )
        if prior_event is not None:
            prior_batch = next(
                (
                    batch for batch in self._store.read_transactions()
                    if any(item.event_id == prior_event.event_id for item in batch.events)
                ),
                None,
            )
            prior_result = self._store.get_by_idempotency(
                _PRINCIPAL,
                prior_batch.idempotency_record.idempotency_key if prior_batch is not None else "",
            )
            if prior_result is not None and prior_event.correlation_id == correlation_id:
                receipt = SettlementReceipt.from_append_result(
                    result=prior_result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
                    audit_refs=(f"private_follow_on:{prior_result.transaction_id}",),
                )
                return self._committed_result(receipt, settlement_plan=None)
            return self._rejected("private_follow_on_idempotency_key_reused")
        target_revisions = tuple(
            self._store.get_stream_head(
                f"gameplay:social:public-milling-notice-acknowledgment:{participant}"
            )
            for participant in participant_refs
        )
        idempotency_key = (
            f"social:public-milling-notice-ack:{notice.event_id}:{notice.stream_revision}:"
            f"{target_revisions[0]}:{target_revisions[1]}:v1"
        )
        existing = self._store.get_by_idempotency(_PRINCIPAL, idempotency_key)
        if existing is not None:
            prior_events = tuple(
                event
                for event in self._store.read_events()
                if event.event_id in set(existing.committed_event_ids)
            )
            if (
                len(prior_events) == 2
                and all(event.event_type == _PUBLIC_MILLING_ACK_EVENT for event in prior_events)
                and all(event.payload.get("source_notice_event_id") == notice.event_id for event in prior_events)
                and all(event.causation_id == notice.event_id for event in prior_events)
                and all(event.correlation_id == correlation_id for event in prior_events)
            ):
                receipt = SettlementReceipt.from_append_result(
                    result=existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
                    audit_refs=(f"private_follow_on:{existing.transaction_id}",),
                )
                return self._committed_result(receipt, settlement_plan=None)
            return self._rejected("private_follow_on_idempotency_key_reused")
        event_specs: dict[str, tuple[tuple[str, Mapping[str, object]], ...]] = {}
        visibility: dict[str, tuple[str, ...]] = {}
        for participant_ref, counterpart_ref in zip(
            participant_refs,
            (participant_refs[1], participant_refs[0]),
            strict=True,
        ):
            target_stream = f"gameplay:social:public-milling-notice-acknowledgment:{participant_ref}"
            event_specs[target_stream] = (
                (
                    _PUBLIC_MILLING_ACK_EVENT,
                    {
                        "acknowledgment_ref": f"social-ack:public-milling-notice:{notice.event_id}:{participant_ref}",
                        "notice_event_id": notice.event_id,
                        "source_notice_event_id": notice.event_id,
                        "source_notice_revision": expected_notice_revision,
                        "source_notice_stream_id": notice.stream_id,
                        "source_notice_event_type": notice.event_type,
                        "source_fact_family_ref": content.source_fact_family_ref,
                        "marker_definition_ref": content.marker_definition_ref,
                        "participant_binding_ref": content.participant_binding_ref,
                        "participant_ref": participant_ref,
                        "counterpart_ref": counterpart_ref,
                        "status": "acknowledged",
                        "notice_kind": source["notice_kind"],
                        "organization_ref": source["provider_ref"],
                        "facility_ref": source["facility_ref"],
                        "project_ref": source["project_ref"],
                        "jurisdiction_ref": source["jurisdiction_ref"],
                        "source_activity_event_id": source["source_activity_event_id"],
                        "source_activity_revision": source["source_activity_revision"],
                        "source_contract_created_event_id": source["source_contract_created_event_id"],
                        "source_contract_created_revision": source["source_contract_created_revision"],
                        "source_contract_fulfilled_event_id": source["source_contract_fulfilled_event_id"],
                        "source_contract_fulfilled_revision": source["source_contract_fulfilled_revision"],
                        "source_acquisition_event_id": source["source_acquisition_event_id"],
                        "source_acquisition_revision": source["source_acquisition_revision"],
                        "policy_revision": content.policy_revision_ref,
                        "descriptor_ref": "descriptor:private-follow-on@1",
                        "descriptor_revision": "descriptor:private-follow-on@1",
                        "catalog_ref": "inf:private-follow-on@1",
                        "schema_ref": "schema:p5:social:public-milling-notice-acknowledged",
                        "schema_version": 1,
                        "schema_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        "registry_ref": self._registry.registry_ref,
                        "registry_revision": self._registry.registry_revision,
                        "registry_digest": self._registry.registry_digest,
                        "package_revision": manifest.patch_revision_id,
                        "content_digest": manifest.content_digest,
                        "declaration_ref": declaration.declaration_ref,
                        "declaration_digest": declaration.declaration_digest,
                        "active_patch_set_revision": binding.active_patch_set_revision,
                        "terminal": "v1_terminal_no_compensation",
                        "family_ref": "private_follow_on@1",
                    },
                ),
            )
            visibility[target_stream] = (f"actor:{participant_ref}",)
        envelope = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.social.settle_private_follow_on",
            command_version=1,
            principal_ref=_PRINCIPAL,
            actor_ref=participant_refs[0],
            project_ref=str(source["project_ref"]),
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={
                f"gameplay:social:public-milling-notice-acknowledgment:{participant}": revision
                for participant, revision in zip(participant_refs, target_revisions, strict=True)
            },
            read_set_revisions={
                str(notice.stream_id): expected_notice_revision,
                str(source["source_activity_stream_id"]): int(source["source_activity_revision"]),
                "gameplay:contracts": int(source["contract_head"]),
            },
            causation_id=notice.event_id,
            correlation_id=correlation_id,
            source_ref=notice.event_id,
            submitted_at="private-follow-on-source-notice",
            pinned_revisions={
                "notice": expected_notice_revision,
                "activity": int(source["source_activity_revision"]),
                "contract_created": int(source["source_contract_created_revision"]),
                "contract_fulfilled": int(source["source_contract_fulfilled_revision"]),
                "acquisition": int(source["source_acquisition_revision"]),
                "descriptor": 1,
            },
            payload={},
        )
        batch = build_multi_stream_atomic_event_batch(
            command_id=envelope.command_id,
            principal_ref=envelope.principal_ref,
            expected_revisions=envelope.expected_revisions,
            read_stream_revisions=envelope.read_set_revisions,
            event_specs=event_specs,
            event_visibility_policies=visibility,
            idempotency_key=envelope.idempotency_key,
            causation_id=envelope.causation_id,
            correlation_id=correlation_id,
            pinned_revisions=envelope.pinned_revisions,
        )
        result = self._store.append_batch(batch)
        if not result.committed:
            return self._rejected(result.failure.error_code if result.failure is not None else "append_batch_failed")
        receipt = SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"private_follow_on:{result.transaction_id}",),
            pinned_revisions=envelope.pinned_revisions,
        )
        settlement_plan = SettlementPlan(
            plan_id=f"settlement:{command_id}",
            command_id=command_id,
            expected_revision_vector=dict(envelope.expected_revisions),
            proposals=(),
            event_mapping={_PUBLIC_MILLING_ACK_EVENT: tuple(envelope.expected_revisions)},
            idempotency_key=idempotency_key,
            causation_id=envelope.causation_id,
            correlation_id=correlation_id,
        )
        return self._committed_result(receipt, settlement_plan=settlement_plan)

    def public_milling_notice_social_acknowledgment_view_for(
        self, *, participant_ref: str, checkpoint_at: int | None = None
    ) -> PublicMillingNoticeSocialAcknowledgmentView:
        if not participant_ref or checkpoint_at is not None and checkpoint_at < 0:
            raise ValueError("public_milling_notice_social_acknowledgment_scope_invalid")
        stream_id = f"gameplay:social:public-milling-notice-acknowledgment:{participant_ref}"
        events = sorted(
            (
                event
                for event in self._store.read_stream(stream_id)
                if event.event_type == _PUBLIC_MILLING_ACK_EVENT
                and event.visibility_policy == f"actor:{participant_ref}"
            ),
            key=lambda event: (event.global_sequence, event.event_id),
        )
        max_sequence = max((event.global_sequence for event in self._store.read_events()), default=0)
        if checkpoint_at is not None and checkpoint_at > max_sequence:
            raise ValueError("public_milling_notice_social_acknowledgment_checkpoint_invalid")
        for event in events:
            try:
                notice = self._store.get_event(str(event.payload.get("source_notice_event_id")))
            except KeyError as exc:
                raise ValueError("public_milling_notice_social_acknowledgment_replay_invalid") from exc
            source, failure = self._private_follow_on_source(
                notice,
                int(event.payload.get("source_notice_revision", -1)),
            )
            if (
                failure is not None
                or event.payload.get("participant_ref") != participant_ref
                or event.payload.get("source_notice_event_id") != notice.event_id
                or event.payload.get("facility_ref") != source["facility_ref"]
                or event.payload.get("project_ref") != source["project_ref"]
                or event.payload.get("jurisdiction_ref") != source["jurisdiction_ref"]
                or event.payload.get("source_activity_event_id") != source["source_activity_event_id"]
                or event.payload.get("source_contract_created_event_id")
                != source["source_contract_created_event_id"]
                or event.payload.get("source_contract_fulfilled_event_id")
                != source["source_contract_fulfilled_event_id"]
                or event.payload.get("source_acquisition_event_id")
                != source["source_acquisition_event_id"]
                or (
                    event.payload.get("source_fact_family_ref") is not None
                    and (
                        event.payload.get("source_fact_family_ref") != source.get("source_fact_family_ref")
                        or event.payload.get("policy_revision") != "policy:social-private-follow-on@1"
                        or event.payload.get("descriptor_ref") != "descriptor:private-follow-on@1"
                        or event.payload.get("descriptor_revision") != "descriptor:private-follow-on@1"
                        or event.payload.get("catalog_ref") != "inf:private-follow-on@1"
                    )
                )
                or (
                    event.payload.get("source_fact_family_ref") is None
                    and (
                        event.payload.get("policy_revision") != _PUBLIC_MILLING_ACK_POLICY
                        or event.payload.get("descriptor_ref") != _PUBLIC_MILLING_ACK_DESCRIPTOR
                        or event.payload.get("descriptor_revision") != _PUBLIC_MILLING_ACK_DESCRIPTOR
                        or event.payload.get("catalog_ref") != _PUBLIC_MILLING_ACK_CATALOG
                    )
                )
            ):
                raise ValueError("public_milling_notice_social_acknowledgment_replay_invalid")
        acknowledgments = tuple(dict(event.payload) for event in events)
        refs = tuple(str(item["acknowledgment_ref"]) for item in acknowledgments)
        source_revision_vector = {stream_id: self._store.get_stream_head(stream_id)}
        if events:
            notice = self._store.get_event(str(events[0].payload["source_notice_event_id"]))
            source_revision_vector[notice.stream_id] = notice.stream_revision
            source, _ = self._public_milling_notice_source(notice, notice.stream_revision)
            if source is not None:
                source_revision_vector[str(source["source_activity_stream_id"])] = int(
                    source["source_activity_revision"]
                )
                source_revision_vector["gameplay:contracts"] = int(source["contract_head"])
        projection = {
            "participant_ref": participant_ref,
            "acknowledgment_refs": refs,
            "acknowledgments": acknowledgments,
            "source_revision_vector": dict(sorted(source_revision_vector.items())),
        }
        return PublicMillingNoticeSocialAcknowledgmentView(
            participant_ref=participant_ref,
            acknowledgment_refs=refs,
            acknowledgments=acknowledgments,
            source_revision_vector=dict(sorted(source_revision_vector.items())),
            projection_hash=_digest(projection),
        )

    def _public_milling_notice_source(
        self, notice: object, expected_notice_revision: int
    ) -> tuple[dict[str, object] | None, str | None]:
        if notice.event_type != "gameplay.government.public_milling_notice_recorded":
            return None, "public_milling_notice_social_acknowledgment_source_invalid"
        if notice.visibility_policy != "project":
            return None, "public_milling_notice_social_acknowledgment_source_private"
        if (
            notice.stream_revision != expected_notice_revision
            or self._store.get_stream_head(notice.stream_id) != expected_notice_revision
            or not notice.stream_id.startswith("gameplay:government:public-notice:")
        ):
            return None, "public_milling_notice_social_acknowledgment_source_stale"
        payload = notice.payload
        if (
            payload.get("notice_kind") != "public_milling_session_completed"
            or payload.get("status") != "completed"
            or payload.get("organization_ref") != _PUBLIC_MILLING_PROVIDER
            or payload.get("policy_revision") != "policy:government-public-milling-notice@1"
            or payload.get("descriptor_ref") != "descriptor:government-public-milling-notice@1"
            or payload.get("descriptor_revision") != "descriptor:government-public-milling-notice@1"
            or payload.get("catalog_ref") != "inf:government-public-milling-notice@1"
        ):
            return None, "public_milling_notice_social_acknowledgment_source_invalid"
        required = (
            "source_activity_event_id",
            "source_contract_created_event_id",
            "source_contract_fulfilled_event_id",
            "facility_ref",
            "project_ref",
            "jurisdiction_ref",
        )
        if any(not isinstance(payload.get(key), str) or not payload.get(key) for key in required):
            return None, "public_milling_notice_social_acknowledgment_binding_invalid"
        try:
            activity = self._store.get_event(str(payload["source_activity_event_id"]))
            created = self._store.get_event(str(payload["source_contract_created_event_id"]))
            fulfilled = self._store.get_event(str(payload["source_contract_fulfilled_event_id"]))
            acquisition = self._store.get_event(str(created.payload["acquisition_event_id"]))
        except (KeyError, TypeError):
            return None, "public_milling_notice_social_acknowledgment_source_invalid"
        if (
            activity.event_type != "gameplay.organization.public_milling_activity_recorded"
            or activity.visibility_policy != "project"
            or activity.payload.get("organization_ref") != _PUBLIC_MILLING_PROVIDER
            or activity.payload.get("activity_kind") != "public_milling_session"
            or activity.payload.get("status") != "completed"
            or activity.event_id != payload["source_activity_event_id"]
            or activity.stream_revision != payload.get("source_activity_revision")
            or self._store.get_stream_head(activity.stream_id) != activity.stream_revision
            or activity.payload.get("facility_ref") != payload["facility_ref"]
            or activity.payload.get("project_ref") != payload["project_ref"]
            or activity.payload.get("source_contract_created_event_id") != created.event_id
            or activity.payload.get("source_contract_fulfilled_event_id") != fulfilled.event_id
        ):
            return None, "public_milling_notice_social_acknowledgment_source_invalid"
        party_refs = created.payload.get("party_refs")
        receiver_ref = acquisition.payload.get("owner_ref")
        if (
            created.event_type != "gameplay.contract.record_created"
            or created.visibility_policy != "authority_only"
            or created.payload.get("terms_ref") != _PUBLIC_MILLING_TERMS
            or created.payload.get("package_revision") != _PUBLIC_MILLING_PACKAGE
            or created.payload.get("facility_kind") != "mill_reinforced"
            or created.payload.get("facility_ref") != payload["facility_ref"]
            or created.payload.get("project_ref") != payload["project_ref"]
            or not isinstance(party_refs, list)
            or len(party_refs) != 2
            or party_refs[0] != _PUBLIC_MILLING_PROVIDER
            or not isinstance(party_refs[1], str)
            or party_refs[1] != receiver_ref
            or receiver_ref == _PUBLIC_MILLING_PROVIDER
        ):
            return None, (
                "public_milling_notice_social_acknowledgment_party_binding_invalid"
                if isinstance(party_refs, list) and len(party_refs) != 2
                else "public_milling_notice_social_acknowledgment_binding_conflict"
            )
        if (
            fulfilled.event_type != "gameplay.contract.record_fulfilled"
            or fulfilled.visibility_policy != "authority_only"
            or fulfilled.payload.get("contract_created_event_id") != created.event_id
            or fulfilled.payload.get("contract_id") != created.payload.get("contract_id")
            or acquisition.event_type != "gameplay.construction_production.facility_acquired"
            or acquisition.visibility_policy != "project"
            or acquisition.payload.get("facility_ref") != payload["facility_ref"]
            or acquisition.payload.get("plot_ref") != payload["project_ref"]
            or acquisition.payload.get("jurisdiction_ref") != payload["jurisdiction_ref"]
            or not isinstance(receiver_ref, str)
            or not receiver_ref.startswith(("organization:", "org:"))
        ):
            return None, "public_milling_notice_social_acknowledgment_binding_conflict"
        return {
            "receiver_ref": receiver_ref,
            "facility_ref": payload["facility_ref"],
            "project_ref": payload["project_ref"],
            "jurisdiction_ref": payload["jurisdiction_ref"],
            "source_activity_event_id": activity.event_id,
            "source_activity_revision": activity.stream_revision,
            "source_activity_stream_id": activity.stream_id,
            "source_contract_created_event_id": created.event_id,
            "source_contract_created_revision": created.stream_revision,
            "source_contract_fulfilled_event_id": fulfilled.event_id,
            "source_contract_fulfilled_revision": fulfilled.stream_revision,
            "source_acquisition_event_id": acquisition.event_id,
            "source_acquisition_revision": acquisition.stream_revision,
            "contract_head": self._store.get_stream_head("gameplay:contracts"),
        }, None

    def _public_workshop_notice_source(
        self, notice: object, expected_notice_revision: int
    ) -> tuple[dict[str, object] | None, str | None]:
        if (
            notice.event_type != "gameplay.government.public_workshop_notice_recorded"
            or notice.visibility_policy != "project"
            or notice.stream_revision != expected_notice_revision
            or self._store.get_stream_head(notice.stream_id) != expected_notice_revision
            or not notice.stream_id.startswith("gameplay:government:public-notice:")
        ):
            return None, "private_follow_on_source_conflict"
        payload = notice.payload
        if (
            payload.get("notice_kind") != "public_workshop_session_completed"
            or payload.get("status") != "completed"
            or payload.get("organization_ref") != "organization:municipal-assessment-office"
            or payload.get("policy_revision") != "policy:government-public-workshop-notice@1"
            or payload.get("descriptor_ref") != "descriptor:government-public-workshop-notice@1"
            or payload.get("descriptor_revision") != "descriptor:government-public-workshop-notice@1"
        ):
            return None, "private_follow_on_source_conflict"
        required = ("source_activity_event_id", "facility_ref", "project_ref", "jurisdiction_ref")
        if any(not isinstance(payload.get(key), str) or not payload.get(key) for key in required):
            return None, "private_follow_on_source_conflict"
        try:
            activity = self._store.get_event(str(payload["source_activity_event_id"]))
            created = self._store.get_event(str(activity.payload["source_contract_created_event_id"]))
            fulfilled = self._store.get_event(str(activity.payload["source_contract_fulfilled_event_id"]))
            acquisition = self._store.get_event(str(created.payload["acquisition_event_id"]))
        except (KeyError, TypeError):
            return None, "private_follow_on_source_conflict"
        receiver_ref = acquisition.payload.get("owner_ref")
        party_refs = created.payload.get("party_refs")
        if (
            activity.event_type != "gameplay.organization.public_workshop_activity_recorded"
            or activity.visibility_policy != "project"
            or activity.payload.get("organization_ref") != "organization:municipal-assessment-office"
            or activity.payload.get("activity_kind") != "public_workshop_session"
            or activity.payload.get("status") != "completed"
            or activity.event_id != payload["source_activity_event_id"]
            or activity.stream_revision != payload.get("source_activity_revision")
            or self._store.get_stream_head(activity.stream_id) != activity.stream_revision
            or activity.payload.get("facility_ref") != payload["facility_ref"]
            or activity.payload.get("project_ref") != payload["project_ref"]
            or created.event_type != "gameplay.contract.record_created"
            or created.visibility_policy != "authority_only"
            or created.payload.get("terms_ref") != "service:industrial-facility-public-workshop-session@1"
            or not isinstance(party_refs, list)
            or len(party_refs) != 2
            or party_refs[0] != "organization:municipal-assessment-office"
            or not isinstance(party_refs[1], str)
            or party_refs[1] != receiver_ref
            or fulfilled.event_type != "gameplay.contract.record_fulfilled"
            or fulfilled.visibility_policy != "authority_only"
            or fulfilled.payload.get("contract_created_event_id") != created.event_id
            or acquisition.event_type != "gameplay.construction_production.facility_acquired"
            or acquisition.visibility_policy != "project"
            or acquisition.payload.get("facility_ref") != payload["facility_ref"]
            or acquisition.payload.get("plot_ref") != payload["project_ref"]
            or acquisition.payload.get("jurisdiction_ref") != payload["jurisdiction_ref"]
            or not isinstance(receiver_ref, str)
            or not receiver_ref.startswith(("organization:", "org:"))
        ):
            return None, "private_follow_on_source_conflict"
        return {
            "provider_ref": "organization:municipal-assessment-office",
            "receiver_ref": receiver_ref,
            "facility_ref": payload["facility_ref"],
            "project_ref": payload["project_ref"],
            "jurisdiction_ref": payload["jurisdiction_ref"],
            "notice_kind": payload["notice_kind"],
            "source_fact_family_ref": "fact:government-public-workshop-notice@1",
            "source_activity_event_id": activity.event_id,
            "source_activity_revision": activity.stream_revision,
            "source_activity_stream_id": activity.stream_id,
            "source_contract_created_event_id": created.event_id,
            "source_contract_created_revision": created.stream_revision,
            "source_contract_fulfilled_event_id": fulfilled.event_id,
            "source_contract_fulfilled_revision": fulfilled.stream_revision,
            "source_acquisition_event_id": acquisition.event_id,
            "source_acquisition_revision": acquisition.stream_revision,
            "contract_head": self._store.get_stream_head("gameplay:contracts"),
        }, None

    def _public_workshop_notice_source(
        self, notice: object, expected_notice_revision: int
    ) -> tuple[dict[str, object] | None, str | None]:
        """Resolve the committed workshop notice chain for the generic follow-on."""
        if notice.event_type != "gameplay.government.public_workshop_notice_recorded":
            return None, "public_workshop_notice_social_acknowledgment_source_invalid"
        if notice.visibility_policy != "project":
            return None, "public_workshop_notice_social_acknowledgment_source_private"
        if (
            notice.stream_revision != expected_notice_revision
            or self._store.get_stream_head(notice.stream_id) != expected_notice_revision
            or not notice.stream_id.startswith("gameplay:government:public-notice:")
        ):
            return None, "public_workshop_notice_social_acknowledgment_source_stale"
        payload = notice.payload
        if (
            payload.get("notice_kind") != "public_workshop_session_completed"
            or payload.get("status") != "completed"
            or payload.get("organization_ref") != "organization:municipal-assessment-office"
            or payload.get("policy_revision") != "policy:government-public-workshop-notice@1"
            or payload.get("descriptor_ref") != "descriptor:government-public-workshop-notice@1"
            or payload.get("descriptor_revision") != "descriptor:government-public-workshop-notice@1"
        ):
            return None, "public_workshop_notice_social_acknowledgment_source_invalid"
        required = ("source_activity_event_id", "facility_ref", "project_ref", "jurisdiction_ref")
        if any(not isinstance(payload.get(key), str) or not payload.get(key) for key in required):
            return None, "public_workshop_notice_social_acknowledgment_binding_invalid"
        try:
            activity = self._store.get_event(str(payload["source_activity_event_id"]))
            created = self._store.get_event(str(activity.payload["source_contract_created_event_id"]))
            fulfilled = self._store.get_event(str(activity.payload["source_contract_fulfilled_event_id"]))
            acquisition = self._store.get_event(str(created.payload["acquisition_event_id"]))
        except (KeyError, TypeError):
            return None, "public_workshop_notice_social_acknowledgment_source_invalid"
        parties = created.payload.get("party_refs")
        receiver_ref = acquisition.payload.get("owner_ref")
        if (
            activity.event_type != "gameplay.organization.public_workshop_activity_recorded"
            or activity.visibility_policy != "project"
            or not isinstance(activity.payload.get("source_contract_fulfilled_revision"), int)
            or activity.payload.get("organization_ref") != payload["organization_ref"]
            or activity.payload.get("activity_kind") != "public_workshop_session"
            or activity.payload.get("status") != "completed"
            or activity.payload.get("facility_ref") != payload["facility_ref"]
            or activity.payload.get("project_ref") != payload["project_ref"]
            or created.event_type != "gameplay.contract.record_created"
            or created.visibility_policy != "authority_only"
            or created.payload.get("terms_ref") != "service:industrial-facility-public-workshop-session@1"
            or fulfilled.event_type != "gameplay.contract.record_fulfilled"
            or fulfilled.visibility_policy != "authority_only"
            or fulfilled.payload.get("contract_created_event_id") != created.event_id
            or acquisition.event_type != "gameplay.construction_production.facility_acquired"
            or acquisition.visibility_policy != "project"
            or acquisition.payload.get("facility_ref") != payload["facility_ref"]
            or acquisition.payload.get("plot_ref") != payload["project_ref"]
            or not isinstance(parties, list)
            or len(parties) != 2
            or not isinstance(parties[0], str)
            or not isinstance(parties[1], str)
            or parties[0] != payload["organization_ref"]
            or parties[1] != receiver_ref
            or receiver_ref == payload["organization_ref"]
        ):
            return None, "public_workshop_notice_social_acknowledgment_source_invalid"
        return {
            "provider_ref": str(payload["organization_ref"]),
            "receiver_ref": str(receiver_ref),
            "notice_kind": payload["notice_kind"],
            "source_fact_family_ref": "fact:government-public-workshop-notice@1",
            "facility_ref": payload["facility_ref"],
            "project_ref": payload["project_ref"],
            "jurisdiction_ref": payload["jurisdiction_ref"],
            "source_activity_event_id": activity.event_id,
            "source_activity_revision": activity.stream_revision,
            "source_activity_stream_id": activity.stream_id,
            "source_contract_created_event_id": created.event_id,
            "source_contract_created_revision": created.stream_revision,
            "source_contract_fulfilled_event_id": fulfilled.event_id,
            "source_contract_fulfilled_revision": fulfilled.stream_revision,
            "source_acquisition_event_id": acquisition.event_id,
            "source_acquisition_revision": acquisition.stream_revision,
            "contract_head": self._store.get_stream_head("gameplay:contracts"),
        }, None

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
    "PublicMillingNoticeSocialAcknowledgmentView",
    "SharedExperienceRecipientView",
    "SocialFactAuthority",
    "SocialFactAuthorityResult",
    "SocialRecipientView",
]
