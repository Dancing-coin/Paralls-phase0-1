from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent, GameplayOutboxEntry, OwnerAuthorizedFragment
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import (
    AppendDerivedSettlementRecipe,
    build_atomic_event_batch,
)
from app.gameplay.shared_contracts import GameplayCommandEnvelope

from .models import ActivationGrant, ActivationLock, ActivationProposal, ActivationReceipt, PendingChange


def _hash(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
        ).hexdigest()
    )


@dataclass(frozen=True)
class ActivationObligationBinding:
    binding_ref: str
    pending_kind: str
    target_owner_ref: str
    target_stream_pattern: str
    privacy_scope: str
    policy_ref: str | None = None
    policy_revision: str | None = None
    state_ref: str | None = None


class ActivationObligationBindingContract:
    """Closed reader for existing activation pending-to-owner rows."""

    _ROWS = (
        ActivationObligationBinding(
            binding_ref="activation-binding:survival-state-expiry:cold:v1",
            pending_kind="survival_state_expiry",
            target_owner_ref="actor_gameplay.survival_domain",
            target_stream_pattern="gameplay:survival:{profile_ref}",
            privacy_scope="project",
            policy_ref="policy:survival_state_expiry",
            policy_revision="1",
            state_ref="state:cold",
        ),
        ActivationObligationBinding(
            binding_ref="activation-binding:survival-state-expiry:dehydrated:v1",
            pending_kind="survival_state_expiry",
            target_owner_ref="actor_gameplay.survival_domain",
            target_stream_pattern="gameplay:survival:{profile_ref}",
            privacy_scope="project",
            policy_ref="policy:survival_state_expiry",
            policy_revision="1",
            state_ref="state:dehydrated",
        ),
        ActivationObligationBinding(
            binding_ref="activation-binding:survival-state-expiry:overheated:v1",
            pending_kind="survival_state_expiry",
            target_owner_ref="actor_gameplay.survival_domain",
            target_stream_pattern="gameplay:survival:{profile_ref}",
            privacy_scope="project",
            policy_ref="policy:survival_state_expiry",
            policy_revision="1",
            state_ref="state:overheated",
        ),
        ActivationObligationBinding(
            binding_ref="activation-binding:survival-state-expiry:fatigued:v1",
            pending_kind="survival_state_expiry",
            target_owner_ref="actor_gameplay.survival_domain",
            target_stream_pattern="gameplay:survival:{profile_ref}",
            privacy_scope="project",
            policy_ref="policy:survival_state_expiry",
            policy_revision="1",
            state_ref="state:fatigued",
        ),
        ActivationObligationBinding(
            binding_ref="activation-binding:schedule-gated-supply:v1",
            pending_kind="schedule_gated_supply",
            target_owner_ref="actor_gameplay.organization_domain",
            target_stream_pattern="existing-organization-stream-from-frozen-plan",
            privacy_scope="plan_report_scope",
        ),
    )

    @classmethod
    def closed_rows(cls) -> tuple[ActivationObligationBinding, ...]:
        return cls._ROWS

    @classmethod
    def resolve(cls, change: PendingChange) -> ActivationObligationBinding | None:
        kind = change.payload.get("kind")
        if kind == "schedule_gated_supply":
            digest = change.payload.get("plan_digest")
            if isinstance(digest, str) and digest.startswith("sha256:"):
                return cls._ROWS[4]
            return None
        if kind != "survival_state_expiry":
            return None
        obligation_id = change.payload.get("obligation_id")
        expected_revision = change.payload.get("expected_survival_revision")
        prefix = f"obligation:survival:state:{change.profile_ref}:"
        if (
            not isinstance(obligation_id, str)
            or not obligation_id.startswith(prefix)
            or change.payload.get("policy_revision") != "1"
            or not isinstance(expected_revision, int)
            or isinstance(expected_revision, bool)
            or expected_revision < 0
            or change.privacy_scope != "project"
        ):
            return None
        state_ref = obligation_id.removeprefix(prefix)
        return next(
            (
                row
                for row in cls._ROWS[:4]
                if row.state_ref == state_ref
            ),
            None,
        )

    @classmethod
    def by_ref(cls, binding_ref: object) -> ActivationObligationBinding | None:
        return next(
            (row for row in cls._ROWS if row.binding_ref == binding_ref), None
        )

    @staticmethod
    def is_legacy_unbound_survival_pending(change: PendingChange) -> bool:
        """Keep historical activation diagnostics unbound to any target owner."""
        expected_revision = change.payload.get("expected_survival_revision")
        return (
            change.payload.get("kind") == "survival_state_expiry"
            and isinstance(change.payload.get("obligation_id"), str)
            and str(change.payload["obligation_id"]).startswith(
                f"obligation:survival:state:{change.profile_ref}:"
            )
            and change.payload.get("policy_revision") == "1"
            and isinstance(expected_revision, int)
            and not isinstance(expected_revision, bool)
            and expected_revision >= 0
            and change.privacy_scope == "project"
        )


