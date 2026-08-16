"""Complete post-P5 proposal contracts over the existing Gameplay authority.

The module deliberately contains no persistence or transport owner.  It builds
typed proposals, validates them deterministically, and submits accepted
settlements through ``GameplayEventStore.append_batch`` only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayOutboxEntry, ReplayResult
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContractResult(ContractModel):
    accepted: bool
    committed: bool = False
    idempotency_status: Literal["new_commit", "duplicate_replayed", "rejected"] = "rejected"
    error_code: str | None = None
    transaction_id: str | None = None
    committed_event_ids: tuple[str, ...] = ()
    projection: dict[str, Any] = Field(default_factory=dict)
    projection_hash: str = ""
    audit: dict[str, Any] = Field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.accepted


class F1AProposal(ContractModel):
    proposal_id: str = Field(min_length=1)
    owner: Literal["world-runtime", "esm", "gameplay-authority"]
    capability: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    input_revision: int = Field(ge=0)
    effective_revision: int | None = Field(default=None, ge=0)
    semantic_tags: tuple[str, ...] = Field(min_length=1)
    entity_ref: str = Field(min_length=1)
    effect_type: str = Field(min_length=1)
    effect_payload: dict[str, Any] = Field(default_factory=dict)
    rule_id: str = Field(min_length=1)
    dependency_refs: tuple[str, ...] = ()
    dependency_graph: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    revision_pins: dict[str, int] = Field(default_factory=dict)
    causal_refs: tuple[str, ...] = ()
    time_request: dict[str, Any] | None = None
    idempotency_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def unique_refs(self) -> "F1AProposal":
        if len(set(self.semantic_tags)) != len(self.semantic_tags) or len(set(self.dependency_refs)) != len(self.dependency_refs):
            raise ValueError("duplicate_contract_reference")
        if len(set(self.causal_refs)) != len(self.causal_refs):
            raise ValueError("duplicate_causal_reference")
        return self


class F1ATimeRequest(ContractModel):
    """A proposal to an existing authority, never a clock or scheduler."""

    authority_ref: Literal["world-runtime", "esm", "gameplay-authority"]
    request_kind: Literal["defer_effect", "expire_effect", "settlement_window"]
    requested_at: datetime
    expires_at: datetime | None = None


class F1BProjectionProposal(ContractModel):
    proposal_id: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    jurisdiction_scope: str = Field(min_length=1)
    requester_scope: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    visibility: Literal["public", "actor_memory", "private_evidence"]
    domain: Literal["relationship", "identity", "reputation", "family", "knowledge", "belief", "perception"] = "relationship"
    operation: Literal["upsert", "merge", "revoke", "forget"] = "upsert"
    content: dict[str, Any] = Field(default_factory=dict)
    revision: int = Field(ge=0)
    retention_until: datetime | None = None
    conflict_set: tuple[str, ...] = ()
    revoked_source_event_id: str | None = None
    idempotency_key: str = Field(min_length=1)

    @property
    def projection_layer(self) -> str:
        return self.visibility


class F1CManifest(ContractModel):
    package_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    schemas: tuple[str, ...] = Field(min_length=1)
    dependencies: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    migration_id: str = Field(min_length=1)
    rollback_target: str = Field(min_length=1)
    trusted_source: str = Field(min_length=1)
    signature: str = Field(min_length=1)
    digest: str = ""

    @model_validator(mode="after")
    def set_immutable_digest(self) -> "F1CManifest":
        calculated = canonical_digest(self.model_dump(exclude={"digest"}))
        if self.digest and self.digest != calculated:
            raise ValueError("manifest_digest_mismatch")
        object.__setattr__(self, "digest", calculated)
        return self


class PostP5Authority:
    """Proposal adapter for F1A/F1B/F1C using one existing event store."""

    _F1A_OWNERS = frozenset({"world-runtime", "esm", "gameplay-authority"})
    _F1C_PERMISSIONS = {"reader": frozenset({"preview"}), "editor": frozenset({"preview", "stage"}), "admin": frozenset({"preview", "stage", "activate", "rollback"})}

    def __init__(self, store: GameplayEventStore) -> None:
        self.store = store
        self._package_states: dict[str, str] = {}
        self._package_digests: dict[str, str] = {}

    @staticmethod
    def _result(result: AppendBatchResult, *, projection: dict[str, Any], audit: dict[str, Any]) -> ContractResult:
        if not result.committed and result.idempotency_status == "rejected":
            return ContractResult(accepted=False, committed=False, error_code=result.failure.error_code if result.failure else "rejected", transaction_id=result.transaction_id, audit=audit)
        return ContractResult(
            accepted=True,
            committed=result.committed,
            idempotency_status=result.idempotency_status,
            transaction_id=result.transaction_id,
            committed_event_ids=tuple(result.committed_event_ids),
            projection=projection,
            projection_hash=canonical_digest(projection),
            audit=audit,
        )

    def submit_f1a(self, proposal: F1AProposal) -> ContractResult:
        existing = self.store.get_by_idempotency(proposal.owner, proposal.idempotency_key)
        if existing is not None and existing.committed:
            return ContractResult(accepted=True, committed=True, idempotency_status="duplicate_replayed", transaction_id=existing.transaction_id, committed_event_ids=tuple(existing.committed_event_ids), audit={"contract": "f1a", "duplicate": True})
        head = self.store.get_stream_head(proposal.stream_id)
        if proposal.owner not in self._F1A_OWNERS:
            return ContractResult(accepted=False, error_code="owner_unauthorized")
        if not proposal.capability.startswith("gameplay."):
            return ContractResult(accepted=False, error_code="capability_unauthorized")
        if proposal.input_revision != head:
            return ContractResult(accepted=False, error_code="stale_revision")
        if proposal.rule_id in proposal.dependency_refs:
            return ContractResult(accepted=False, error_code="dependency_cycle")
        if self._has_dependency_cycle(proposal.dependency_graph):
            return ContractResult(accepted=False, error_code="dependency_cycle")
        if any(value < 0 for value in proposal.revision_pins.values()):
            return ContractResult(accepted=False, error_code="revision_pin_invalid")
        if proposal.effect_payload.get("conflict_refs"):
            return ContractResult(accepted=False, error_code="effect_conflict")
        time_request = self._validate_time_request(proposal.time_request)
        if isinstance(time_request, str):
            return ContractResult(accepted=False, error_code=time_request)
        payload = {
            "proposal_id": proposal.proposal_id,
            "owner": proposal.owner,
            "capability": proposal.capability,
            "semantic_tags": proposal.semantic_tags,
            "entity_ref": proposal.entity_ref,
            "effect_type": proposal.effect_type,
            "effect_payload": proposal.effect_payload,
            "rule_id": proposal.rule_id,
            "dependencies": proposal.dependency_refs,
            "causal_refs": proposal.causal_refs,
            "time_request": time_request.model_dump(mode="json") if time_request else None,
            "requested_revision": proposal.effective_revision or head,
        }
        event_specs = [("post_p5.f1a.effect_applied", payload)]
        if time_request is not None:
            event_specs.append(("post_p5.f1a.time_requested", {"proposal_id": proposal.proposal_id, **time_request.model_dump(mode="json")}))
        batch = build_atomic_event_batch(
            command_id=proposal.proposal_id,
            principal_ref=proposal.owner,
            stream_id=proposal.stream_id,
            expected_revision=head,
            event_specs=tuple(event_specs),
            idempotency_key=proposal.idempotency_key,
            causation_id=f"causation:{proposal.proposal_id}",
            correlation_id=f"correlation:{proposal.proposal_id}",
            pinned_revisions={proposal.stream_id: proposal.effective_revision or head, **proposal.revision_pins},
        )
        result = self.store.append_batch(self._with_outbox(batch, projection=payload))
        projection = {"stream_id": proposal.stream_id, "effect_type": proposal.effect_type, "causal_refs": list(proposal.causal_refs), "accepted": result.committed}
        return self._result(result, projection=projection, audit={"contract": "f1a", "proposal_digest": canonical_digest(proposal.model_dump(mode="json"))})

    def submit_f1b(self, proposal: F1BProjectionProposal) -> ContractResult:
        existing = self.store.get_by_idempotency(proposal.actor_ref, proposal.idempotency_key)
        if existing is not None and existing.committed:
            return ContractResult(accepted=True, committed=True, idempotency_status="duplicate_replayed", transaction_id=existing.transaction_id, committed_event_ids=tuple(existing.committed_event_ids), audit={"contract": "f1b", "duplicate": True})
        if proposal.jurisdiction_scope != proposal.requester_scope:
            return ContractResult(accepted=False, error_code="cross_scope_denied")
        if proposal.retention_until is not None and proposal.retention_until <= datetime.now(timezone.utc):
            return ContractResult(accepted=False, error_code="projection_expired")
        if proposal.revision != self.store.get_stream_head(f"social:{proposal.subject_ref}"):
            return ContractResult(accepted=False, error_code="stale_revision")
        if len(set(proposal.conflict_set)) != len(proposal.conflict_set):
            return ContractResult(accepted=False, error_code="conflict_merge_invalid")
        visible = dict(proposal.content)
        if proposal.visibility == "public":
            visible = {key: value for key, value in visible.items() if not key.lower().startswith(("private", "secret", "password"))}
        if proposal.operation in {"revoke", "forget"}:
            visible = {}
        elif proposal.operation == "merge":
            prior = self.store.read_stream(f"social:{proposal.subject_ref}")
            if prior:
                last_content = prior[-1].payload.get("content", {})
                if isinstance(last_content, dict):
                    visible = {**last_content, **visible}
        payload = {
            "source_event_id": proposal.source_event_id,
            "actor_ref": proposal.actor_ref,
            "subject_ref": proposal.subject_ref,
            "jurisdiction_scope": proposal.jurisdiction_scope,
            "provenance": proposal.provenance,
            "visibility": proposal.visibility,
            "domain": proposal.domain,
            "operation": proposal.operation,
            "content": visible,
            "retention_until": proposal.retention_until.isoformat() if proposal.retention_until else None,
            "conflict_set": sorted(proposal.conflict_set),
            "revoked_source_event_id": proposal.revoked_source_event_id,
        }
        stream_id = f"social:{proposal.subject_ref}"
        batch = build_atomic_event_batch(
            command_id=proposal.proposal_id,
            principal_ref=proposal.actor_ref,
            stream_id=stream_id,
            expected_revision=proposal.revision,
            event_specs=(("post_p5.f1b.projection_published", payload),),
            idempotency_key=proposal.idempotency_key,
            causation_id=proposal.source_event_id,
            correlation_id=f"correlation:{proposal.proposal_id}",
        )
        result = self.store.append_batch(self._with_outbox(batch, projection=payload))
        return self._result(result, projection=payload, audit={"contract": "f1b", "privacy_filtered": proposal.visibility == "public", "provenance": proposal.provenance})

    def _validate_manifest(self, manifest: F1CManifest) -> str | None:
        if not manifest.signature.startswith("trusted:") or manifest.trusted_source not in {"paralls-core", "paralls-review"}:
            return "untrusted_source"
        if manifest.migration_id.startswith("fail:"):
            return "migration_failed"
        if any(not value for value in (*manifest.schemas, *manifest.capabilities, *manifest.dependencies)):
            return "manifest_schema_invalid"
        if manifest.package_id in manifest.dependencies or any(not dependency.startswith(("gameplay.", "package:")) for dependency in manifest.dependencies):
            return "dependency_validation_failed"
        return None

    def decide_package(self, manifest: F1CManifest, *, principal: Literal["reader", "editor", "admin"], action: Literal["preview", "stage", "activate", "rollback"], surface: Literal["ui", "cli", "mcp"] = "ui") -> ContractResult:
        if action not in self._F1C_PERMISSIONS[principal]:
            return ContractResult(accepted=False, error_code="permission_denied", audit={"surface": surface, "principal": principal, "action": action})
        error = self._validate_manifest(manifest)
        if error:
            return ContractResult(accepted=False, error_code=error, audit={"surface": surface, "principal": principal, "action": action})
        current = self._package_states.get(manifest.package_id, "draft")
        required = {"preview": "preview", "stage": "staging", "activate": "active", "rollback": "rolled-back"}[action]
        if action == "stage" and current not in {"draft", "preview", "staging"}:
            return ContractResult(accepted=False, error_code="stale_activation")
        if action == "activate" and current not in {"staging"}:
            return ContractResult(accepted=False, error_code="stale_activation")
        if action == "rollback" and current != "active":
            return ContractResult(accepted=False, error_code="rollback_target_missing")
        if action == "preview":
            self._package_states[manifest.package_id] = "preview"
            self._package_digests[manifest.package_id] = manifest.digest
            return ContractResult(accepted=True, committed=False, projection={"state": "preview", "digest": manifest.digest}, projection_hash=manifest.digest, audit={"surface": surface, "principal": principal, "action": action, "manifest_digest": manifest.digest})
        stream_id = f"package:{manifest.package_id}"
        head = self.store.get_stream_head(stream_id)
        payload = {"package_id": manifest.package_id, "revision": manifest.revision, "manifest_digest": manifest.digest, "state": required, "rollback_target": manifest.rollback_target, "owner": manifest.owner, "audit_complete": True, "surface": surface, "principal": principal, "action": action}
        batch = build_atomic_event_batch(command_id=f"f1c:{manifest.package_id}:{action}:{manifest.revision}", principal_ref=principal, stream_id=stream_id, expected_revision=head, event_specs=((f"post_p5.f1c.package_{action}", payload),), idempotency_key=f"idem:{manifest.package_id}:{action}:{manifest.digest}", causation_id=f"manifest:{manifest.digest}", correlation_id=f"package:{manifest.package_id}")
        result = self.store.append_batch(self._with_outbox(batch, projection=payload))
        if result.committed:
            self._package_states[manifest.package_id] = required
            self._package_digests[manifest.package_id] = manifest.digest
        return self._result(result, projection=payload, audit={"surface": surface, "principal": principal, "action": action, "manifest_digest": manifest.digest, "audit_complete": True})

    def preview_package(self, manifest: F1CManifest, *, principal: Literal["reader", "editor", "admin"] = "reader") -> ContractResult:
        return self.decide_package(manifest, principal=principal, action="preview")

    def activate_package(self, manifest: F1CManifest, *, principal: Literal["reader", "editor", "admin"] = "admin") -> ContractResult:
        return self.decide_package(manifest, principal=principal, action="activate")

    def rollback_package(self, manifest: F1CManifest, *, principal: Literal["reader", "editor", "admin"] = "admin") -> ContractResult:
        return self.decide_package(manifest, principal=principal, action="rollback")

    def replay_f1a(self) -> tuple[ReplayResult, ReplayResult]:
        return self._replay_prefix("post_p5.f1a.")

    def replay_f1b(self) -> tuple[ReplayResult, ReplayResult]:
        return self._replay_prefix("post_p5.f1b.")

    def replay_f1c(self) -> tuple[ReplayResult, ReplayResult]:
        return self._replay_prefix("post_p5.f1c.")

    def _replay_prefix(self, prefix: str) -> tuple[ReplayResult, ReplayResult]:
        events = [event for event in self.store.read_events() if event.event_type.startswith(prefix)]
        replay = GameplayProjectionReplay(projector_id=f"projection:{prefix}", projector_version="v1")
        full = replay.full_replay(events)
        split = max(0, len(events) // 2)
        checkpoint = replay.create_checkpoint(events[:split])
        tail = replay.checkpoint_plus_tail_replay(checkpoint, events[split:])
        return full, tail

    @staticmethod
    def _has_dependency_cycle(graph: dict[str, tuple[str, ...]]) -> bool:
        visited: set[str] = set()
        visiting: set[str] = set()

        def walk(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            cyclic = any(walk(child) for child in graph.get(node, ()))
            visiting.remove(node)
            visited.add(node)
            return cyclic

        return any(walk(node) for node in graph)

    @staticmethod
    def _validate_time_request(value: dict[str, Any] | None) -> F1ATimeRequest | str | None:
        if value is None:
            return None
        legacy_expires = value.get("expires_at")
        if legacy_expires and not value.get("requested_at"):
            try:
                expires = datetime.fromisoformat(str(legacy_expires).replace("Z", "+00:00"))
            except ValueError:
                return "time_request_invalid"
            return "time_request_expired" if expires <= datetime.now(timezone.utc) else "time_request_invalid"
        try:
            request = F1ATimeRequest.model_validate(value)
        except Exception:
            return "time_request_invalid"
        if request.expires_at is not None and request.expires_at <= datetime.now(timezone.utc):
            return "time_request_expired"
        return request

    @staticmethod
    def _with_outbox(batch, *, projection: dict[str, Any]):
        event = batch.events[0]
        outbox = GameplayOutboxEntry(
            outbox_id=f"outbox:{event.event_id}",
            transaction_id=batch.transaction_id,
            event_id=event.event_id,
            global_sequence=0,
            topic="post_p5.scoped_projection",
            audience=str(projection.get("jurisdiction_scope", projection.get("owner", "scoped"))),
            payload_projection={"event_type": event.event_type, "projection": projection},
        )
        return batch.model_copy(update={"outbox_entries": [outbox]})
