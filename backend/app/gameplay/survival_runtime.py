"""Explicit Survival profile proposals; no inventory, account, or body ownership."""

from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.ecology_consumer_admission import EcologyConsumerAdmissionCheck
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import AtomicEventBatch, AppendBatchResult, GameplayEvent, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.patch_runtime import _canonical_digest
from app.gameplay.semantic_registry import SemanticRegistry, SemanticRegistryError
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.semantic_effects import EffectApplication, EffectLifecycleEvaluator, ResistanceProfile, StateDefinition
from app.gameplay.shared_contracts import GameplayCommandEnvelope, ScheduledObligation


class SurvivalMode(StrEnum):
    DISABLED = "disabled"
    NARRATIVE = "narrative"
    LIGHTWEIGHT = "lightweight"
    SIMULATION = "simulation"


class NeedDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    need_ref: str = Field(min_length=1)
    category: str = Field(min_length=1)
    decay_per_tick: float = Field(ge=0, le=1)


class NeedState(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    need_ref: str = Field(min_length=1)
    value: float = Field(ge=0, le=1)
    last_tick: int = Field(ge=0)


class ConsumptionPlan(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    need_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    required_owner_refs: tuple[str, ...] = ()
    pinned_revisions: dict[str, int] = Field(default_factory=dict)


class SurvivalPolicy(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    policy_ref: str = Field(min_length=1)
    mode: SurvivalMode
    revision: str = Field(min_length=1)


class SurvivalState(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state_ref: str = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    stacks: int = Field(ge=1)
    effective_magnitude: int = Field(ge=0)
    expiry_obligation_id: str | None = None


class SurvivalStateExpiryPolicy(StrictGameplayModel):
    """Closed Survival-owned policy for state expiry only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_ref: Literal["policy:survival_state_expiry"] = "policy:survival_state_expiry"
    policy_revision: str = Field(default="1", min_length=1)

    @staticmethod
    def obligation_id_for(*, actor_ref: str, state_ref: str) -> str:
        return f"obligation:survival:state:{actor_ref}:{state_ref}"

    def build_obligation(
        self,
        *,
        actor_ref: str,
        state_ref: str,
        due_tick: int,
        expected_revision: int,
        status: Literal["open", "due", "cancelled"] = "open",
    ) -> ScheduledObligation:
        stream_id = f"gameplay:survival:{actor_ref}"
        return ScheduledObligation(
            obligation_id=self.obligation_id_for(actor_ref=actor_ref, state_ref=state_ref),
            owner_ref=SurvivalAuthority._PRINCIPAL,
            due_tick=due_tick,
            policy_revision=self.policy_revision,
            status=status,
            source_refs=(f"state:{actor_ref}:{state_ref}", self.policy_ref),
            idempotency_key=f"obligation:survival:state:{actor_ref}:{state_ref}:{self.policy_revision}",
            expected_revisions={stream_id: expected_revision},
            visibility_scope="project",
        )


@dataclass(frozen=True)
class SurvivalProjection:
    needs: Mapping[tuple[str, str], NeedState]
    latest_plan: ConsumptionPlan | None
    source_revision_vector: Mapping[str, int]
    states: Mapping[tuple[str, str], SurvivalState]
    open_obligations: Mapping[str, int]


class SurvivalProjector:
    _TICK = "gameplay.survival.need_tick"
    _CONSUMPTION = "gameplay.survival.consumption_accepted"
    _STATE_APPLIED = "gameplay.survival.state_applied"
    _OBLIGATION_OPENED = "gameplay.survival.obligation_opened"
    _STATE_EXPIRED = "gameplay.survival.state_expired"
    _OBLIGATION_SETTLED = "gameplay.survival.obligation_settled"
    _STATE_DISPELLED = "gameplay.survival.state_dispelled"
    _STATE_TRANSFORMED = "gameplay.survival.state_transformed"
    _STATE_COMPENSATED = "gameplay.survival.state_compensated"
    _OBLIGATION_CANCELLED = "gameplay.survival.obligation_cancelled"
    _OBLIGATION_COMPENSATED = "gameplay.survival.obligation_compensated"

    def rebuild(
        self,
        events: Sequence[GameplayEvent],
        *,
        checkpoint: SurvivalProjection | None = None,
    ) -> SurvivalProjection:
        needs: dict[tuple[str, str], NeedState] = dict(checkpoint.needs) if checkpoint else {}
        latest_plan: ConsumptionPlan | None = checkpoint.latest_plan if checkpoint else None
        revisions: dict[str, int] = dict(checkpoint.source_revision_vector) if checkpoint else {}
        states: dict[tuple[str, str], SurvivalState] = dict(checkpoint.states) if checkpoint else {}
        open_obligations: dict[str, int] = dict(checkpoint.open_obligations) if checkpoint else {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in {
                self._TICK,
                self._CONSUMPTION,
                self._STATE_APPLIED,
                self._OBLIGATION_OPENED,
                self._STATE_EXPIRED,
                self._OBLIGATION_SETTLED,
                self._STATE_DISPELLED,
                self._STATE_TRANSFORMED,
                self._STATE_COMPENSATED,
                self._OBLIGATION_CANCELLED,
                self._OBLIGATION_COMPENSATED,
            }:
                continue
            payload = event.payload
            if event.event_type == self._STATE_APPLIED:
                actor_ref = str(payload.get("actor_ref", ""))
                state_payload = payload.get("state")
                if (
                    not actor_ref
                    or not isinstance(state_payload, dict)
                    or payload.get("family_ref") not in {None, "owner_bound_environment_consumer@1"}
                ):
                    raise ValueError("survival_event_payload_invalid")
                if payload.get("family_ref") == "owner_bound_environment_consumer@1":
                    provenance_payload = {
                        "family_ref": payload.get("family_ref"),
                        "package_revision": payload.get("package_revision"),
                        "content_digest": payload.get("content_digest"),
                        "declaration_ref": payload.get("declaration_ref"),
                        "declaration_digest": payload.get("declaration_digest"),
                        "descriptor_ref": payload.get("descriptor_ref"),
                        "descriptor_revision": payload.get("descriptor_revision"),
                        "active_patch_set_revision": payload.get("active_patch_set_revision"),
                        "policy_revision": payload.get("policy_revision"),
                    }
                    if (
                        not isinstance(payload.get("content_digest"), str)
                        or not isinstance(payload.get("declaration_digest"), str)
                        or payload.get("provenance_digest") != _canonical_digest(provenance_payload)
                    ):
                        raise ValueError("owner_bound_environment_consumer_replay_invalid")
                state = SurvivalState.model_validate(state_payload)
                states[(actor_ref, state.state_ref)] = state
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type == self._OBLIGATION_OPENED:
                obligation_id = str(payload.get("obligation_id", ""))
                due_tick = payload.get("due_tick")
                if not obligation_id or not isinstance(due_tick, int) or isinstance(due_tick, bool) or due_tick < 0:
                    raise ValueError("survival_event_payload_invalid")
                open_obligations[obligation_id] = due_tick
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type in {self._STATE_EXPIRED, self._STATE_DISPELLED}:
                actor_ref = str(payload.get("actor_ref", ""))
                state_ref = str(payload.get("state_ref", ""))
                if not actor_ref or not state_ref:
                    raise ValueError("survival_event_payload_invalid")
                states.pop((actor_ref, state_ref), None)
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type in {self._OBLIGATION_SETTLED, self._OBLIGATION_CANCELLED, self._OBLIGATION_COMPENSATED}:
                obligation_id = str(payload.get("obligation_id", ""))
                if not obligation_id:
                    raise ValueError("survival_event_payload_invalid")
                open_obligations.pop(obligation_id, None)
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type == self._STATE_TRANSFORMED:
                actor_ref = str(payload.get("actor_ref", ""))
                state_payload = payload.get("state")
                if not actor_ref or not isinstance(state_payload, dict):
                    raise ValueError("survival_event_payload_invalid")
                state = SurvivalState.model_validate(state_payload)
                states[(actor_ref, state.state_ref)] = state
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type == self._STATE_COMPENSATED:
                actor_ref = str(payload.get("actor_ref", ""))
                state_payload = payload.get("state")
                if not actor_ref or not isinstance(state_payload, dict):
                    raise ValueError("survival_event_payload_invalid")
                state = SurvivalState.model_validate(state_payload)
                states[(actor_ref, state.state_ref)] = state
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            actor_ref = str(payload.get("actor_ref", ""))
            need_ref = str(payload.get("need_ref", ""))
            if not actor_ref or not need_ref:
                raise ValueError("survival_event_payload_invalid")
            if event.event_type == self._TICK:
                state = NeedState(
                    need_ref=need_ref,
                    value=float(payload["value"]),
                    last_tick=int(payload["last_tick"]),
                )
                needs[(actor_ref, need_ref)] = state
                plan_payload = payload.get("consumption_plan")
                if plan_payload is not None:
                    if not isinstance(plan_payload, dict):
                        raise ValueError("survival_event_payload_invalid")
                    latest_plan = ConsumptionPlan.model_validate(plan_payload)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        if any(
            state.expiry_obligation_id is not None and state.expiry_obligation_id not in open_obligations
            for state in states.values()
        ):
            raise ValueError("owner_bound_environment_consumer_replay_invalid")
        return SurvivalProjection(
            needs=MappingProxyType(dict(sorted(needs.items()))),
            latest_plan=latest_plan,
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
            states=MappingProxyType(dict(sorted(states.items()))),
            open_obligations=MappingProxyType(dict(sorted(open_obligations.items()))),
        )


class SurvivalAuthority:
    _PRINCIPAL = "actor_gameplay.survival_domain"

    def __init__(self, *, store: GameplayEventStore, package_registry: object | None = None) -> None:
        self._store = store
        self._projector = SurvivalProjector()
        self._package_registry = package_registry

    def commit_obligation_batch(self, batch: AtomicEventBatch) -> AppendBatchResult:
        """Commit only a Survival-owned lifecycle plan."""
        if not batch.owner_fragments or any(
            fragment.owner_principal_ref != self._PRINCIPAL
            or any(not event.stream_id.startswith("gameplay:survival:") for event in batch.events)
            for fragment in batch.owner_fragments
        ):
            return self._rejected_append(batch.command_id, "survival_owner_commit_scope_denied")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:survival-state-expiry@1",
                contract_kind="lifecycle",
                owner_ref=self._PRINCIPAL,
                stream_ids=tuple(sorted({event.stream_id for event in batch.events})),
                event_types=tuple(event.event_type for event in batch.events),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected_append(batch.command_id, str(error))
        return self._store.append_batch(batch)

    @staticmethod
    def _rejected_append(command_id: str, error_code: str) -> AppendBatchResult:
        from app.gameplay.models import GameplayFailure

        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="survival_obligation_commit"),
        )

    def projector(self, *, checkpoint_at: int | None = None) -> SurvivalProjection:
        events = self._store.read_events()
        if checkpoint_at is None:
            return self._projector.rebuild(events)
        if checkpoint_at < 0:
            raise ValueError("survival_checkpoint_invalid")
        checkpoint = self._projector.rebuild(events[:checkpoint_at])
        return self._projector.rebuild(events[checkpoint_at:], checkpoint=checkpoint)

    def project_states(self, *, scope: Literal["public", "authority"] = "public") -> dict[str, tuple[dict[str, object], ...]]:
        rows: dict[str, list[dict[str, object]]] = {}
        for (actor_ref, _state_ref), state in self.projector().states.items():
            row: dict[str, object] = {"state_ref": state.state_ref, "stacks": state.stacks}
            if scope == "authority":
                row.update(
                    {
                        "effect_ref": state.effect_ref,
                        "effective_magnitude": state.effective_magnitude,
                        "expiry_obligation_id": state.expiry_obligation_id,
                    }
                )
            rows.setdefault(actor_ref, []).append(row)
        return {
            actor_ref: tuple(sorted(values, key=lambda item: str(item["state_ref"])))
            for actor_ref, values in sorted(rows.items())
        }

    def apply_effect_state(
        self,
        *,
        command: GameplayCommandEnvelope,
        application: EffectApplication,
        resistance: ResistanceProfile,
        definition: StateDefinition,
        expiry_policy: SurvivalStateExpiryPolicy | None = None,
        source_evidence_refs: tuple[str, ...] = (),
        provenance_payload: Mapping[str, object] = MappingProxyType({}),
    ) -> AppendBatchResult:
        """Commit an owner-admitted semantic proposal; the evaluator never writes."""
        if command.principal_ref != self._PRINCIPAL or command.actor_ref is None:
            return self._rejected(command, "survival_state_owner_required")
        proposal_digest = self._state_application_digest(
            command=command,
            application=application,
            resistance=resistance,
            definition=definition,
            expiry_policy=expiry_policy,
        )
        existing = self._store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key)
        if existing is not None:
            existing_digest = self._committed_state_application_digest(existing.committed_event_ids)
            if existing_digest == proposal_digest:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"})
            return self._rejected(command, "idempotency_key_reused")
        actor_ref = command.actor_ref
        if application.target_component_ref != actor_ref:
            return self._rejected(command, "survival_state_target_mismatch")
        stream_id = f"gameplay:survival:{actor_ref}"
        contract_effect_ref = {
            ("effect:cold", "state:cold"): "effect:cold_exposure",
        }.get((application.effect_ref, definition.state_ref), application.effect_ref)
        try:
            contract = SemanticRegistry.require_closed_state_owner_contract(
                effect_ref=contract_effect_ref,
                state_ref=definition.state_ref,
            )
        except SemanticRegistryError:
            # Only semantic proposals cross the shared admission boundary.
            # Existing Survival-owned lifecycle maintenance retains its
            # established owner-local inputs and obligations.
            if command.source_ref.startswith("proposal:semantic:"):
                return self._rejected(command, "survival_state_owner_mapping_unregistered")
            contract = None
        if contract is not None and (
            contract.owner_ref != self._PRINCIPAL
            or contract.stream_pattern != "gameplay:survival:{actor_ref}"
            or contract.apply_event_type != "gameplay.survival.state_applied"
            or contract.opened_event_type != "gameplay.survival.obligation_opened"
            or contract.projection_scope != "project"
        ):
            return self._rejected(command, "survival_state_owner_mapping_unregistered")
        if command.expected_revisions != {stream_id: self._store.get_stream_head(stream_id)}:
            return self._rejected(command, "revision_conflict")
        current = self.projector().states.get((actor_ref, definition.state_ref))
        resolution = EffectLifecycleEvaluator().resolve(
            application,
            resistance=resistance,
            state=definition,
            existing_stacks=current.stacks if current else 0,
        )
        if not resolution.accepted:
            return self._rejected(command, resolution.error_code or "survival_state_rejected")
        if definition.expiry_policy == "scheduled" and resolution.expiry_obligation is None:
            return self._rejected(command, "survival_state_expiry_required")
        policy = expiry_policy or SurvivalStateExpiryPolicy()
        obligation: ScheduledObligation | None = None
        if resolution.expiry_obligation is not None:
            obligation = policy.build_obligation(
                actor_ref=actor_ref,
                state_ref=definition.state_ref,
                due_tick=int(resolution.expiry_obligation["due_tick"]),
                expected_revision=self._store.get_stream_head(stream_id),
            )
        state = SurvivalState(
            state_ref=definition.state_ref,
            effect_ref=application.effect_ref,
            stacks=resolution.next_stacks,
            effective_magnitude=resolution.effective_magnitude,
            expiry_obligation_id=obligation.obligation_id if obligation else None,
        )
        event_specs: list[tuple[str, Mapping[str, object]]] = [
            (
                "gameplay.survival.state_applied",
                {
                    "actor_ref": actor_ref,
                    "state": state.model_dump(mode="json"),
                    "causal_chain_id": application.causal_chain_id,
                    "source_ref": command.source_ref,
                    "source_evidence_refs": list(source_evidence_refs),
                    "state_application_digest": proposal_digest,
                    "provenance_digest": _canonical_digest(
                        {
                            "family_ref": "owner_bound_environment_consumer@1",
                            "package_revision": provenance_payload.get("package_revision"),
                            "content_digest": provenance_payload.get("content_digest"),
                            "declaration_ref": provenance_payload.get("declaration_ref"),
                            "declaration_digest": provenance_payload.get("declaration_digest"),
                            "descriptor_ref": provenance_payload.get("descriptor_ref"),
                            "descriptor_revision": provenance_payload.get("descriptor_revision"),
                            "active_patch_set_revision": provenance_payload.get("active_patch_set_revision"),
                            "policy_revision": provenance_payload.get("policy_revision"),
                        }
                    ),
                    **dict(provenance_payload),
                },
            )
        ]
        if obligation is not None:
            event_specs.append(
                (
                    "gameplay.survival.obligation_opened",
                    {
                        "obligation_id": obligation.obligation_id,
                        "due_tick": obligation.due_tick,
                        "policy_ref": policy.policy_ref,
                        "policy_revision": policy.policy_revision,
                        "state_ref": definition.state_ref,
                        "actor_ref": actor_ref,
                    },
                )
            )
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:survival-state-expiry@1",
                contract_kind="lifecycle",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=tuple(event_type for event_type, _ in event_specs),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected(command, str(error))
        batch = build_atomic_event_batch(
            command_id=command.command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=event_specs,
            idempotency_key=command.idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            read_stream_revisions=dict(command.read_set_revisions),
            pinned_revisions=dict(command.pinned_revisions),
        )
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.survival.scoped_projection",
                        audience="project",
                        payload_projection={"actor_ref": actor_ref, "state_ref": definition.state_ref},
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def apply_weather_front_cold_exposure(
        self,
        *,
        command: GameplayCommandEnvelope,
        content: OwnerBoundEnvironmentConsumerContent | None = None,
        provenance_payload: Mapping[str, object] = MappingProxyType({}),
    ) -> AppendBatchResult:
        """Apply the one admitted Ecology evidence row through existing Survival events."""
        if (
            command.command_type != "gameplay.survival.apply_weather_front_cold"
            or command.principal_ref != self._PRINCIPAL
            or command.source_ref != "authority:ecology"
            or command.actor_ref is None
            or command.payload.get("visibility_scope") != "project"
        ):
            return self._rejected(command, "weather_front_cold_authority_required")
        actor_ref = command.actor_ref
        world_ref = command.payload.get("world_ref")
        weather_event_id = command.payload.get("weather_event_id")
        assignment_event_id = command.payload.get("region_assignment_event_id")
        if not all(isinstance(value, str) and value for value in (world_ref, weather_event_id, assignment_event_id)):
            return self._rejected(command, "weather_front_cold_evidence_required")
        try:
            weather_event = self._store.get_event(weather_event_id)
            assignment_event = self._store.get_event(assignment_event_id)
        except KeyError:
            return self._rejected(command, "weather_front_cold_evidence_missing")
        target_region_ref = weather_event.payload.get("target_region_ref")
        ecology_stream = weather_event.stream_id
        population_stream = f"population:{world_ref}"
        if (
            weather_event.event_type != "gameplay.ecology.weather_front.propagated"
            or not ecology_stream.startswith("gameplay:ecology:")
            or weather_event.visibility_policy != "project"
            or weather_event.payload.get("weather_ref") != "weather:frost"
            or not isinstance(target_region_ref, str)
            or assignment_event.event_type != "population.activation.region_assigned"
            or assignment_event.stream_id != population_stream
            or assignment_event.visibility_policy != "project"
            or assignment_event.payload.get("profile_ref") != actor_ref
            or assignment_event.payload.get("region_ref") != target_region_ref
            or assignment_event.payload.get("privacy_scope") != "project"
        ):
            return self._rejected(command, "weather_front_cold_evidence_invalid")
        lifecycle = {
            "population.activation.committed": "active",
            "population.activation.suspended": "suspended",
            "population.activation.requeued": "requeued",
            "population.activation.locked": "locked",
        }
        status = None
        for event in self._store.read_stream(population_stream):
            if event.payload.get("profile_ref") == actor_ref and event.event_type in lifecycle:
                status = lifecycle[event.event_type]
        if status != "active":
            return self._rejected(command, "weather_front_cold_profile_not_active")
        survival_stream = f"gameplay:survival:{actor_ref}"
        if (
            set(command.expected_revisions) != {survival_stream}
            or set(command.read_set_revisions) != {ecology_stream, population_stream}
        ):
            return self._rejected(command, "weather_front_cold_revision_vector_invalid")
        if self._store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key) is None:
            admission_check = EcologyConsumerAdmissionCheck.verify(
                store=self._store,
                contract_ref="inf:weather-front-survival-cold@1",
                target_owner_ref=self._PRINCIPAL,
                target_stream_ids=(survival_stream,),
                target_event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                ),
                projection_scope="project",
                source_event_id=weather_event.event_id,
                source_stream_id=ecology_stream,
                source_revision=weather_event.stream_revision,
                target_expected_revisions=dict(command.expected_revisions),
                idempotency_key=command.idempotency_key,
            )
            if not admission_check.accepted:
                return self._rejected(
                    command,
                    admission_check.error_code or "weather_front_cold_admission_invalid",
                )
        try:
            tick = int(weather_event.payload["tick"])
        except (KeyError, TypeError, ValueError):
            return self._rejected(command, "weather_front_cold_evidence_invalid")
        if tick < 0 or isinstance(weather_event.payload.get("tick"), bool):
            return self._rejected(command, "weather_front_cold_evidence_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:weather-front-survival-cold@1",
                contract_kind="ecology_consumer",
                owner_ref=self._PRINCIPAL,
                stream_ids=(survival_stream,),
                event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                ),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected(command, str(error))
        effect_ref = content.effect_ref if content is not None else "effect:cold_exposure"
        state_ref = content.state_ref if content is not None else "state:cold"
        magnitude = content.magnitude if content is not None else 100
        stack_key = content.stack_key if content is not None else "cold"
        stack_policy = content.stack_policy if content is not None else "add"
        stack_limit = content.stack_limit if content is not None else 2
        expiry_policy = content.expiry_policy if content is not None else "scheduled"
        expires_after_ticks = content.expires_after_ticks if content is not None else 1
        return self.apply_effect_state(
            command=command,
            application=EffectApplication(
                effect_ref=effect_ref,
                target_component_ref=actor_ref,
                magnitude=magnitude,
                stack_key=stack_key,
                expires_at_tick=tick + expires_after_ticks if expiry_policy == "scheduled" else None,
                causal_chain_id=f"weather-front-cold:{weather_event_id}:{assignment_event_id}",
            ),
            resistance=ResistanceProfile(
                effect_ref=effect_ref,
                source_ref=actor_ref,
                modifier_basis_points=0,
                revision=1,
            ),
            definition=StateDefinition(
                state_ref=state_ref,
                stack_policy=stack_policy,
                stack_limit=stack_limit,
                expiry_policy=expiry_policy,
            ),
            source_evidence_refs=(weather_event_id, assignment_event_id),
            provenance_payload=provenance_payload,
        )

    def apply_weather_front_heat_exposure(
        self,
        *,
        command: GameplayCommandEnvelope,
        content: OwnerBoundEnvironmentConsumerContent | None = None,
        provenance_payload: Mapping[str, object] = MappingProxyType({}),
    ) -> AppendBatchResult:
        """Apply the one admitted heat weather evidence row through Survival."""
        if (
            command.command_type != "gameplay.survival.apply_weather_front_heat"
            or command.principal_ref != self._PRINCIPAL
            or command.source_ref != "authority:ecology"
            or command.actor_ref is None
            or command.payload.get("visibility_scope") != "project"
        ):
            return self._rejected(command, "weather_front_heat_authority_required")
        actor_ref = command.actor_ref
        world_ref = command.payload.get("world_ref")
        weather_event_id = command.payload.get("weather_event_id")
        assignment_event_id = command.payload.get("region_assignment_event_id")
        if not all(isinstance(value, str) and value for value in (world_ref, weather_event_id, assignment_event_id)):
            return self._rejected(command, "weather_front_heat_evidence_required")
        try:
            weather_event = self._store.get_event(weather_event_id)
            assignment_event = self._store.get_event(assignment_event_id)
        except KeyError:
            return self._rejected(command, "weather_front_heat_evidence_missing")
        target_region_ref = weather_event.payload.get("target_region_ref")
        ecology_stream = weather_event.stream_id
        population_stream = f"population:{world_ref}"
        if (
            weather_event.event_type != "gameplay.ecology.weather_front.propagated"
            or not ecology_stream.startswith("gameplay:ecology:")
            or weather_event.visibility_policy != "project"
            or weather_event.payload.get("weather_ref") != "weather:heat"
            or not isinstance(target_region_ref, str)
            or assignment_event.event_type != "population.activation.region_assigned"
            or assignment_event.stream_id != population_stream
            or assignment_event.visibility_policy != "project"
            or assignment_event.payload.get("profile_ref") != actor_ref
            or assignment_event.payload.get("region_ref") != target_region_ref
            or assignment_event.payload.get("privacy_scope") != "project"
        ):
            return self._rejected(command, "weather_front_heat_evidence_invalid")
        lifecycle = {
            "population.activation.committed": "active",
            "population.activation.suspended": "suspended",
            "population.activation.requeued": "requeued",
            "population.activation.locked": "locked",
        }
        status = None
        for event in self._store.read_stream(population_stream):
            if event.payload.get("profile_ref") == actor_ref and event.event_type in lifecycle:
                status = lifecycle[event.event_type]
        if status != "active":
            return self._rejected(command, "weather_front_heat_profile_not_active")
        survival_stream = f"gameplay:survival:{actor_ref}"
        if (
            set(command.expected_revisions) != {survival_stream}
            or set(command.read_set_revisions) != {ecology_stream, population_stream}
        ):
            return self._rejected(command, "weather_front_heat_revision_vector_invalid")
        if self._store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key) is None:
            admission_check = EcologyConsumerAdmissionCheck.verify(
                store=self._store,
                contract_ref="inf:weather-front-survival-heat@1",
                target_owner_ref=self._PRINCIPAL,
                target_stream_ids=(survival_stream,),
                target_event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                ),
                projection_scope="project",
                source_event_id=weather_event.event_id,
                source_stream_id=ecology_stream,
                source_revision=weather_event.stream_revision,
                target_expected_revisions=dict(command.expected_revisions),
                idempotency_key=command.idempotency_key,
            )
            if not admission_check.accepted:
                return self._rejected(
                    command,
                    admission_check.error_code or "weather_front_heat_admission_invalid",
                )
        try:
            tick = int(weather_event.payload["tick"])
        except (KeyError, TypeError, ValueError):
            return self._rejected(command, "weather_front_heat_evidence_invalid")
        if tick < 0 or isinstance(weather_event.payload.get("tick"), bool):
            return self._rejected(command, "weather_front_heat_evidence_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:weather-front-survival-heat@1",
                contract_kind="ecology_consumer",
                owner_ref=self._PRINCIPAL,
                stream_ids=(survival_stream,),
                event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                ),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected(command, str(error))
        effect_ref = content.effect_ref if content is not None else "effect:heat_exposure"
        state_ref = content.state_ref if content is not None else "state:overheated"
        magnitude = content.magnitude if content is not None else 100
        stack_key = content.stack_key if content is not None else "heat"
        stack_policy = content.stack_policy if content is not None else "add"
        stack_limit = content.stack_limit if content is not None else 2
        expiry_policy = content.expiry_policy if content is not None else "scheduled"
        expires_after_ticks = content.expires_after_ticks if content is not None else 1
        return self.apply_effect_state(
            command=command,
            application=EffectApplication(
                effect_ref=effect_ref,
                target_component_ref=actor_ref,
                magnitude=magnitude,
                stack_key=stack_key,
                expires_at_tick=tick + expires_after_ticks if expiry_policy == "scheduled" else None,
                causal_chain_id=f"weather-front-heat:{weather_event_id}:{assignment_event_id}",
            ),
            resistance=ResistanceProfile(
                effect_ref=effect_ref,
                source_ref=actor_ref,
                modifier_basis_points=0,
                revision=1,
            ),
            definition=StateDefinition(
                state_ref=state_ref,
                stack_policy=stack_policy,
                stack_limit=stack_limit,
                expiry_policy=expiry_policy,
            ),
            source_evidence_refs=(weather_event_id, assignment_event_id),
            provenance_payload=provenance_payload,
        )

    def apply_weather_front_dehydration_exposure(
        self,
        *,
        command: GameplayCommandEnvelope,
        content: OwnerBoundEnvironmentConsumerContent | None = None,
        provenance_payload: Mapping[str, object] = MappingProxyType({}),
    ) -> AppendBatchResult:
        """Apply the approved drought weather-front row through existing Survival events."""
        if (
            command.command_type != "gameplay.survival.apply_weather_front_dehydration"
            or command.principal_ref != self._PRINCIPAL
            or command.source_ref != "authority:ecology"
            or command.actor_ref is None
            or command.payload.get("visibility_scope") != "project"
        ):
            return self._rejected(command, "weather_front_dehydration_authority_required")
        actor_ref = command.actor_ref
        world_ref = command.payload.get("world_ref")
        weather_event_id = command.payload.get("weather_event_id")
        assignment_event_id = command.payload.get("region_assignment_event_id")
        if not all(
            isinstance(value, str) and value
            for value in (world_ref, weather_event_id, assignment_event_id)
        ):
            return self._rejected(command, "weather_front_dehydration_evidence_required")
        if command.idempotency_key != f"weather-front-dehydration:{weather_event_id}:{actor_ref}:v1":
            return self._rejected(command, "weather_front_dehydration_idempotency_key_invalid")
        try:
            weather_event = self._store.get_event(weather_event_id)
            assignment_event = self._store.get_event(assignment_event_id)
        except KeyError:
            return self._rejected(command, "weather_front_dehydration_evidence_missing")
        target_region_ref = weather_event.payload.get("target_region_ref")
        ecology_stream = weather_event.stream_id
        population_stream = f"population:{world_ref}"
        if (
            weather_event.event_type != "gameplay.ecology.weather_front.propagated"
            or not ecology_stream.startswith("gameplay:ecology:")
            or weather_event.visibility_policy != "project"
            or weather_event.payload.get("weather_ref") != "weather:drought"
            or not isinstance(target_region_ref, str)
            or not target_region_ref
            or assignment_event.event_type != "population.activation.region_assigned"
            or assignment_event.stream_id != population_stream
            or assignment_event.visibility_policy != "project"
            or assignment_event.payload.get("profile_ref") != actor_ref
            or assignment_event.payload.get("region_ref") != target_region_ref
            or assignment_event.payload.get("privacy_scope") != "project"
        ):
            return self._rejected(command, "weather_front_dehydration_evidence_invalid")
        lifecycle = {
            "population.activation.committed": "active",
            "population.activation.suspended": "suspended",
            "population.activation.requeued": "requeued",
            "population.activation.locked": "locked",
        }
        status = None
        for event in self._store.read_stream(population_stream):
            if event.payload.get("profile_ref") == actor_ref and event.event_type in lifecycle:
                status = lifecycle[event.event_type]
        if status != "active":
            return self._rejected(command, "weather_front_dehydration_profile_not_active")
        survival_stream = f"gameplay:survival:{actor_ref}"
        if (
            set(command.expected_revisions) != {survival_stream}
            or set(command.read_set_revisions) != {ecology_stream, population_stream}
            or command.read_set_revisions[ecology_stream] != weather_event.stream_revision
            or command.read_set_revisions[population_stream] != assignment_event.stream_revision
        ):
            return self._rejected(command, "weather_front_dehydration_revision_vector_invalid")
        if self._store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key) is None:
            admission_check = EcologyConsumerAdmissionCheck.verify(
                store=self._store,
                contract_ref="inf:weather-front-survival-dehydration@1",
                target_owner_ref=self._PRINCIPAL,
                target_stream_ids=(survival_stream,),
                target_event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                ),
                projection_scope="project",
                source_event_id=weather_event.event_id,
                source_stream_id=ecology_stream,
                source_revision=weather_event.stream_revision,
                target_expected_revisions=dict(command.expected_revisions),
                idempotency_key=command.idempotency_key,
            )
            if not admission_check.accepted:
                return self._rejected(
                    command,
                    admission_check.error_code or "weather_front_dehydration_admission_invalid",
                )
        try:
            tick = int(weather_event.payload["tick"])
        except (KeyError, TypeError, ValueError):
            return self._rejected(command, "weather_front_dehydration_evidence_invalid")
        if tick < 0 or isinstance(weather_event.payload.get("tick"), bool):
            return self._rejected(command, "weather_front_dehydration_evidence_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:weather-front-survival-dehydration@1",
                contract_kind="ecology_consumer",
                owner_ref=self._PRINCIPAL,
                stream_ids=(survival_stream,),
                event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                ),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected(command, str(error))
        effect_ref = content.effect_ref if content is not None else "effect:dehydration_exposure"
        state_ref = content.state_ref if content is not None else "state:dehydrated"
        magnitude = content.magnitude if content is not None else 100
        stack_key = content.stack_key if content is not None else "dehydration"
        stack_policy = content.stack_policy if content is not None else "add"
        stack_limit = content.stack_limit if content is not None else 2
        expiry_policy = content.expiry_policy if content is not None else "scheduled"
        expires_after_ticks = content.expires_after_ticks if content is not None else 1
        return self.apply_effect_state(
            command=command,
            application=EffectApplication(
                effect_ref=effect_ref,
                target_component_ref=actor_ref,
                magnitude=magnitude,
                stack_key=stack_key,
                expires_at_tick=tick + expires_after_ticks if expiry_policy == "scheduled" else None,
                causal_chain_id=f"weather-front-dehydration:{weather_event_id}:{assignment_event_id}",
            ),
            resistance=ResistanceProfile(
                effect_ref=effect_ref,
                source_ref=actor_ref,
                modifier_basis_points=0,
                revision=1,
            ),
            definition=StateDefinition(
                state_ref=state_ref,
                stack_policy=stack_policy,
                stack_limit=stack_limit,
                expiry_policy=expiry_policy,
            ),
            source_evidence_refs=(weather_event_id, assignment_event_id),
            provenance_payload=provenance_payload,
        )

    def apply_weather_front_rain_hydration(
        self,
        *,
        command: GameplayCommandEnvelope,
        content: OwnerBoundEnvironmentConsumerContent | None = None,
        provenance_payload: Mapping[str, object] = MappingProxyType({}),
    ) -> AppendBatchResult:
        """Apply the exact rain -> hydration consumer row through Survival."""
        if (
            command.command_type != "gameplay.survival.apply_weather_front_hydration"
            or command.principal_ref != self._PRINCIPAL
            or command.source_ref != "authority:ecology"
            or command.actor_ref is None
            or command.payload.get("visibility_scope") != "project"
        ):
            return self._rejected(command, "weather_front_hydration_authority_required")
        actor_ref = command.actor_ref
        world_ref = command.payload.get("world_ref")
        weather_event_id = command.payload.get("weather_event_id")
        assignment_event_id = command.payload.get("region_assignment_event_id")
        if not all(isinstance(value, str) and value for value in (world_ref, weather_event_id, assignment_event_id)):
            return self._rejected(command, "weather_front_hydration_evidence_required")
        if command.idempotency_key != f"weather-front-hydration:{weather_event_id}:{actor_ref}:v1":
            return self._rejected(command, "weather_front_hydration_idempotency_key_invalid")
        try:
            weather_event = self._store.get_event(weather_event_id)
            assignment_event = self._store.get_event(assignment_event_id)
        except KeyError:
            return self._rejected(command, "weather_front_hydration_evidence_missing")
        target_region_ref = weather_event.payload.get("target_region_ref")
        ecology_stream = weather_event.stream_id
        population_stream = f"population:{world_ref}"
        if (
            weather_event.event_type != "gameplay.ecology.weather_front.propagated"
            or not ecology_stream.startswith("gameplay:ecology:")
            or weather_event.visibility_policy != "project"
            or weather_event.payload.get("weather_ref") != "weather:rain"
            or not isinstance(target_region_ref, str)
            or not target_region_ref
            or assignment_event.event_type != "population.activation.region_assigned"
            or assignment_event.stream_id != population_stream
            or assignment_event.visibility_policy != "project"
            or assignment_event.payload.get("profile_ref") != actor_ref
            or assignment_event.payload.get("region_ref") != target_region_ref
            or assignment_event.payload.get("privacy_scope") != "project"
        ):
            return self._rejected(command, "weather_front_hydration_evidence_invalid")
        lifecycle = {
            "population.activation.committed": "active",
            "population.activation.suspended": "suspended",
            "population.activation.requeued": "requeued",
            "population.activation.locked": "locked",
        }
        status = None
        for event in self._store.read_stream(population_stream):
            if event.payload.get("profile_ref") == actor_ref and event.event_type in lifecycle:
                status = lifecycle[event.event_type]
        if status != "active":
            return self._rejected(command, "weather_front_hydration_profile_not_active")
        survival_stream = f"gameplay:survival:{actor_ref}"
        if (
            set(command.expected_revisions) != {survival_stream}
            or set(command.read_set_revisions) != {ecology_stream, population_stream}
            or command.read_set_revisions[ecology_stream] != weather_event.stream_revision
            or command.read_set_revisions[population_stream] != assignment_event.stream_revision
        ):
            return self._rejected(command, "weather_front_hydration_revision_vector_invalid")
        if self._store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key) is None:
            admission_check = EcologyConsumerAdmissionCheck.verify(
                store=self._store,
                contract_ref="inf:weather-front-survival-hydration@1",
                target_owner_ref=self._PRINCIPAL,
                target_stream_ids=(survival_stream,),
                target_event_types=("gameplay.survival.state_applied", "gameplay.survival.obligation_opened"),
                projection_scope="project",
                source_event_id=weather_event.event_id,
                source_stream_id=ecology_stream,
                source_revision=weather_event.stream_revision,
                target_expected_revisions=dict(command.expected_revisions),
                idempotency_key=command.idempotency_key,
            )
            if not admission_check.accepted:
                return self._rejected(command, admission_check.error_code or "weather_front_hydration_admission_invalid")
        try:
            tick = int(weather_event.payload["tick"])
        except (KeyError, TypeError, ValueError):
            return self._rejected(command, "weather_front_hydration_evidence_invalid")
        if tick < 0 or isinstance(weather_event.payload.get("tick"), bool):
            return self._rejected(command, "weather_front_hydration_evidence_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:weather-front-survival-hydration@1",
                contract_kind="ecology_consumer",
                owner_ref=self._PRINCIPAL,
                stream_ids=(survival_stream,),
                event_types=("gameplay.survival.state_applied", "gameplay.survival.obligation_opened"),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected(command, str(error))
        effect_ref = content.effect_ref if content is not None else "effect:hydration"
        state_ref = content.state_ref if content is not None else "state:hydrated"
        magnitude = content.magnitude if content is not None else 100
        stack_key = content.stack_key if content is not None else "hydration"
        stack_policy = content.stack_policy if content is not None else "refresh"
        stack_limit = content.stack_limit if content is not None else 1
        expiry_policy = content.expiry_policy if content is not None else "scheduled"
        expires_after_ticks = content.expires_after_ticks if content is not None else 1
        return self.apply_effect_state(
            command=command,
            application=EffectApplication(
                effect_ref=effect_ref,
                target_component_ref=actor_ref,
                magnitude=magnitude,
                stack_key=stack_key,
                expires_at_tick=tick + expires_after_ticks if expiry_policy == "scheduled" else None,
                causal_chain_id=f"weather-front-hydration:{weather_event_id}:{assignment_event_id}",
            ),
            resistance=ResistanceProfile(
                effect_ref=effect_ref,
                source_ref=actor_ref,
                modifier_basis_points=0,
                revision=1,
            ),
            definition=StateDefinition(
                state_ref=state_ref,
                stack_policy=stack_policy,
                stack_limit=stack_limit,
                expiry_policy=expiry_policy,
            ),
            source_evidence_refs=(weather_event_id, assignment_event_id),
            provenance_payload=provenance_payload,
        )

    def settle_owner_bound_environment_consumer(self, *, intent: object) -> AppendBatchResult:
        """Build one admitted environment consumer from committed evidence only."""
        from app.gameplay.closed_generic_gameplay_families import OwnerBoundEnvironmentConsumerIntent

        try:
            typed_intent = intent if isinstance(intent, OwnerBoundEnvironmentConsumerIntent) else OwnerBoundEnvironmentConsumerIntent.model_validate(intent)
            weather = self._store.get_event(typed_intent.weather_event_id)
            assignment = self._store.get_event(typed_intent.region_assignment_event_id)
        except Exception:
            return self._rejected_append(str(getattr(intent, "command_id", "environment-consumer")), "owner_bound_environment_consumer_source_missing")
        resolved_content, row_error = self._resolve_owner_bound_environment_row(weather)
        if row_error is not None or resolved_content is None:
            return self._rejected_append(typed_intent.command_id, row_error or "owner_bound_environment_consumer_binding_invalid")
        manifest, declaration, binding, content = resolved_content
        weather_ref = weather.payload.get("weather_ref")
        if (
            weather.event_type != "gameplay.ecology.weather_front.propagated"
            or weather.visibility_policy != "project"
            or not isinstance(weather_ref, str)
            or (content.weather_ref is not None and weather_ref != content.weather_ref)
            or assignment.event_type != "population.activation.region_assigned"
            or assignment.visibility_policy != "project"
            or not isinstance(assignment.payload.get("profile_ref"), str)
            or not isinstance(assignment.payload.get("world_ref"), str)
            or assignment.payload.get("region_ref") != weather.payload.get("target_region_ref")
        ):
            return self._rejected_append(typed_intent.command_id, "owner_bound_environment_consumer_source_conflict")
        actor_ref = str(assignment.payload["profile_ref"])
        world_ref = str(assignment.payload["world_ref"])
        survival_stream = f"gameplay:survival:{actor_ref}"
        idempotency_key = f"owner-bound-environment-consumer:{manifest.patch_revision_id}:{weather.event_id}:{actor_ref}:v1"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            prior = next(
                (event for event in self._store.read_events() if event.event_id in set(existing.committed_event_ids)),
                None,
            )
            if prior is not None and prior.causation_id == weather.event_id and prior.correlation_id == typed_intent.correlation_id:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(typed_intent.command_id, "idempotency_key_reused")
        command = GameplayCommandEnvelope(
            command_id=typed_intent.command_id,
            command_type="gameplay.survival.apply_owner_bound_environment_consumer",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=actor_ref,
            project_ref="project:weather-survival",
            transaction_id=f"transaction:{typed_intent.command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={survival_stream: self._store.get_stream_head(survival_stream)},
            read_set_revisions={
                weather.stream_id: weather.stream_revision,
                assignment.stream_id: assignment.stream_revision,
            },
            causation_id=weather.event_id,
            correlation_id=typed_intent.correlation_id,
            source_ref="authority:ecology",
            submitted_at="2026-08-30T00:00:00Z",
            payload={
                "world_ref": world_ref,
                "weather_event_id": weather.event_id,
                "region_assignment_event_id": assignment.event_id,
                "visibility_scope": "project",
            },
        )
        return self._apply_owner_bound_environment_content(
            command=command,
            content=content,
            provenance_payload={
                "family_ref": "owner_bound_environment_consumer@1",
                "package_revision": manifest.patch_revision_id,
                "content_digest": manifest.content_digest,
                "declaration_ref": declaration.declaration_ref,
                "declaration_digest": declaration.declaration_digest,
                "descriptor_ref": binding.descriptor_ref,
                "descriptor_revision": binding.descriptor_revision,
                "active_patch_set_revision": binding.active_patch_set_revision,
                "policy_revision": content.policy_revision_ref,
            },
        )

    def _apply_owner_bound_environment_content(
        self,
        *,
        command: GameplayCommandEnvelope,
        content: OwnerBoundEnvironmentConsumerContent,
        provenance_payload: Mapping[str, object],
    ) -> AppendBatchResult:
        actor_ref = command.actor_ref
        world_ref = command.payload.get("world_ref")
        weather_event_id = command.payload.get("weather_event_id")
        assignment_event_id = command.payload.get("region_assignment_event_id")
        if (
            command.command_type != "gameplay.survival.apply_owner_bound_environment_consumer"
            or command.principal_ref != self._PRINCIPAL
            or command.source_ref != "authority:ecology"
            or not isinstance(actor_ref, str)
            or not isinstance(world_ref, str)
            or not isinstance(weather_event_id, str)
            or not isinstance(assignment_event_id, str)
            or command.payload.get("visibility_scope") != "project"
        ):
            return self._rejected(command, "owner_bound_environment_consumer_authority_required")
        try:
            weather = self._store.get_event(weather_event_id)
            assignment = self._store.get_event(assignment_event_id)
        except KeyError:
            return self._rejected(command, "owner_bound_environment_consumer_source_missing")
        weather_ref = weather.payload.get("weather_ref")
        source_name = weather_ref.removeprefix("weather:") if isinstance(weather_ref, str) else ""
        expected_source_family_ref = f"event:weather-front-{source_name}@1"
        target_region_ref = weather.payload.get("target_region_ref")
        population_stream = f"population:{world_ref}"
        target_definition = content.target_state_definition_ref
        target_state_ref = (
            target_definition.removeprefix("definition:survival-").split("@", 1)[0]
            if target_definition.startswith("definition:survival-")
            else target_definition.removeprefix("state:").split("@", 1)[0]
        )
        content_state_ref = content.state_ref.removeprefix("state:").split("@", 1)[0]
        if not target_state_ref or target_state_ref != content_state_ref:
            return self._rejected(command, "owner_bound_environment_consumer_content_invalid")
        if (
            weather.event_type != "gameplay.ecology.weather_front.propagated"
            or not weather.stream_id.startswith("gameplay:ecology:")
            or weather.visibility_policy != "project"
            or not isinstance(weather_ref, str)
            or not source_name
            or content.source_event_family_ref != expected_source_family_ref
            or (content.weather_ref is not None and content.weather_ref != weather_ref)
            or not isinstance(target_region_ref, str)
            or assignment.event_type != "population.activation.region_assigned"
            or assignment.stream_id != population_stream
            or assignment.visibility_policy != "project"
            or assignment.payload.get("profile_ref") != actor_ref
            or assignment.payload.get("region_ref") != target_region_ref
            or assignment.payload.get("privacy_scope") != "project"
        ):
            return self._rejected(command, "owner_bound_environment_consumer_source_conflict")
        status_events = {
            "population.activation.committed": "active",
            "population.activation.suspended": "suspended",
            "population.activation.requeued": "requeued",
            "population.activation.locked": "locked",
        }
        status = None
        for event in self._store.read_stream(population_stream):
            if event.payload.get("profile_ref") == actor_ref and event.event_type in status_events:
                status = status_events[event.event_type]
        if status != "active":
            return self._rejected(command, "owner_bound_environment_consumer_profile_not_active")
        survival_stream = f"gameplay:survival:{actor_ref}"
        if (
            set(command.expected_revisions) != {survival_stream}
            or set(command.read_set_revisions) != {weather.stream_id, population_stream}
            or command.read_set_revisions[weather.stream_id] != weather.stream_revision
            or command.read_set_revisions[population_stream] != assignment.stream_revision
        ):
            return self._rejected(command, "owner_bound_environment_consumer_revision_vector_invalid")
        admission_check = EcologyConsumerAdmissionCheck.verify(
            store=self._store,
            contract_ref="inf:owner-bound-environment-consumer@1",
            target_owner_ref=self._PRINCIPAL,
            target_stream_ids=(survival_stream,),
            target_event_types=("gameplay.survival.state_applied",),
            projection_scope="project",
            source_event_id=weather.event_id,
            source_stream_id=weather.stream_id,
            source_revision=weather.stream_revision,
            target_expected_revisions=dict(command.expected_revisions),
            idempotency_key=command.idempotency_key,
        )
        if not admission_check.accepted:
            return self._rejected(command, admission_check.error_code or "owner_bound_environment_consumer_admission_invalid")
        try:
            tick = weather.payload["tick"]
            if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
                raise ValueError
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:owner-bound-environment-consumer@1",
                contract_kind="ecology_consumer",
                owner_ref=self._PRINCIPAL,
                stream_ids=(survival_stream,),
                event_types=("gameplay.survival.state_applied",),
                projection_scope="project",
            )
        except (KeyError, TypeError, ValueError, GovernedAuthorityContractError) as error:
            return self._rejected(command, str(error) or "owner_bound_environment_consumer_source_invalid")
        return self.apply_effect_state(
            command=command,
            application=EffectApplication(
                effect_ref=content.effect_ref,
                target_component_ref=actor_ref,
                magnitude=content.magnitude,
                stack_key=content.stack_key,
                expires_at_tick=tick + content.expires_after_ticks if content.expiry_policy == "scheduled" else None,
                causal_chain_id=f"owner-bound-environment-consumer:{weather.event_id}:{assignment.event_id}",
            ),
            resistance=ResistanceProfile(
                effect_ref=content.effect_ref,
                source_ref=actor_ref,
                modifier_basis_points=0,
                revision=1,
            ),
            definition=StateDefinition(
                state_ref=content.state_ref,
                stack_policy=content.stack_policy,
                stack_limit=content.stack_limit,
                expiry_policy=content.expiry_policy,
            ),
            source_evidence_refs=(weather.event_id, assignment.event_id),
            provenance_payload=provenance_payload,
        )

    def _resolve_owner_bound_environment_row(
        self, weather: GameplayEvent
    ) -> tuple[tuple[object, object, object, OwnerBoundEnvironmentConsumerContent] | None, str | None]:
        registry = self._package_registry
        active = getattr(registry, "active_patch_set", None) if registry is not None else None
        if active is None:
            return None, "owner_bound_environment_consumer_package_inactive"
        try:
            manifests = registry.active_manifests(active.active_patch_set_revision)
        except Exception:
            return None, "owner_bound_environment_consumer_package_inactive"
        from app.gameplay.closed_generic_gameplay_families import OwnerBoundEnvironmentConsumerContent

        candidates: list[tuple[object, object, object, OwnerBoundEnvironmentConsumerContent]] = []
        binding_invalid = False
        content_shape_match = False
        weather_ref = weather.payload.get("weather_ref")
        source_name = weather_ref.removeprefix("weather:") if isinstance(weather_ref, str) else ""
        source_event_family_ref = f"event:weather-front-{source_name}@1"
        for manifest in manifests:
            extension = manifest.platform_extension
            if extension is None:
                continue
            declarations = {item.declaration_ref: item for item in extension.outcome_declarations}
            for request in extension.capability_binding_requests:
                if request.capability_ref != "capability:owner-bound-environment-consumer@1":
                    continue
                declaration = declarations.get(request.declaration_ref)
                if declaration is None:
                    continue
                bindings = tuple(
                    binding for binding in active.capability_bindings
                    if binding.binding_ref == request.binding_ref
                    and binding.package_revision == manifest.patch_revision_id
                    and binding.descriptor_ref == "descriptor:owner-bound-environment-consumer@1"
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
                    content = OwnerBoundEnvironmentConsumerContent.model_validate(
                        definitions[0].typed_content
                    )
                except Exception:
                    continue
                if content.source_event_family_ref != source_event_family_ref:
                    continue
                if content.weather_ref is not None and content.weather_ref != weather_ref:
                    continue
                declaration_payload = declaration.model_dump(mode="json", exclude={"declaration_digest"})
                expected_family_digest = _canonical_digest(
                    content.model_dump(mode="json", exclude_none=True)
                )
                if (
                    bindings[0].active_patch_set_revision != active.active_patch_set_revision
                    or bindings[0].descriptor_ref != "descriptor:owner-bound-environment-consumer@1"
                    or bindings[0].descriptor_revision != "descriptor:owner-bound-environment-consumer@1"
                    or bindings[0].content_digest != manifest.content_digest
                    or bindings[0].family_content_digest != expected_family_digest
                    or bindings[0].declaration_ref != declaration.declaration_ref
                    or bindings[0].declaration_digest != declaration.declaration_digest
                    or declaration.declaration_digest != _canonical_digest(declaration_payload)
                ):
                    binding_invalid = True
                    continue
                content_shape_match = True
                candidates.append((manifest, declaration, bindings[0], content))
        if not candidates:
            if binding_invalid:
                return None, "owner_bound_environment_consumer_binding_invalid"
            return None, (
                "owner_bound_environment_consumer_content_invalid"
                if content_shape_match
                else "owner_bound_environment_consumer_source_conflict"
            )
        if len(candidates) != 1:
            return None, "owner_bound_environment_consumer_binding_ambiguous"
        return candidates[0], None

    @staticmethod
    def _state_application_digest(
        *,
        command: GameplayCommandEnvelope,
        application: EffectApplication,
        resistance: ResistanceProfile,
        definition: StateDefinition,
        expiry_policy: SurvivalStateExpiryPolicy | None,
    ) -> str:
        payload = {
            "command": command.model_dump(mode="json"),
            "application": application.model_dump(mode="json"),
            "resistance": resistance.model_dump(mode="json"),
            "definition": definition.model_dump(mode="json"),
            "expiry_policy": expiry_policy.model_dump(mode="json") if expiry_policy else None,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return "sha256:" + sha256(encoded).hexdigest()

    def _committed_state_application_digest(self, event_ids: tuple[str, ...]) -> str | None:
        ids = set(event_ids)
        for event in self._store.read_events():
            if event.event_id in ids and event.event_type == "gameplay.survival.state_applied":
                digest = event.payload.get("state_application_digest")
                return digest if isinstance(digest, str) else None
        return None

    @classmethod
    def build_state_expiry_fragment(
        cls,
        *,
        obligation: ScheduledObligation,
        actor_ref: str,
        state_ref: str,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        stream_id = f"gameplay:survival:{actor_ref}"
        if (
            obligation.owner_ref != cls._PRINCIPAL
            or obligation.expected_revisions != {stream_id: expected_revision}
            or obligation.status not in {"open", "due", "retry"}
            or obligation.obligation_id != SurvivalStateExpiryPolicy.obligation_id_for(actor_ref=actor_ref, state_ref=state_ref)
        ):
            raise ValueError("survival_state_expiry_fragment_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:survival:state-expiry:{actor_ref}:{state_ref}:{obligation.due_tick}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="survival:state-expiry",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={"survival_state_expiry": obligation.due_tick},
            event_specs={
                stream_id: (
                    (
                        "gameplay.survival.state_expired",
                        {
                            "actor_ref": actor_ref,
                            "state_ref": state_ref,
                            "obligation_id": obligation.obligation_id,
                            "due_tick": obligation.due_tick,
                        },
                    ),
                    (
                        "gameplay.survival.obligation_settled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "settled",
                            "policy_ref": "policy:survival_state_expiry",
                            "policy_revision": obligation.policy_revision,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project", "project")},
        )

    @classmethod
    def build_state_dispel_fragment(
        cls,
        *,
        obligation: ScheduledObligation,
        actor_ref: str,
        state_ref: str,
        expected_revision: int,
        reason_ref: str,
    ) -> OwnerAuthorizedFragment:
        stream_id = f"gameplay:survival:{actor_ref}"
        if (
            not reason_ref
            or obligation.owner_ref != cls._PRINCIPAL
            or obligation.expected_revisions != {stream_id: expected_revision}
            or obligation.obligation_id != SurvivalStateExpiryPolicy.obligation_id_for(actor_ref=actor_ref, state_ref=state_ref)
        ):
            raise ValueError("survival_state_dispel_fragment_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:survival:state-dispel:{actor_ref}:{state_ref}:{reason_ref}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="survival:state-dispel",
            expected_revisions={stream_id: expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.survival.state_dispelled",
                        {
                            "actor_ref": actor_ref,
                            "state_ref": state_ref,
                            "obligation_id": obligation.obligation_id,
                            "reason_ref": reason_ref,
                        },
                    ),
                    (
                        "gameplay.survival.obligation_cancelled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "cancelled",
                            "policy_ref": "policy:survival_state_expiry",
                            "policy_revision": obligation.policy_revision,
                            "reason_ref": reason_ref,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project", "project")},
        )

    @classmethod
    def build_state_retry_fragment(
        cls,
        *,
        obligation: ScheduledObligation,
        actor_ref: str,
        state_ref: str,
        next_due_tick: int,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        stream_id = f"gameplay:survival:{actor_ref}"
        policy = obligation.retry_policy
        attempt, maximum = policy.get("attempt"), policy.get("max_attempts")
        if (
            obligation.owner_ref != cls._PRINCIPAL
            or obligation.expected_revisions != {stream_id: expected_revision}
            or obligation.obligation_id != SurvivalStateExpiryPolicy.obligation_id_for(actor_ref=actor_ref, state_ref=state_ref)
            or not isinstance(attempt, int)
            or isinstance(attempt, bool)
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or attempt < 1
            or attempt > maximum
            or next_due_tick < obligation.due_tick
        ):
            raise ValueError("survival_state_retry_fragment_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:survival:state-retry:{actor_ref}:{state_ref}:{attempt}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="survival:state-expiry-retry",
            expected_revisions={stream_id: expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.survival.obligation_retry_scheduled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "policy_ref": "policy:survival_state_expiry",
                            "policy_revision": obligation.policy_revision,
                            "attempt": attempt,
                            "max_attempts": maximum,
                            "next_due_tick": next_due_tick,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project",)},
        )

    @classmethod
    def build_state_compensation_fragment(
        cls,
        *,
        obligation: ScheduledObligation,
        actor_ref: str,
        restored_state: SurvivalState,
        expected_revision: int,
        reason_ref: str,
    ) -> OwnerAuthorizedFragment:
        stream_id = f"gameplay:survival:{actor_ref}"
        if (
            not reason_ref
            or obligation.owner_ref != cls._PRINCIPAL
            or obligation.status != "settled"
            or not obligation.compensation_policy
            or obligation.expected_revisions != {stream_id: expected_revision}
            or obligation.obligation_id != SurvivalStateExpiryPolicy.obligation_id_for(actor_ref=actor_ref, state_ref=restored_state.state_ref)
        ):
            raise ValueError("survival_state_compensation_fragment_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:survival:state-compensate:{actor_ref}:{restored_state.state_ref}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="survival:state-expiry-compensation",
            expected_revisions={stream_id: expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.survival.state_compensated",
                        {
                            "actor_ref": actor_ref,
                            "state": restored_state.model_dump(mode="json"),
                            "obligation_id": obligation.obligation_id,
                            "reason_ref": reason_ref,
                        },
                    ),
                    (
                        "gameplay.survival.obligation_compensated",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": "settled",
                            "current_state": "compensated",
                            "policy_ref": "policy:survival_state_expiry",
                            "policy_revision": obligation.policy_revision,
                            "reason_ref": reason_ref,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project", "project")},
        )

    @classmethod
    def build_state_transform_fragment(
        cls,
        *,
        obligation: ScheduledObligation,
        actor_ref: str,
        state_ref: str,
        replacement: SurvivalState,
        expected_revision: int,
        reason_ref: str,
    ) -> OwnerAuthorizedFragment:
        stream_id = f"gameplay:survival:{actor_ref}"
        if (
            not reason_ref
            or replacement.state_ref == state_ref
            or obligation.owner_ref != cls._PRINCIPAL
            or obligation.expected_revisions != {stream_id: expected_revision}
            or obligation.obligation_id != SurvivalStateExpiryPolicy.obligation_id_for(actor_ref=actor_ref, state_ref=state_ref)
        ):
            raise ValueError("survival_state_transform_fragment_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:survival:state-transform:{actor_ref}:{state_ref}:{replacement.state_ref}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="survival:state-transform",
            expected_revisions={stream_id: expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.survival.state_dispelled",
                        {"actor_ref": actor_ref, "state_ref": state_ref, "obligation_id": obligation.obligation_id, "reason_ref": reason_ref},
                    ),
                    (
                        "gameplay.survival.state_transformed",
                        {"actor_ref": actor_ref, "from_state_ref": state_ref, "state": replacement.model_dump(mode="json"), "reason_ref": reason_ref},
                    ),
                    (
                        "gameplay.survival.obligation_cancelled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "cancelled",
                            "policy_ref": "policy:survival_state_expiry",
                            "policy_revision": obligation.policy_revision,
                            "reason_ref": reason_ref,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project", "project", "project")},
        )

    def settle_tick(
        self,
        *,
        actor_ref: str,
        policy: SurvivalPolicy,
        definition: NeedDefinition,
        state: NeedState,
        tick: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if policy.mode in {SurvivalMode.DISABLED, SurvivalMode.NARRATIVE}:
            raise ValueError("survival_mode_no_authority_tick")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        next_state, plan = self.tick(policy=policy, definition=definition, state=state, tick=tick)
        stream_id = f"gameplay:survival:{actor_ref}"
        plan_payload = None
        if plan is not None:
            plan_payload = plan.model_dump(mode="json")
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.survival.need_tick",
                    {
                        "actor_ref": actor_ref,
                        "need_ref": next_state.need_ref,
                        "value": next_state.value,
                        "last_tick": next_state.last_tick,
                        "policy_ref": policy.policy_ref,
                        "policy_revision": policy.revision,
                        "consumption_plan": plan_payload,
                    },
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"survival": tick},
        )
        return self._store.append_batch(batch)

    def settle_consumption(
        self,
        *,
        actor_ref: str,
        plan: ConsumptionPlan,
        accepted_reservation_refs: tuple[str, ...],
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if not accepted_reservation_refs:
            raise ValueError("reservation_required")
        required = set(plan.required_owner_refs)
        provided = set(accepted_reservation_refs)
        if required and not required.issubset(provided):
            raise ValueError("reservation_required")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        stream_id = f"gameplay:survival:{actor_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.survival.consumption_accepted",
                    {
                        "actor_ref": actor_ref,
                        "need_ref": plan.need_ref,
                        "item_ref": plan.item_ref,
                        "quantity": plan.quantity,
                        "accepted_reservation_refs": accepted_reservation_refs,
                    },
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions=plan.pinned_revisions,
        )
        return self._store.append_batch(batch)

    @classmethod
    def build_due_tick_fragment(
        cls,
        *,
        actor_ref: str,
        policy: SurvivalPolicy,
        definition: NeedDefinition,
        state: NeedState,
        tick: int,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        if policy.mode in {SurvivalMode.DISABLED, SurvivalMode.NARRATIVE}:
            raise ValueError("survival_mode_no_authority_tick")
        next_state, plan = cls.tick(policy=policy, definition=definition, state=state, tick=tick)
        stream_id = f"gameplay:survival:{actor_ref}"
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:survival:due:{actor_ref}:{definition.need_ref}:{tick}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="survival:due-tick",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={"survival": tick},
            event_specs={stream_id: (("gameplay.survival.need_tick", {"actor_ref": actor_ref, "need_ref": next_state.need_ref, "value": next_state.value, "last_tick": next_state.last_tick, "policy_ref": policy.policy_ref, "policy_revision": policy.revision, "consumption_plan": plan.model_dump(mode="json") if plan else None}),)},
        )
    @staticmethod
    def tick(*, policy: SurvivalPolicy, definition: NeedDefinition, state: NeedState, tick: int) -> tuple[NeedState, ConsumptionPlan | None]:
        if tick < state.last_tick:
            raise ValueError("revision_conflict")
        if policy.mode in {SurvivalMode.DISABLED, SurvivalMode.NARRATIVE}:
            return state, None
        elapsed = tick - state.last_tick
        if elapsed == 0:
            return state, None
        next_value = max(0.0, state.value - definition.decay_per_tick * elapsed)
        next_state = state.model_copy(update={"value": next_value, "last_tick": tick}, deep=True)
        plan = ConsumptionPlan(
            need_ref=definition.need_ref,
            item_ref="item:food",
            quantity=1,
            required_owner_refs=("inventory", "ownership"),
            pinned_revisions={"survival": tick},
        ) if next_value < 0.5 else None
        return next_state, plan

    @staticmethod
    def _rejected(command: GameplayCommandEnvelope, error_code: str) -> AppendBatchResult:
        from app.gameplay.models import GameplayFailure

        return AppendBatchResult(
            committed=False,
            transaction_id=command.transaction_id or f"transaction:{command.command_id}",
            command_id=command.command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="survival_state"),
        )

__all__ = ["ConsumptionPlan", "NeedDefinition", "NeedState", "SurvivalAuthority", "SurvivalMode", "SurvivalPolicy", "SurvivalProjection", "SurvivalProjector", "SurvivalState", "SurvivalStateExpiryPolicy"]