class ProfileActivationAuthority:
    """Authority for lifecycle facts; profile data remains registry-owned."""

    _PRINCIPAL = "world_runtime.activation_authority"
    _REGION_ASSIGNMENT_EVENT = "population.activation.region_assigned"

    def __init__(
        self,
        *,
        registry: CharacterProfileRegistry,
        store: GameplayEventStore,
        grants: tuple[ActivationGrant, ...] = (),
    ) -> None:
        self.registry = registry
        self.store = store
        self.grants = grants
        self._locks: dict[str, ActivationLock] = {}
        self._pending: dict[str, list[PendingChange]] = {}

    def resolve(self, profile_ref: str):
        """Resolve an existing authored profile without materializing state."""
        return self.registry.profile_ref(profile_ref)

    def commit(self, proposal: ActivationProposal) -> ActivationReceipt:
        stream = f"population:{proposal.world_ref}"
        identity_digest = ""
        try:
            identity_digest = self.registry.authored_identity_digest(
                proposal.profile_ref
            )
        except KeyError:
            return self._rejected(proposal, "profile_not_registered")
        if self.grants and not any(
            grant.profile_ref == proposal.profile_ref
            and grant.world_ref == proposal.world_ref
            and grant.package_revision == proposal.package_revision
            and grant.policy_revision == proposal.policy_revision
            and set(proposal.scope_grant).issubset(grant.scope_grant)
            for grant in self.grants
        ):
            return self._rejected(proposal, "package_scope_grant_denied")
        expected = proposal.expected_revisions.get(stream)
        if expected is None:
            return self._rejected(proposal, "activation_revision_required")
        existing = self.store.get_by_idempotency(
            proposal.source_ref, proposal.idempotency_key
        )
        if existing is not None:
            replayed = existing.model_copy(
                update={"idempotency_status": "duplicate_replayed"}
            )
            return self._receipt(proposal, replayed, "active", identity_digest)
        if self.store.get_stream_head(stream) != expected:
            return self._rejected(proposal, "revision_conflict")
        batch = build_atomic_event_batch(
            command_id=proposal.proposal_id,
            principal_ref=proposal.source_ref,
            stream_id=stream,
            expected_revision=expected,
            event_specs=[
                (
                    "population.activation.committed",
                    {
                        "profile_ref": proposal.profile_ref,
                        "identity_digest": identity_digest,
                        "world_ref": proposal.world_ref,
                        "package_revision": proposal.package_revision,
                        "policy_revision": proposal.policy_revision,
                        "scope_grant": list(proposal.scope_grant),
                        "cadence_class": proposal.cadence_class,
                        "activation_reason": proposal.activation_reason,
                    },
                )
            ],
            idempotency_key=proposal.idempotency_key,
            causation_id=proposal.proposal_id,
            correlation_id=proposal.correlation_id,
            pinned_revisions={"package": 1, "policy": 1},
        )
        result = self.store.append_batch(batch)
        if not result.committed:
            return self._rejected(
                proposal,
                result.failure.error_code if result.failure else "append_rejected",
            )
        return self._receipt(proposal, result, "active", identity_digest)

    def suspend(
        self, world_ref: str, profile_ref: str, *, expected_revision: int
    ) -> ActivationReceipt:
        return self._lifecycle(
            world_ref,
            profile_ref,
            expected_revision,
            "suspended",
            f"suspend:{world_ref}:{profile_ref}:{expected_revision}",
        )

    def requeue(
        self, world_ref: str, profile_ref: str, *, expected_revision: int
    ) -> ActivationReceipt:
        return self._lifecycle(
            world_ref,
            profile_ref,
            expected_revision,
            "requeued",
            f"requeue:{world_ref}:{profile_ref}:{expected_revision}",
        )

    def lock(self, *, world_ref: str, profile_ref: str, expected_revision: int) -> ActivationReceipt:
        stream = f"population:{world_ref}"
        if self.store.get_stream_head(stream) != expected_revision:
            return ActivationReceipt(committed=False, status="rejected", profile_ref=profile_ref, zero_write=True, stop_reason="revision_conflict")
        lock_ref = f"lock:{world_ref}:{profile_ref}"
        lock = ActivationLock(lock_ref=lock_ref, profile_ref=profile_ref, world_ref=world_ref, held_revision=expected_revision)
        result = self._lifecycle(world_ref, profile_ref, expected_revision, "locked", f"lock:{world_ref}:{profile_ref}:{expected_revision}")
        if result.committed:
            self._locks[lock_ref] = lock
        return result

    def record_pending(self, change: PendingChange) -> ActivationReceipt:
        lock = self._locks.get(change.lock_ref)
        if lock is None or lock.status != "active" or lock.profile_ref != change.profile_ref:
            return ActivationReceipt(committed=False, status="rejected", profile_ref=change.profile_ref, zero_write=True, stop_reason="activation_lock_missing")
        if change.expected_revision != lock.held_revision:
            return ActivationReceipt(committed=False, status="rejected", profile_ref=change.profile_ref, zero_write=True, stop_reason="revision_conflict")
        binding = ActivationObligationBindingContract.resolve(change)
        legacy_unbound = (
            binding is None
            and ActivationObligationBindingContract.is_legacy_unbound_survival_pending(change)
        )
        if binding is None and not legacy_unbound:
            return ActivationReceipt(committed=False, status="rejected", profile_ref=change.profile_ref, zero_write=True, stop_reason="pending_change_kind_unsupported")
        supplied_binding_ref = change.payload.get("binding_ref")
        binding_ref = binding.binding_ref if binding is not None else ""
        if supplied_binding_ref is not None and supplied_binding_ref != binding_ref:
            return ActivationReceipt(committed=False, status="rejected", profile_ref=change.profile_ref, zero_write=True, stop_reason="pending_binding_forged")
        kind = binding.pending_kind if binding is not None else "survival_state_expiry"
        plan_digest = change.payload.get("plan_digest")
        stream = f"population:{lock.world_ref}"
        digest = self.registry.authored_identity_digest(change.profile_ref)
        existing = self.store.get_by_idempotency(
            "world_runtime.activation_authority", f"pending:{change.change_ref}"
        )
        if existing is not None:
            if len(existing.committed_event_ids) == 1:
                prior = self.store.get_event(existing.committed_event_ids[0])
                expected_payload = {
                    "profile_ref": change.profile_ref,
                    "identity_digest": digest,
                    "world_ref": lock.world_ref,
                    "lock_ref": change.lock_ref,
                    "change_ref": change.change_ref,
                    "kind": kind,
                    "plan_digest": plan_digest,
                    "privacy_scope": change.privacy_scope,
                    "obligation_id": change.payload.get("obligation_id"),
                    "policy_revision": change.payload.get("policy_revision"),
                    "expected_survival_revision": change.payload.get("expected_survival_revision"),
                    "binding_ref": binding_ref,
                }
                if prior.event_type == "population.activation.pending_recorded" and prior.payload == expected_payload:
                    replayed = existing.model_copy(update={"idempotency_status": "duplicate_replayed"})
                    return self._receipt_from_result(replayed, change.profile_ref, digest, "locked")
            return ActivationReceipt(committed=False, status="rejected", profile_ref=change.profile_ref, zero_write=True, stop_reason="idempotency_key_reused")
        expected_revision = self.store.get_stream_head(stream)
        batch = build_atomic_event_batch(
            command_id=f"pending:{change.change_ref}",
            principal_ref="world_runtime.activation_authority",
            stream_id=stream,
            expected_revision=expected_revision,
            event_specs=[(
                "population.activation.pending_recorded",
                {
                    "profile_ref": change.profile_ref,
                    "identity_digest": digest,
                    "world_ref": lock.world_ref,
                    "lock_ref": change.lock_ref,
                    "change_ref": change.change_ref,
                    "kind": kind,
                    "plan_digest": plan_digest,
                    "privacy_scope": change.privacy_scope,
                    "obligation_id": change.payload.get("obligation_id"),
                    "policy_revision": change.payload.get("policy_revision"),
                    "expected_survival_revision": change.payload.get("expected_survival_revision"),
                    "binding_ref": binding_ref,
                },
            )],
            idempotency_key=f"pending:{change.change_ref}",
            causation_id=change.lock_ref,
            correlation_id=f"correlation:{lock.world_ref}",
        )
        result = self.store.append_batch(batch)
        if not result.committed:
            return ActivationReceipt(committed=False, status="rejected", profile_ref=change.profile_ref, zero_write=True, stop_reason=result.failure.error_code if result.failure else "append_rejected")
        self._pending.setdefault(change.lock_ref, []).append(change)
        return self._receipt_from_result(result, change.profile_ref, digest, "locked")

    def release_lock(self, *, lock_ref: str, expected_revision: int) -> ActivationReceipt:
        lock = self._locks.get(lock_ref)
        if lock is None:
            return ActivationReceipt(committed=False, status="rejected", profile_ref="unknown", zero_write=True, stop_reason="activation_lock_missing")
        stream = f"population:{lock.world_ref}"
        if self.store.get_stream_head(stream) != expected_revision:
            return ActivationReceipt(committed=False, status="rejected", profile_ref=lock.profile_ref, zero_write=True, stop_reason="revision_conflict")
        pending = [
            item for item in self.pending_projection(lock.world_ref).values()
            if item["lock_ref"] == lock_ref and item["status"] == "recorded"
        ]
        digest = self.registry.authored_identity_digest(lock.profile_ref)
        batch = build_atomic_event_batch(
            command_id=f"release:{lock_ref}:{expected_revision}", principal_ref="world_runtime.activation_authority", stream_id=stream, expected_revision=expected_revision,
            event_specs=[("population.activation.released", {"profile_ref": lock.profile_ref, "identity_digest": digest, "lock_ref": lock_ref, "pending_change_refs": [str(item["change_ref"]) for item in pending]})],
            idempotency_key=f"release:{lock_ref}:{expected_revision}", causation_id=lock_ref, correlation_id=f"correlation:{lock.world_ref}",
        )
        result = self.store.append_batch(batch)
        if not result.committed:
            return ActivationReceipt(committed=False, status="rejected", profile_ref=lock.profile_ref, zero_write=True, stop_reason=result.failure.error_code if result.failure else "append_rejected")
        self._locks[lock_ref] = lock.model_copy(update={"status": "released"})
        self._pending.pop(lock_ref, None)
        return self._receipt_from_result(result, lock.profile_ref, digest, "requeued")

    def pending_projection(self, world_ref: str) -> dict[str, dict[str, object]]:
        """Rebuild the admitted pending schedule rows from the activation stream."""
        pending: dict[str, dict[str, object]] = {}
        for event in self.store.read_stream(f"population:{world_ref}"):
            if event.event_type == "population.activation.pending_recorded":
                change_ref = str(event.payload.get("change_ref", ""))
                if change_ref:
                    pending[change_ref] = {
                        "change_ref": change_ref,
                        "lock_ref": str(event.payload.get("lock_ref", "")),
                        "profile_ref": str(event.payload.get("profile_ref", "")),
                        "world_ref": str(event.payload.get("world_ref", "")),
                        "kind": str(event.payload.get("kind", "")),
                        "plan_digest": str(event.payload.get("plan_digest", "")),
                        "privacy_scope": str(event.payload.get("privacy_scope", "")),
                        "obligation_id": event.payload.get("obligation_id"),
                        "policy_revision": event.payload.get("policy_revision"),
                        "expected_survival_revision": event.payload.get("expected_survival_revision"),
                        "binding_ref": event.payload.get("binding_ref"),
                        "status": "recorded",
                    }
            elif event.event_type == "population.activation.released":
                for change_ref in event.payload.get("pending_change_refs", []):
                    row = pending.get(str(change_ref))
                    if row is not None and row["lock_ref"] == event.payload.get("lock_ref"):
                        row["status"] = "released"
        return pending

    def pending_view_for(
        self, *, world_ref: str, reader_scope: str
    ) -> dict[str, dict[str, object]]:
        """Expose pending admissions only to their recorded scope or activation authority."""
        return {
            change_ref: row
            for change_ref, row in self.pending_projection(world_ref).items()
            if reader_scope == "authority:activation"
            or row["privacy_scope"] == reader_scope
        }

    def assign_profile_region(
        self,
        *,
        command: GameplayCommandEnvelope,
        world_ref: str,
        profile_ref: str,
        region_ref: str,
        region_evidence_event_id: str,
    ) -> ActivationReceipt:
        """Record one active profile's region from one committed Ecology fact.

        This remains a closed activation-owner row.  It does not infer presence
        from dossier or client state, and Ecology only supplies committed
        evidence; it cannot write the population stream itself.
        """
        stream = f"population:{world_ref}"
        if (
            command.command_type != "population.activation.assign_region"
            or command.principal_ref != self._PRINCIPAL
            or command.source_ref != self._PRINCIPAL
            or command.actor_ref != profile_ref
            or command.payload.get("region_ref") != region_ref
            or command.payload.get("visibility_scope") != "project"
        ):
            return self._region_assignment_rejected(profile_ref, "region_assignment_authority_required")
        try:
            digest = self.registry.authored_identity_digest(profile_ref)
        except KeyError:
            return self._region_assignment_rejected(profile_ref, "profile_not_registered")
        if self.projection(world_ref).get(profile_ref, {}).get("status") != "active":
            return self._region_assignment_rejected(profile_ref, "profile_not_active")
        try:
            evidence = self.store.get_event(region_evidence_event_id)
        except KeyError:
            return self._region_assignment_rejected(profile_ref, "ecology_region_evidence_missing")
        ecology_stream = f"gameplay:ecology:{region_ref}"
        record = evidence.payload.get("record")
        if (
            evidence.event_type != "gameplay.ecology.region.recorded"
            or evidence.stream_id != ecology_stream
            or evidence.visibility_policy != "project"
            or evidence.payload.get("record_ref") != region_ref
            or not isinstance(record, dict)
            or record.get("region_ref") != region_ref
        ):
            return self._region_assignment_rejected(profile_ref, "ecology_region_evidence_invalid")
        expected_activation_revision = command.expected_revisions.get(stream)
        expected_ecology_revision = command.read_set_revisions.get(ecology_stream)
        event_payload = {
            "profile_ref": profile_ref,
            "identity_digest": digest,
            "world_ref": world_ref,
            "region_ref": region_ref,
            "source_event_id": evidence.event_id,
            "source_stream_id": ecology_stream,
            "source_stream_revision": evidence.stream_revision,
            "source_record_revision": evidence.payload.get("source_revision"),
            "privacy_scope": "project",
        }
        existing = self.store.get_by_idempotency(
            self._PRINCIPAL, command.idempotency_key
        )
        if existing is not None:
            if len(existing.committed_event_ids) == 1:
                prior = self.store.get_event(existing.committed_event_ids[0])
                if (
                    prior.event_type == self._REGION_ASSIGNMENT_EVENT
                    and prior.payload == event_payload
                ):
                    return self._receipt_from_result(
                        existing.model_copy(update={"idempotency_status": "duplicate_replayed"}),
                        profile_ref,
                        digest,
                        "active",
                        scope=("project",),
                    )
            return self._region_assignment_rejected(profile_ref, "idempotency_key_reused")
        if (
            set(command.expected_revisions) != {stream}
            or set(command.read_set_revisions) != {ecology_stream}
            or expected_activation_revision != self.store.get_stream_head(stream)
            or expected_ecology_revision != self.store.get_stream_head(ecology_stream)
        ):
            return self._region_assignment_rejected(profile_ref, "revision_conflict")
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:activation:region:{world_ref}:{profile_ref}:{command.command_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="activation:profile-region-assignment:v1",
            expected_revisions={stream: expected_activation_revision},
            read_set_revisions={ecology_stream: expected_ecology_revision},
            pinned_revisions={"ecology_region_record": evidence.stream_revision},
            event_specs={stream: ((self._REGION_ASSIGNMENT_EVENT, event_payload),)},
            event_visibility_policies={stream: ("project",)},
        )
        recipe = AppendDerivedSettlementRecipe.from_fragments(
            command_id=command.command_id,
            idempotency_principal_ref=self._PRINCIPAL,
            idempotency_key=command.idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            fragments=(fragment,),
        )
        event = recipe.batch.events[0]
        batch = recipe.batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=recipe.batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="population.activation.scoped_projection",
                        audience="project",
                        payload_projection={
                            "profile_ref": profile_ref,
                            "region_ref": region_ref,
                            "event_type": self._REGION_ASSIGNMENT_EVENT,
                        },
                    )
                ]
            },
            deep=True,
        )
        result = self.store.append_batch(batch)
        if not result.committed:
            return self._region_assignment_rejected(
                profile_ref,
                result.failure.error_code if result.failure else "append_rejected",
            )
        return self._receipt_from_result(
            result, profile_ref, digest, "active", scope=("project",)
        )

    def profile_region_projection(self, world_ref: str) -> dict[str, dict[str, object]]:
        """Rebuild the fixed profile-to-region projection from activation events."""
        return self.profile_region_projection_from_events(
            self.store.read_stream(f"population:{world_ref}")
        )

    @classmethod
    def profile_region_projection_from_events(
        cls,
        events: Sequence[GameplayEvent],
        *,
        checkpoint_state: dict[str, dict[str, object]] | None = None,
    ) -> dict[str, dict[str, object]]:
        """Apply an ordered activation event tail onto a region projection checkpoint."""
        state = {
            profile_ref: dict(row)
            for profile_ref, row in (checkpoint_state or {}).items()
        }
        for event in events:
            if event.event_type != cls._REGION_ASSIGNMENT_EVENT:
                continue
            profile_ref = event.payload.get("profile_ref")
            region_ref = event.payload.get("region_ref")
            source_event_id = event.payload.get("source_event_id")
            if all(isinstance(value, str) and value for value in (profile_ref, region_ref, source_event_id)):
                state[profile_ref] = {
                    "region_ref": region_ref,
                    "source_event_id": source_event_id,
                    "privacy_scope": event.payload.get("privacy_scope"),
                }
        return state

    def profile_region_view_for(
        self, *, world_ref: str, reader_scope: str
    ) -> dict[str, dict[str, str]]:
        """Expose project region assignments, never an unrestricted presence view."""
        if reader_scope != "project":
            return {}
        active = self.projection(world_ref)
        return {
            profile_ref: {
                "region_ref": str(row["region_ref"]),
                "source_event_id": str(row["source_event_id"]),
            }
            for profile_ref, row in self.profile_region_projection(world_ref).items()
            if row.get("privacy_scope") == "project"
            and active.get(profile_ref, {}).get("status") == "active"
        }

    def _lifecycle(
        self,
        world_ref: str,
        profile_ref: str,
        expected_revision: int,
        status: str,
        command_id: str,
    ) -> ActivationReceipt:
        try:
            digest = self.registry.authored_identity_digest(profile_ref)
        except KeyError:
            return ActivationReceipt(
                committed=False,
                status="rejected",
                profile_ref=profile_ref,
                zero_write=True,
                stop_reason="profile_not_registered",
            )
        stream = f"population:{world_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref="world_runtime.activation_authority",
            stream_id=stream,
            expected_revision=expected_revision,
            event_specs=[
                (
                    f"population.activation.{status}",
                    {
                        "profile_ref": profile_ref,
                        "identity_digest": digest,
                        "world_ref": world_ref,
                    },
                )
            ],
            idempotency_key=command_id,
            causation_id=command_id,
            correlation_id=f"correlation:{world_ref}",
        )
        result = self.store.append_batch(batch)
        if not result.committed:
            return ActivationReceipt(
                committed=False,
                status="rejected",
                profile_ref=profile_ref,
                identity_digest=digest,
                zero_write=True,
                stop_reason=result.failure.error_code
                if result.failure
                else "append_rejected",
            )
        return self._receipt_from_result(result, profile_ref, digest, status)

    def projection(self, world_ref: str) -> dict[str, dict[str, object]]:
        state: dict[str, dict[str, object]] = {}
        lifecycle_events = {
            "population.activation.committed": "active",
            "population.activation.suspended": "suspended",
            "population.activation.requeued": "requeued",
            "population.activation.locked": "locked",
        }
        for event in self.store.read_stream(f"population:{world_ref}"):
            status = lifecycle_events.get(event.event_type)
            if status is None:
                continue
            profile_ref = str(event.payload.get("profile_ref", ""))
            if profile_ref:
                state[profile_ref] = {
                    "status": status,
                    "identity_digest": event.payload.get("identity_digest", ""),
                }
        return state

    def _receipt(
        self, proposal: ActivationProposal, result, status: str, digest: str
    ) -> ActivationReceipt:
        return self._receipt_from_result(
            result, proposal.profile_ref, digest, status, scope=proposal.scope_grant
        )

    @staticmethod
    def _region_assignment_rejected(profile_ref: str, reason: str) -> ActivationReceipt:
        return ActivationReceipt(
            committed=False,
            status="rejected",
            profile_ref=profile_ref,
            zero_write=True,
            stop_reason=reason,
        )

    def _receipt_from_result(
        self,
        result,
        profile_ref: str,
        digest: str,
        status: str,
        *,
        scope: tuple[str, ...] = (),
    ) -> ActivationReceipt:
        replay = GameplayProjectionReplay(
            projector_id="population-activation", projector_version="1"
        ).full_replay(self.store.read_events())
        return ActivationReceipt(
            committed=True,
            status=status,
            profile_ref=profile_ref,
            identity_digest=digest,
            committed_event_ids=tuple(result.committed_event_ids),
            revision_vector=dict(result.resulting_stream_revisions),
            replay_hash=replay.projection_hash,
            scope=scope,
            redaction="identity-and-status-only",
            zero_write=False,
            idempotency_status=result.idempotency_status,
        )

    @staticmethod
    def _rejected(proposal: ActivationProposal, reason: str) -> ActivationReceipt:
        return ActivationReceipt(
            committed=False,
            status="rejected",
            profile_ref=proposal.profile_ref,
            zero_write=True,
            stop_reason=reason,
        )
