from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock

from app.character_agent.models.behavior_policy import (
    BehaviorPolicyConsumption,
    BehaviorPolicyRecord,
)
from app.character_agent.storage.session_store import CharacterAgentSessionStore


class BehaviorPolicyStore:
    """Rebuildable actor-private policy lifecycle backed by session events."""

    _POLICY_EVENT_TYPES = frozenset(
        {
            "character_behavior_policy_proposed",
            "character_behavior_policy_reconciled",
            "character_behavior_policy_consumed",
        }
    )
    _TERMINAL_STATUSES = frozenset({"expired", "superseded", "rolled_back", "rejected"})
    _TRANSITIONS = {
        "candidate": frozenset({"accepted", "rejected", "expired", "superseded"}),
        "accepted": frozenset({"applied", "rejected", "expired", "superseded", "rolled_back"}),
        "applied": frozenset({"applied", "expired", "superseded", "rolled_back"}),
    }

    def __init__(
        self,
        storage_root: str | Path | None = None,
        *,
        session_store: CharacterAgentSessionStore | None = None,
    ) -> None:
        self._lock = RLock()
        self._session_store = session_store or CharacterAgentSessionStore(storage_root)
        self._records_by_actor: dict[str, dict[str, BehaviorPolicyRecord]] = {}
        self._load()

    def propose(self, record: BehaviorPolicyRecord) -> BehaviorPolicyRecord:
        with self._lock:
            self._validate_record_context(record)
            records = self._records_by_actor.setdefault(record.actor_id, {})
            existing_by_key = self._record_for_idempotency(record.actor_id, record.idempotency_key)
            if existing_by_key is not None:
                if record.idempotency_key in existing_by_key.merged_idempotency_keys:
                    if existing_by_key.merged_idempotency_digests.get(record.idempotency_key) != self._proposal_digest(record):
                        raise ValueError("behavior_policy_idempotency_conflict")
                    return existing_by_key.model_copy(deep=True)
                if self._same_proposal(existing_by_key, record):
                    return existing_by_key.model_copy(deep=True)
                raise ValueError("behavior_policy_idempotency_conflict")
            existing_by_id = records.get(record.policy_id)
            if existing_by_id is not None:
                if existing_by_id.model_dump(mode="json") == record.model_dump(mode="json"):
                    return existing_by_id.model_copy(deep=True)
                raise ValueError("behavior_policy_id_conflict")
            if record.supersedes_policy_id:
                predecessor = records.get(record.supersedes_policy_id)
                if predecessor is None:
                    raise ValueError("behavior_policy_superseded_policy_not_found")
                self._transition(predecessor, status="superseded", now=record.created_at, action="superseded")
            compatible = self._compatible_failure(record)
            if compatible is not None:
                merged_keys = sorted(
                    set(compatible.merged_idempotency_keys)
                    | {compatible.idempotency_key, record.idempotency_key}
                )
                merged_digests = {
                    **compatible.merged_idempotency_digests,
                    compatible.idempotency_key: self._proposal_digest(compatible),
                    record.idempotency_key: self._proposal_digest(record),
                }
                merged = compatible.model_copy(update={
                    "failure_count": compatible.failure_count + record.failure_count,
                    "transition_revision": compatible.transition_revision + 1,
                    "merged_idempotency_keys": merged_keys,
                    "merged_idempotency_digests": merged_digests,
                })
                self._write_record(merged, event_type="character_behavior_policy_reconciled", producer_ts=record.created_at, action="failure_merged")
                return merged.model_copy(deep=True)
            self._write_record(
                record,
                event_type="character_behavior_policy_proposed",
                producer_ts=record.created_at,
                action="proposed",
            )
            return record.model_copy(deep=True)

    def get(self, actor_id: str, policy_id: str) -> BehaviorPolicyRecord:
        with self._lock:
            return self._get_owned(actor_id, policy_id).model_copy(deep=True)

    def accepted_snapshot(self, actor_id: str, *, now: int) -> dict[str, object]:
        """The sole L3-visible projection: accepted, evidenced, unexpired policy."""
        with self._lock:
            accepted: list[BehaviorPolicyRecord] = []
            for record in list(self._records_by_actor.get(actor_id, {}).values()):
                if record.status == "accepted" and now >= record.expires_at:
                    record = self._transition(record, status="expired", now=now, action="expired")
                if (
                    record.status == "accepted"
                    and record.evidence_refs
                    and record.consumed_count < record.max_consumptions
                ):
                    accepted.append(record)
            accepted.sort(key=lambda item: (-item.policy_revision, item.created_at, item.policy_id))
            record = accepted[0] if accepted else None
            return {
                "actor_id": actor_id,
                "record": record.model_dump(mode="json") if record is not None else None,
            }

    def continuity_snapshot(self, actor_id: str) -> dict[str, object]:
        with self._lock:
            return {
                "policy_revision": "policy:character-behavior:v1",
                "records": [
                    record.model_dump(mode="json")
                    for _, record in sorted(self._records_by_actor.get(actor_id, {}).items())
                ],
            }

    def restore_continuity_snapshot(self, actor_id: str, snapshot: dict[str, object]) -> None:
        with self._lock:
            raw_records = snapshot.get("records")
            if not isinstance(raw_records, list):
                raise ValueError("behavior_policy_snapshot_invalid")
            records = self._records_by_actor.setdefault(actor_id, {})
            for raw_record in raw_records:
                if not isinstance(raw_record, dict):
                    raise ValueError("behavior_policy_snapshot_invalid")
                record = BehaviorPolicyRecord.model_validate(raw_record)
                self._validate_record_context(record)
                if record.actor_id != actor_id:
                    raise ValueError("behavior_policy_snapshot_actor_mismatch")
                existing = records.get(record.policy_id)
                if existing is None:
                    records[record.policy_id] = record
                elif record.transition_revision > existing.transition_revision:
                    if not self._legal_restore_successor(existing, record):
                        raise ValueError("behavior_policy_snapshot_transition_forbidden")
                    records[record.policy_id] = record
                elif record.transition_revision == existing.transition_revision and record != existing:
                    raise ValueError("behavior_policy_snapshot_revision_conflict")

    def consume(
        self,
        actor_id: str,
        policy_id: str,
        turn_id: str,
        now: int,
        *,
        branch_id: str | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> BehaviorPolicyConsumption:
        with self._lock:
            record = self._get_owned(actor_id, policy_id)
            if not branch_id or not causation_id or not correlation_id:
                return BehaviorPolicyConsumption(record=record, applied=False, reason="missing_linkage")
            if turn_id in record.consumed_turn_ids:
                link = record.consumption_links.get(turn_id)
                if (
                    isinstance(link, dict)
                    and link.get("branch_id") == branch_id
                    and link.get("causation_id") == causation_id
                    and link.get("correlation_id") == correlation_id
                ):
                    return BehaviorPolicyConsumption(record=record, applied=True, replayed=True)
                return BehaviorPolicyConsumption(record=record, applied=False, reason="linkage_conflict")
            if now >= record.expires_at:
                if record.status != "expired":
                    record = self._transition(record, status="expired", now=now, action="expired")
                return BehaviorPolicyConsumption(record=record, applied=False, reason="expired")
            if record.consumed_count >= record.max_consumptions:
                return BehaviorPolicyConsumption(record=record, applied=False, reason="max_consumptions_reached")
            if record.status != "accepted":
                return BehaviorPolicyConsumption(record=record, applied=False, reason=record.status)
            consumption_links = dict(record.consumption_links)
            consumption_links[turn_id] = {
                "branch_id": branch_id,
                "causation_id": causation_id,
                "correlation_id": correlation_id,
            }
            updated = record.model_copy(
                update={
                    "status": "applied"
                    if record.consumed_count + 1 >= record.max_consumptions
                    else "accepted",
                    "consumed_count": record.consumed_count + 1,
                    "consumed_turn_ids": [*record.consumed_turn_ids, turn_id],
                    "consumption_links": consumption_links,
                    "transition_revision": record.transition_revision + 1,
                }
            )
            self._write_record(
                updated,
                event_type="character_behavior_policy_consumed",
                producer_ts=now,
                action="consumed",
                turn_id=turn_id,
            )
            return BehaviorPolicyConsumption(record=updated, applied=True)

    def reconcile_consumed_turn(
        self,
        actor_id: str,
        turn_id: str,
        outcome: str,
        now: int,
        *,
        branch_id: str | None = None,
        causation_id: str,
        correlation_id: str,
    ) -> BehaviorPolicyRecord | None:
        with self._lock:
            for record in self._records_by_actor.get(actor_id, {}).values():
                link = record.consumption_links.get(turn_id)
                if (
                    link
                    and branch_id
                    and link.get("branch_id") == branch_id
                    and link.get("causation_id") == causation_id
                    and link.get("correlation_id") == correlation_id
                ):
                    return self.reconcile_outcome(actor_id, record.policy_id, record.source_turn_id, outcome, now)
        return None

    def reconcile_outcome(
        self,
        actor_id: str,
        policy_id: str,
        source_turn_id: str,
        outcome: str,
        now: int,
    ) -> BehaviorPolicyRecord:
        with self._lock:
            record = self._get_owned(actor_id, policy_id)
            if record.source_turn_id != source_turn_id:
                raise ValueError("behavior_policy_source_turn_mismatch")
            if record.status in self._TERMINAL_STATUSES:
                return record.model_copy(deep=True)
            if now >= record.expires_at:
                return self._transition(record, status="expired", now=now, action="expired")
            normalized = outcome.strip().lower()
            if normalized in {"evidence_qualified", "accepted"}:
                status = "accepted" if record.evidence_refs else "rejected"
                if record.status == status:
                    return record.model_copy(deep=True)
                return self._transition(record, status=status, now=now, action=normalized)
            status_by_outcome = {
                "success": "rolled_back",
                "rolled_back": "rolled_back",
                "superseded": "superseded",
                "rejected": "rejected",
                "expired": "expired",
            }
            try:
                status = status_by_outcome[normalized]
            except KeyError as error:
                raise ValueError("behavior_policy_unknown_outcome") from error
            if record.status == status:
                return record.model_copy(deep=True)
            return self._transition(record, status=status, now=now, action=normalized)

    def _load(self) -> None:
        for actor_id, events in self._session_store.list_all_events().items():
            records = self._records_by_actor.setdefault(actor_id, {})
            for event in events:
                if event.get("event_type") not in self._POLICY_EVENT_TYPES:
                    continue
                payload = event.get("payload")
                if not isinstance(payload, dict):
                    raise ValueError("behavior_policy_event_invalid")
                raw_record = payload.get("record")
                if not isinstance(raw_record, dict):
                    raise ValueError("behavior_policy_event_invalid")
                record = BehaviorPolicyRecord.model_validate(raw_record)
                self._validate_record_context(record)
                if record.actor_id != actor_id:
                    raise ValueError("behavior_policy_event_actor_mismatch")
                metadata = payload.get("metadata")
                if not isinstance(metadata, dict) or metadata != self._metadata(record):
                    raise ValueError("behavior_policy_event_metadata_mismatch")
                existing = records.get(record.policy_id)
                if existing is None:
                    records[record.policy_id] = record
                elif record.transition_revision > existing.transition_revision:
                    if not self._legal_restore_successor(existing, record):
                        raise ValueError("behavior_policy_event_transition_forbidden")
                    records[record.policy_id] = record
                elif record.transition_revision == existing.transition_revision and record != existing:
                    raise ValueError("behavior_policy_event_revision_conflict")

    def _record_for_idempotency(self, actor_id: str, idempotency_key: str) -> BehaviorPolicyRecord | None:
        return next(
            (
                record
                for record in self._records_by_actor.get(actor_id, {}).values()
                if record.idempotency_key == idempotency_key or idempotency_key in record.merged_idempotency_keys
            ),
            None,
        )

    @staticmethod
    def _same_proposal(existing: BehaviorPolicyRecord, proposed: BehaviorPolicyRecord) -> bool:
        mutable_fields = {
            "status", "consumed_count", "consumed_turn_ids", "transition_revision",
            "failure_count", "merged_idempotency_keys",
            "merged_idempotency_digests",
        }
        existing_payload = existing.model_dump(mode="json", exclude=mutable_fields)
        proposed_payload = proposed.model_dump(mode="json", exclude=mutable_fields)
        return existing_payload == proposed_payload

    def _get_owned(self, actor_id: str, policy_id: str) -> BehaviorPolicyRecord:
        record = self._records_by_actor.get(actor_id, {}).get(policy_id)
        if record is not None:
            return record
        if any(policy_id in policies for policies in self._records_by_actor.values()):
            raise ValueError("behavior_policy_actor_forbidden")
        raise ValueError("behavior_policy_not_found")

    def _transition(
        self,
        record: BehaviorPolicyRecord,
        *,
        status: str,
        now: int,
        action: str,
    ) -> BehaviorPolicyRecord:
        if record.status in self._TERMINAL_STATUSES:
            return record.model_copy(deep=True)
        if status not in self._TRANSITIONS.get(record.status, frozenset()):
            raise ValueError("behavior_policy_transition_forbidden")
        updated = record.model_copy(update={"status": status, "transition_revision": record.transition_revision + 1})
        self._write_record(
            updated,
            event_type="character_behavior_policy_reconciled",
            producer_ts=now,
            action=action,
        )
        return updated

    def _write_record(
        self,
        record: BehaviorPolicyRecord,
        *,
        event_type: str,
        producer_ts: int,
        action: str,
        turn_id: str | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "record": record.model_dump(mode="json"),
            "action": action,
            "metadata": self._metadata(record),
        }
        if turn_id is not None:
            payload["turn_id"] = turn_id
        self._session_store.append_event(
            actor_id=record.actor_id,
            event_type=event_type,
            producer_ts=producer_ts,
            payload=deepcopy(payload),
        )
        self._records_by_actor.setdefault(record.actor_id, {})[record.policy_id] = record

    @staticmethod
    def _metadata(record: BehaviorPolicyRecord) -> dict[str, object]:
        return {
            "actor_id": record.actor_id, "branch_id": record.branch_id,
            "valid_at": record.valid_at, "causation_id": record.causation_id,
            "correlation_id": record.correlation_id, "source_revision": record.source_revision,
            "policy_revision": record.policy_revision, "transition_revision": record.transition_revision,
            "idempotency_key": record.idempotency_key,
        }

    @staticmethod
    def _validate_record_context(record: BehaviorPolicyRecord) -> None:
        if record.valid_at < record.created_at:
            raise ValueError("behavior_policy_valid_time_precedes_creation")
        if record.valid_at > record.expires_at:
            raise ValueError("behavior_policy_valid_time_after_expiry")

    @staticmethod
    def _proposal_digest(record: BehaviorPolicyRecord) -> str:
        payload = record.model_dump(
            mode="json",
            exclude={
                "status", "consumed_count", "consumed_turn_ids", "consumption_links",
                "transition_revision", "failure_count", "merged_idempotency_keys",
                "merged_idempotency_digests",
            },
        )
        return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    @classmethod
    def _legal_restore_successor(
        cls,
        existing: BehaviorPolicyRecord,
        incoming: BehaviorPolicyRecord,
    ) -> bool:
        return incoming.status == existing.status or incoming.status in cls._TRANSITIONS.get(existing.status, frozenset())

    def _compatible_failure(self, record: BehaviorPolicyRecord) -> BehaviorPolicyRecord | None:
        for existing in self._records_by_actor.get(record.actor_id, {}).values():
            if existing.status in self._TERMINAL_STATUSES:
                continue
            if (
                existing.policy_type == record.policy_type
                and existing.failed_intent == record.failed_intent
                and existing.branch_id == record.branch_id
                and 0 <= record.created_at - existing.created_at <= existing.failure_window
            ):
                return existing
        return None


__all__ = ["BehaviorPolicyStore"]
