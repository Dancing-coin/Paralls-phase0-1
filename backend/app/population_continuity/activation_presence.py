from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.gameplay.life_state_runtime import CanonicalLifeStateAuthority

from .activation import ProfileActivationAuthority
from .models import ActivationProposal, ActivationReceipt
from .presence_runtime import CharacterSpawnRequest, PopulationPresenceAuthority, PresenceReceipt


@dataclass(frozen=True)
class ActivationPresenceResult:
    """Outcome of the production Population activation -> Presence handoff."""

    activation: ActivationReceipt
    presence: PresenceReceipt | None = None
    recovery_required: bool = False
    life_state: AppendBatchResult | None = None
    life_state_stop_reason: str | None = None


class PopulationActivationPresenceService:
    """Application caller joining existing activation and presence owners.

    This is a production application boundary, not a test helper.  It requires
    an existing ActivationGrant from the activation authority; it never mints a
    grant or identity.  A committed activation is retained when presence fails,
    so retry first reuses the activation receipt and only retries Presence.
    """

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        activation_authority: ProfileActivationAuthority,
        presence_authority: PopulationPresenceAuthority,
        producer_ref: str,
    ) -> None:
        if activation_authority.store is not store or presence_authority.store is not store:
            raise ValueError("activation_presence_store_mismatch")
        source = presence_authority._sources
        if (source is None or source._authority is not activation_authority
                or source._producer != producer_ref):
            raise ValueError("activation_presence_source_mismatch")
        self.store = store
        self.activation_authority = activation_authority
        self.presence_authority = presence_authority
        self.producer_ref = producer_ref
        self.life_state_authority = CanonicalLifeStateAuthority(store=store)

    def commit_and_spawn(
        self,
        proposal: ActivationProposal,
        *,
        presence_idempotency_key: str,
        presence_expected_revision: int,
    ) -> ActivationPresenceResult:
        # The authority's empty-grant mode is useful for legacy lifecycle locks,
        # but it cannot authorize a population candidate for entity creation.
        if not self.activation_authority.grants:
            rejected = ActivationReceipt(
                committed=False,
                status="rejected",
                profile_ref=proposal.profile_ref,
                zero_write=True,
                stop_reason="activation_source_unauthorized",
            )
            return ActivationPresenceResult(activation=rejected)
        if proposal.source_ref != self.producer_ref:
            rejected = ActivationReceipt(
                committed=False,
                status="rejected",
                profile_ref=proposal.profile_ref,
                zero_write=True,
                stop_reason="activation_source_unauthorized",
            )
            return ActivationPresenceResult(activation=rejected)

        activation = self.activation_authority.commit(proposal)
        if not activation.committed:
            return ActivationPresenceResult(activation=activation)
        if len(activation.committed_event_ids) != 1:
            return ActivationPresenceResult(activation=activation, recovery_required=True)
        try:
            source_event = self.store.get_event(activation.committed_event_ids[0])
        except KeyError:
            return ActivationPresenceResult(activation=activation, recovery_required=True)
        source_batch = self.store.get_transaction(source_event.transaction_id)
        if (
            source_event.event_type != "population.activation.committed"
            or source_event.stream_id != f"population:{proposal.world_ref}"
            or source_event.payload.get("profile_ref") != proposal.profile_ref
            or source_event.payload.get("world_ref") != proposal.world_ref
            or source_event.payload.get("package_revision") != proposal.package_revision
            or source_event.payload.get("policy_revision") != proposal.policy_revision
            or tuple(source_event.payload.get("scope_grant", ())) != tuple(proposal.scope_grant)
            or source_batch is None
            or source_batch.idempotency_record.principal_ref != proposal.source_ref
            or source_batch.idempotency_record.idempotency_key != proposal.idempotency_key
        ):
            return ActivationPresenceResult(activation=activation, recovery_required=True)

        presence = self.presence_authority.spawn(
            CharacterSpawnRequest(
                world_ref=proposal.world_ref,
                character_ref=proposal.profile_ref,
                activation_event_id=activation.committed_event_ids[0],
                idempotency_key=presence_idempotency_key,
                expected_revision=presence_expected_revision,
            )
        )
        life_state = None
        life_state_stop_reason = None
        if presence.committed:
            try:
                life_state = self._ensure_initial_life_state(proposal, activation, presence)
                if not life_state.committed:
                    life_state_stop_reason = life_state.failure.error_code if life_state.failure else "life_state_presence_append_rejected"
            except ValueError as exc:
                life_state_stop_reason = str(exc)
                life_state = self.life_state_authority._reject(
                    f"life-state:presence:{presence.committed_event_ids[0] if presence.committed_event_ids else 'missing'}",
                    life_state_stop_reason,
                )
            if life_state_stop_reason:
                return ActivationPresenceResult(
                    activation=activation, presence=presence,
                    recovery_required=True, life_state=life_state,
                    life_state_stop_reason=life_state_stop_reason,
                )
        return ActivationPresenceResult(
            activation=activation,
            presence=presence,
            life_state=life_state,
            life_state_stop_reason=life_state_stop_reason,
            recovery_required=not presence.committed,
        )

    def _ensure_initial_life_state(self, proposal: ActivationProposal,
                                   activation: ActivationReceipt,
                                   presence: PresenceReceipt) -> AppendBatchResult:
        """Create the first alive fact only after Presence has committed."""
        life_stream = f"gameplay:character:life:{proposal.profile_ref}"
        initial_alive = [event for event in self.store.read_stream(
            life_stream, event_type="gameplay.character.life_state_changed"
        ) if event.payload.get("to_state") == "alive"]
        if initial_alive:
            if len(initial_alive) != 1:
                raise ValueError("life_state_initial_receipt_invalid")
            # Reappearance keeps character life continuity. Validate the original
            # admission receipt instead of trusting an arbitrary alive row or
            # trying to initialize alive again for the new entity incarnation.
            original = initial_alive[0]
            result = self.life_state_authority.initialize_alive_from_presence(
                activation_event_id=original.payload.get("source_activation_event_id", ""),
                presence_event_id=original.payload.get("source_presence_event_id", ""),
                expected_activation_revision=original.payload.get("source_activation_revision"),
                expected_presence_revision=original.payload.get("source_presence_revision"),
                command_id=original.command_id,
                idempotency_key=f"life-state:presence:{original.payload.get('source_presence_event_id', '')}",
                causation_id=original.causation_id,
                correlation_id=original.correlation_id,
            )
            return result
        if len(activation.committed_event_ids) != 1 or len(presence.committed_event_ids) != 1:
            raise ValueError("life_state_presence_source_missing")
        activation_event = self.store.get_event(activation.committed_event_ids[0])
        presence_event = self.store.get_event(presence.committed_event_ids[0])
        result = self.life_state_authority.initialize_alive_from_presence(
            activation_event_id=activation_event.event_id,
            presence_event_id=presence_event.event_id,
            expected_activation_revision=activation_event.stream_revision,
            expected_presence_revision=presence_event.stream_revision,
            command_id=f"life-state:presence:{presence_event.event_id}",
            idempotency_key=f"life-state:presence:{presence_event.event_id}",
            causation_id=presence_event.event_id,
            correlation_id=activation_event.correlation_id,
        )
        return result

__all__ = ["ActivationPresenceResult", "PopulationActivationPresenceService"]
