from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.gameplay.life_state_runtime import CanonicalLifeStateAuthority

if TYPE_CHECKING:
    from app.gameplay.resource_materialization import CharacterResourceMaterializationCaller

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
    resources: AppendBatchResult | None = None
    resource_stop_reason: str | None = None


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
        resource_materialization_caller: CharacterResourceMaterializationCaller | None = None,
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
        if resource_materialization_caller is not None and resource_materialization_caller.authority.store is not store:
            raise ValueError("activation_resource_store_mismatch")
        self.resource_materialization_caller = resource_materialization_caller

    def commit_and_spawn(
        self,
        proposal: ActivationProposal,
        *,
        presence_idempotency_key: str,
        presence_expected_revision: int,
        resource_timeline_ref: str | None = None,
        resource_world_tick: int | None = None,
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
        if presence.committed and self.resource_materialization_caller is not None:
            try:
                if (not resource_timeline_ref or type(resource_world_tick) is not int
                        or resource_world_tick < 0):
                    raise ValueError("activation_resource_temporal_source_missing")
                pins = self._resource_source_pins(proposal, presence)
                resource_key = f"resources:initial:{presence.committed_event_ids[0]}"
                # A retry may occur after the Population clock advances. Reuse
                # the durable resource receipt captured at the first attempt;
                # do not reinterpret the retry as a new temporal admission.
                prior = self.resource_materialization_caller.authority.store.get_by_idempotency(
                    "resource-template-consumer", resource_key
                )
                if prior is not None:
                    if not self._resource_receipt_matches(prior, proposal, presence, resource_timeline_ref):
                        raise ValueError("resource_idempotency_key_reused")
                    return ActivationPresenceResult(
                        activation=activation, presence=presence,
                        life_state=life_state, life_state_stop_reason=life_state_stop_reason,
                        resources=prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
                        recovery_required=not prior.committed,
                        resource_stop_reason=(prior.failure.error_code if prior.failure else None),
                    )
                resources = self.resource_materialization_caller.materialize(
                    actor_ref=proposal.profile_ref,
                    world_ref=proposal.world_ref,
                    timeline_ref=resource_timeline_ref,
                    world_tick=resource_world_tick,
                    idempotency_key=resource_key,
                    expected_revision=self.store.get_stream_head(
                        f"gameplay:resources:{proposal.profile_ref.removeprefix('character:')}"
                    ),
                    read_stream_revisions=pins,
                )
            except ValueError as exc:
                return ActivationPresenceResult(
                    activation=activation, presence=presence,
                    life_state=life_state, life_state_stop_reason=life_state_stop_reason,
                    recovery_required=True, resource_stop_reason=str(exc),
                )
            return ActivationPresenceResult(
                activation=activation, presence=presence, life_state=life_state,
                life_state_stop_reason=life_state_stop_reason, resources=resources,
                recovery_required=not resources.committed,
                resource_stop_reason=(resources.failure.error_code if resources.failure else None),
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

    def _resource_source_pins(self, proposal: ActivationProposal, presence: PresenceReceipt) -> dict[str, int]:
        """Revalidate domain facts before first resource write, atomically pinned at append."""
        activation_stream = f"population:{proposal.world_ref}"
        presence_stream = self.presence_authority.stream_id(proposal.world_ref)
        life_stream = f"gameplay:character:life:{proposal.profile_ref}"
        pins = {stream: self.store.get_stream_head(stream)
                for stream in (activation_stream, presence_stream, life_stream)}
        activations = [event for event in self.store.read_stream(activation_stream)
                       if event.payload.get("profile_ref") == proposal.profile_ref
                       and event.event_type.startswith("population.activation.")]
        presences = [event for event in self.store.read_stream(presence_stream)
                     if event.payload.get("character_ref") == proposal.profile_ref]
        if (not activations or activations[-1].event_type != "population.activation.committed"
                or activations[-1].event_id != presence.source_activation_event_id):
            raise ValueError("activation_resource_source_inactive")
        if (not presences or len(presence.committed_event_ids) != 1
                or presences[-1].event_type != "population.presence.spawned"
                or presences[-1].event_id != presence.committed_event_ids[0]):
            raise ValueError("activation_resource_presence_inactive")
        if any(event.payload.get("to_state") == "dead" for event in self.store.read_stream(life_stream)):
            raise ValueError("character_confirmed_dead")
        if any(self.store.get_stream_head(stream) != revision for stream, revision in pins.items()):
            raise ValueError("revision_conflict")
        return pins

    def _resource_receipt_matches(self, receipt, proposal: ActivationProposal,
                                  presence: PresenceReceipt, timeline_ref: str) -> bool:
        if not receipt.committed or receipt.failure is not None or len(receipt.committed_event_ids) != 3:
            return False
        tx = self.store.get_transaction(receipt.transaction_id)
        if (tx is None or tx.idempotency_record.principal_ref != "resource-template-consumer"
                or tx.idempotency_record.idempotency_key != f"resources:initial:{presence.committed_event_ids[0]}"):
            return False
        # Reuse the owner's transaction/event/revision/sequence verification.
        # Preserve the original temporal admission rather than freezing the retry tick.
        expected = tx.model_copy(update={"events": [
            event.model_copy(update={"stream_revision": 0, "global_sequence": 0})
            for event in tx.events
        ]}, deep=True)
        if not self.resource_materialization_caller.authority._receipt_is_complete(receipt, expected):
            return False
        try:
            events = [self.store.get_event(event_id) for event_id in receipt.committed_event_ids]
        except KeyError:
            return False
        actor = proposal.profile_ref.removeprefix("character:")
        return {event.payload.get("resource_id") for event in events} == {
            "core.stamina", "core.mana", "core.action_points",
        } and all(
            event.event_type == "gameplay.resource.materialized"
            and event.schema_version == 1
            and event.visibility_policy == "authority_only"
            and event.stream_id == f"gameplay:resources:{actor}"
            and event.payload.get("actor_ref") == actor
            and event.payload.get("world_ref") == proposal.world_ref
            and event.payload.get("timeline_ref") == timeline_ref
            for event in events
        )


__all__ = ["ActivationPresenceResult", "PopulationActivationPresenceService"]
