"""Minimal event-sourced full-title authority, separate from custody and economy."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, OwnerAuthorizedFragment


class OwnershipRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class OwnershipRight:
    right_id: str
    asset_ref: str
    holder_ref: str
    source_event_id: str


@dataclass(frozen=True)
class OwnershipProjection:
    rights: Mapping[str, OwnershipRight]
    active_right_by_asset: Mapping[str, str]
    source_revision_vector: Mapping[str, int]
    projection_revision: str


class OwnershipProjector:
    _EVENT_TYPES = {"gameplay.ownership.right_granted", "gameplay.ownership.right_transferred"}

    def rebuild(self, events: Sequence[GameplayEvent]) -> OwnershipProjection:
        rights: dict[str, OwnershipRight] = {}
        by_asset: dict[str, str] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in self._EVENT_TYPES:
                continue
            payload = event.payload
            right_id = _text(payload, "right_id")
            asset_ref = _text(payload, "asset_ref")
            if event.event_type == "gameplay.ownership.right_granted":
                if right_id in rights or asset_ref in by_asset:
                    raise OwnershipRuntimeError("ownership_title_conflict")
                rights[right_id] = OwnershipRight(right_id, asset_ref, _text(payload, "holder_ref"), event.event_id)
                by_asset[asset_ref] = right_id
            else:
                prior = rights.get(right_id)
                if prior is None or prior.asset_ref != asset_ref:
                    raise OwnershipRuntimeError("ownership_right_missing")
                if prior.holder_ref != _text(payload, "from_holder_ref"):
                    raise OwnershipRuntimeError("ownership_right_holder_mismatch")
                rights[right_id] = OwnershipRight(right_id, asset_ref, _text(payload, "to_holder_ref"), event.event_id)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        frozen_rights = MappingProxyType(dict(sorted(rights.items())))
        frozen_assets = MappingProxyType(dict(sorted(by_asset.items())))
        frozen_revisions = MappingProxyType(dict(sorted(revisions.items())))
        return OwnershipProjection(frozen_rights, frozen_assets, frozen_revisions, f"ownership:{_digest([frozen_rights, frozen_assets, frozen_revisions])[:16]}")


class OwnershipAuthorityService:
    _PRINCIPAL = "actor_gameplay.ownership_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._projector = OwnershipProjector()

    def grant_initial_title(self, *, command_id: str, asset_ref: str, holder_ref: str, right_id: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        command = {"kind": "grant", "command_id": command_id, "asset_ref": asset_ref, "holder_ref": holder_ref, "right_id": right_id}
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        if not asset_ref or not holder_ref or not right_id or right_id in projection.rights or asset_ref in projection.active_right_by_asset:
            raise OwnershipRuntimeError("ownership_title_conflict")
        return self._append(command_id, idempotency_key, digest, "gameplay.ownership.right_granted", {"right_id": right_id, "asset_ref": asset_ref, "holder_ref": holder_ref}, causation_id, correlation_id, projection)

    def transfer_title(self, *, command_id: str, asset_ref: str, right_id: str, from_holder_ref: str, to_holder_ref: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        command = {"kind": "transfer", "command_id": command_id, "asset_ref": asset_ref, "right_id": right_id, "from_holder_ref": from_holder_ref, "to_holder_ref": to_holder_ref}
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        right = projection.rights.get(right_id)
        if right is None or right.asset_ref != asset_ref:
            raise OwnershipRuntimeError("ownership_right_missing")
        if right.holder_ref != from_holder_ref or not to_holder_ref:
            raise OwnershipRuntimeError("ownership_right_holder_mismatch")
        return self._append(command_id, idempotency_key, digest, "gameplay.ownership.right_transferred", {"right_id": right_id, "asset_ref": asset_ref, "from_holder_ref": from_holder_ref, "to_holder_ref": to_holder_ref}, causation_id, correlation_id, projection)

    def build_package_declared_negotiated_exchange_fragment(
        self,
        *,
        provider_holder_ref: str,
        receiver_holder_ref: str,
        source_ref: str,
        asset_ref: str,
        outcome_ref: str,
        package_revision: str,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        """Build the fixed INF-2AC ownership transfer fragment.

        Ownership computes the active right from committed title truth; the
        caller may not nominate a right_id directly for this admitted outcome.
        """
        if (
            not provider_holder_ref
            or not receiver_holder_ref
            or not source_ref
            or not asset_ref
            or not outcome_ref
            or not package_revision
        ):
            raise OwnershipRuntimeError("ownership_package_exchange_invalid")
        projection = self._projector.rebuild(self._store.read_events())
        stream_id = "gameplay:ownership"
        if projection.source_revision_vector.get(stream_id, 0) != expected_revision:
            raise OwnershipRuntimeError("revision_conflict")
        right_id = projection.active_right_by_asset.get(asset_ref)
        if right_id is None:
            raise OwnershipRuntimeError("ownership_package_exchange_source_ambiguous")
        right = projection.rights.get(right_id)
        if right is None or right.holder_ref != provider_holder_ref:
            raise OwnershipRuntimeError("ownership_right_holder_mismatch")
        return OwnerAuthorizedFragment(
            fragment_id=(
                "fragment:ownership:package-declared-negotiated-exchange:"
                f"{provider_holder_ref}:{receiver_holder_ref}:{outcome_ref}"
            ),
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="ownership:package-declared-negotiated-exchange@1",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={"ownership": expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.ownership.right_transferred",
                        {
                            "source_ref": source_ref,
                            "right_id": right.right_id,
                            "asset_ref": asset_ref,
                            "from_holder_ref": provider_holder_ref,
                            "to_holder_ref": receiver_holder_ref,
                            "outcome_ref": outcome_ref,
                            "package_revision": package_revision,
                            "source_event_id": right.source_event_id,
                            "source_selection_rule_ref": "exchange:unique-owned-source@1",
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("authority_only",)},
        )

    def _duplicate(self, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if record is None:
            return None
        if record.payload_digest != digest:
            raise OwnershipRuntimeError("idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if result is None:
            raise OwnershipRuntimeError("ownership_idempotency_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    def _append(self, command_id: str, idempotency_key: str, digest: str, event_type: str, payload: dict[str, str], causation_id: str, correlation_id: str, projection: OwnershipProjection) -> AppendBatchResult:
        stream_id = "gameplay:ownership"
        transaction_id = f"tx:{command_id}"
        event = {"event_id": f"evt:{command_id}:ownership", "event_type": event_type, "schema_version": 1, "stream_id": stream_id, "stream_revision": 0, "global_sequence": 0, "transaction_id": transaction_id, "command_id": command_id, "causation_id": causation_id, "correlation_id": correlation_id, "visibility_policy": "authority_only", "payload": payload}
        return self._store.append_batch({"transaction_id": transaction_id, "command_id": command_id, "expected_stream_revisions": {stream_id: projection.source_revision_vector.get(stream_id, 0)}, "pinned_revisions": {"ownership": projection.source_revision_vector.get(stream_id, 0)}, "events": [event], "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": idempotency_key, "payload_digest": digest}, "outbox_entries": [], "result_digest": _digest(event), "projection_refresh_hints": []})


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise OwnershipRuntimeError("ownership_event_payload_invalid")
    return value


def _digest(value: object) -> str:
    def default(item: object) -> object:
        if isinstance(item, Mapping):
            return dict(item)
        if hasattr(item, "__dict__"):
            return item.__dict__
        raise TypeError(type(item).__name__)
    return sha256(json.dumps(value, default=default, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


__all__ = ["OwnershipAuthorityService", "OwnershipProjection", "OwnershipProjector", "OwnershipRight", "OwnershipRuntimeError"]
