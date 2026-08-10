from __future__ import annotations

import hashlib
import json

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch

from .models import ActivationGrant, ActivationProposal, ActivationReceipt


def _hash(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
        ).hexdigest()
    )


class ProfileActivationAuthority:
    """Authority for lifecycle facts; profile data remains registry-owned."""

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
        for event in self.store.read_stream(f"population:{world_ref}"):
            profile_ref = str(event.payload.get("profile_ref", ""))
            if profile_ref:
                event_status = event.event_type.rsplit(".", 1)[-1]
                state[profile_ref] = {
                    "status": "active" if event_status == "committed" else event_status,
                    "identity_digest": event.payload.get("identity_digest", ""),
                }
        return state

    def _receipt(
        self, proposal: ActivationProposal, result, status: str, digest: str
    ) -> ActivationReceipt:
        return self._receipt_from_result(
            result, proposal.profile_ref, digest, status, scope=proposal.scope_grant
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
