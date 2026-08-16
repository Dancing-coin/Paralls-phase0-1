from __future__ import annotations

from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, ProductionRun, Recipe
from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.entity_causal_projection import EntityCausalProjection
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayFailure, GameplayOutboxEntry, StrictGameplayModel
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.semantic_registry import SemanticRegistry
from app.gameplay.semantic_effects import EffectApplication, EffectLifecycleEvaluator, ResistanceProfile, StateDefinition
from app.gameplay.settlement_plan import SettlementPlan, build_multi_stream_atomic_event_batch_from_fragments
from app.gameplay.shared_contracts import GameplayCommandEnvelope, SemanticSnapshot
from app.gameplay.survival_runtime import SurvivalAuthority, SurvivalState, SurvivalStateExpiryPolicy
from app.world_runtime.obligations import ObligationLifecycleRegistration, ObligationSettlementCoordinator


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


class SemanticEffectCommand(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    effect_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    semantic_snapshot: SemanticSnapshot
    expected_snapshot_digest: str = Field(min_length=1)
    causal_parent_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    privacy_scope: Literal["project", "authority_only", "private_evidence"] = "project"


class SemanticProductionFinishCommand(StrictGameplayModel):
    """Closed semantic proposal for the sole INF-1R production-finish target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    effect_ref: Literal["effect:production_due_finish"]
    source_rule_ref: str = Field(min_length=1)
    rule_set_revision: str = Field(min_length=1)
    trace_digest: str = Field(min_length=1)
    causal_chain_id: str = Field(min_length=1)
    semantic_snapshot: SemanticSnapshot
    expected_snapshot_digest: str = Field(min_length=1)
    run: ProductionRun
    recipe: Recipe
    tick: int = Field(ge=0)
    privacy_scope: Literal["project", "authority_only", "private_evidence"] = "project"


class SemanticWageObligationCommand(StrictGameplayModel):
    """Closed semantic proposal for the existing Economy wage-obligation row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    effect_ref: str = Field(min_length=1)
    target_ref: str = Field(pattern=r"^character:")
    semantic_snapshot: SemanticSnapshot
    expected_snapshot_digest: str = Field(min_length=1)
    accrual_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    work_evidence_refs: tuple[str, ...] = Field(min_length=1)
    wage_amount_minor: int = Field(gt=0)
    due_tick: int = Field(ge=0)
    policy_revision: str = Field(min_length=1)
    causal_parent_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    privacy_scope: Literal["project", "authority_only", "private_evidence"] = "project"


class SemanticEcologyFrostCommand(StrictGameplayModel):
    """Closed proposal input for the existing Ecology frost crop-state row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    principal_ref: Literal["authority:semantic"]
    hazard_ref: str = Field(pattern=r"^hazard:")
    crop_ref: str = Field(pattern=r"^crop:")
    region_ref: str = Field(pattern=r"^region:")
    expected_revision: int = Field(ge=0)
    magnitude: int = Field(ge=0)
    due_tick: int = Field(ge=0)
    resistance_revision: int = Field(ge=0)
    semantic_snapshot: SemanticSnapshot
    expected_snapshot_digest: str = Field(min_length=1)
    effect_ref: Literal["effect:frost"] = "effect:frost"
    state_ref: Literal["state:frosted@1"] = "state:frosted@1"


class SemanticEcologyDroughtCommand(StrictGameplayModel):
    """Closed proposal input for the existing Ecology drought state row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    principal_ref: Literal["authority:semantic"]
    region_ref: str = Field(pattern=r"^region:")
    source_event_id: str = Field(min_length=1)
    source_event_revision: int = Field(ge=1)
    expected_revision: int = Field(ge=0)
    due_tick: int = Field(ge=0)
    resistance_revision: int = Field(ge=0)
    semantic_snapshot: SemanticSnapshot
    expected_snapshot_digest: str = Field(min_length=1)
    effect_ref: Literal["effect:drought"] = "effect:drought"
    state_ref: Literal["state:drought@1"] = "state:drought@1"


class SemanticEcologyFrostStateActionCommand(StrictGameplayModel):
    """Closed semantic proposal for the existing Ecology frost dispel row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    principal_ref: Literal["authority:semantic"]
    hazard_ref: str = Field(pattern=r"^hazard:")
    crop_ref: str = Field(pattern=r"^crop:")
    region_ref: str = Field(pattern=r"^region:")
    expected_revision: int = Field(ge=0)
    semantic_snapshot: SemanticSnapshot
    expected_snapshot_digest: str = Field(min_length=1)
    privacy_scope: Literal["project", "authority_only", "private_evidence"] = "project"
    effect_ref: Literal["effect:ecology_frost_state_dispel"] = "effect:ecology_frost_state_dispel"
    state_ref: Literal["state:frosted@1"] = "state:frosted@1"


class SemanticSurvivalStateActionCommand(StrictGameplayModel):
    """Closed proposal for an event-derived Survival state action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    effect_ref: str = Field(min_length=1)
    target_ref: str = Field(pattern=r"^character:")
    state_ref: str = Field(min_length=1)
    semantic_snapshot: SemanticSnapshot
    expected_snapshot_digest: str = Field(min_length=1)
    reason_ref: str = Field(min_length=1)
    privacy_scope: Literal["project", "authority_only", "private_evidence"] = "project"


class SemanticConstructionMaintenanceDispelCommand(StrictGameplayModel):
    """Closed proposal for the sole Construction maintenance dispel action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    effect_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    state_ref: str = Field(min_length=1)
    semantic_snapshot: SemanticSnapshot
    expected_snapshot_digest: str = Field(min_length=1)
    reason_ref: str = Field(min_length=1)
    privacy_scope: Literal["project", "authority_only", "private_evidence"] = "project"


class RegisteredStateApplySurvivalProvenance(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provenance_kind: Literal["survival_semantic_snapshot"] = "survival_semantic_snapshot"
    semantic_revision: Literal[1] = 1


class RegisteredStateApplyConstructionProvenance(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provenance_kind: Literal["construction_maintenance_semantic_snapshot"] = (
        "construction_maintenance_semantic_snapshot"
    )
    semantic_revision: Literal[1] = 1


class RegisteredStateApplyEcologyFrostProvenance(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provenance_kind: Literal["ecology_frost_canonical_source"] = "ecology_frost_canonical_source"
    hazard_ref: str = Field(pattern=r"^hazard:")
    region_ref: str = Field(pattern=r"^region:")
    magnitude: int = Field(ge=0)
    due_tick: int = Field(ge=0)
    resistance_revision: int = Field(ge=0)


class RegisteredStateApplyEcologyDroughtProvenance(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provenance_kind: Literal["ecology_drought_opening_event"] = "ecology_drought_opening_event"
    source_event_id: str = Field(min_length=1)
    source_event_revision: int = Field(ge=1)
    due_tick: int = Field(ge=0)
    resistance_revision: int = Field(ge=0)


RegisteredStateApplyProvenance = Annotated[
    RegisteredStateApplySurvivalProvenance
    | RegisteredStateApplyConstructionProvenance
    | RegisteredStateApplyEcologyFrostProvenance
    | RegisteredStateApplyEcologyDroughtProvenance,
    Field(discriminator="provenance_kind"),
]


class RegisteredStateApplyCommand(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    effect_ref: str = Field(min_length=1)
    state_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    semantic_snapshot: SemanticSnapshot
    expected_snapshot_digest: str = Field(min_length=1)
    privacy_scope: Literal["project", "authority_only", "private_evidence"] = "project"
    provenance: RegisteredStateApplyProvenance


class SemanticSettlementAuthority:
    """Owner bridge from semantic proposals to the existing event spine."""

    def __init__(self, *, store: GameplayEventStore, registry: SemanticRegistry) -> None:
        self.store = store
        self.registry = registry

    def settle(self, command: SemanticEffectCommand, *, lifecycle_payload: dict[str, object] | None = None) -> AppendBatchResult:
        existing = self.store.get_by_idempotency(command.principal_ref, command.idempotency_key)
        if existing is not None and existing.committed:
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"})
        try:
            if command.semantic_snapshot.digest != command.expected_snapshot_digest:
                return self._failure(command, "semantic_snapshot_digest_mismatch")
            if command.semantic_snapshot.entity_ref != command.target_ref:
                return self._failure(command, "semantic_target_mismatch")
            if command.privacy_scope == "private_evidence":
                return self._failure(command, "semantic_privacy_scope_denied")
            if self.store.get_stream_head(command.stream_id) != command.expected_revision:
                return self._failure(command, "revision_conflict")
            payload = {
                "entity_ref": command.target_ref,
                "entity_kind": command.target_ref.split(":", 1)[0],
                "component_refs": list(command.semantic_snapshot.component_refs),
                "status_refs": list(command.semantic_snapshot.statuses),
                "type_refs": [tag for tag in command.semantic_snapshot.resolved_tags if tag.startswith("type:")],
                "material_refs": [tag for tag in command.semantic_snapshot.resolved_tags if tag.startswith("material:")],
                "property_refs": [tag for tag in command.semantic_snapshot.resolved_tags if tag.startswith("property:")],
                "effect_ref": command.effect_ref,
                "causal_parent_refs": list(command.causal_parent_refs),
                "evidence_refs": list(command.evidence_refs),
                "semantic_snapshot_digest": command.semantic_snapshot.digest,
                **(lifecycle_payload or {}),
            }
            envelope = GameplayCommandEnvelope(
                command_id=command.command_id,
                command_type="semantic.effect.settle",
                command_version=1,
                principal_ref=command.principal_ref,
                actor_ref=command.owner_ref,
                project_ref=None,
                transaction_id=None,
                idempotency_key=command.idempotency_key,
                expected_revisions={command.stream_id: command.expected_revision},
                causation_id=command.command_id,
                correlation_id=f"semantic:{command.target_ref}",
                source_ref="semantic_registry",
                submitted_at="semantic-authority",
                pinned_revisions=dict(command.semantic_snapshot.source_revision_vector),
                payload={"stream_ref": command.stream_id, "event_type": "semantic.effect.settled", **payload},
            )
            batch = SettlementPlan.from_command_envelope(envelope).to_atomic_event_batch()
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="semantic.scoped_projection",
                            audience=command.privacy_scope,
                            payload_projection={
                                "entity_ref": command.target_ref,
                                "effect_ref": command.effect_ref,
                                "semantic_snapshot_digest": command.semantic_snapshot.digest,
                            },
                        )
                    ]
                },
                deep=True,
            )
            return self.store.append_batch(batch)
        except ValueError as exc:
            return self._failure(command, str(exc) or "semantic_settlement_rejected")

    def settle_lifecycle(
        self,
        command: SemanticEffectCommand,
        *,
        application: EffectApplication,
        resistance: ResistanceProfile,
        state: StateDefinition,
        existing_stacks: int,
        lifecycle_payload: dict[str, object] | None = None,
    ) -> AppendBatchResult:
        if application.effect_ref != command.effect_ref:
            return self._failure(command, "semantic_effect_mismatch")
        resolution = EffectLifecycleEvaluator().resolve(
            application,
            resistance=resistance,
            state=state,
            existing_stacks=existing_stacks,
        )
        if not resolution.accepted:
            return self._failure(command, resolution.error_code or "semantic_effect_rejected")
        return self.settle(
            command,
            lifecycle_payload={
                "state_ref": state.state_ref,
                "effective_magnitude": resolution.effective_magnitude,
                "next_stacks": resolution.next_stacks,
                "expiry_obligation": resolution.expiry_obligation,
                "resistance_revision": resistance.revision,
                **(lifecycle_payload or {}),
            },
        )

    def settle_registered_state(
        self,
        command: RegisteredStateApplyCommand,
        *,
        application: EffectApplication | None = None,
        resistance: ResistanceProfile | None = None,
        state: StateDefinition | None = None,
    ) -> AppendBatchResult:
        """Route one closed registered row to its existing domain owner."""
        try:
            route = self.registry.registered_state_owner_route(
                state_ref=command.state_ref,
                effect_ref=command.effect_ref,
            )
        except ValueError:
            return self._registered_state_failure(command, "semantic_registered_state_route_unknown")
        if (
            command.principal_ref != "authority:semantic"
            or command.owner_ref != route.owner_ref
            or command.privacy_scope != route.projection_scope
        ):
            return self._registered_state_failure(command, "semantic_registered_state_route_mismatch")
        if route.adapter_ref == "SemanticSettlementAuthority.settle_closed_survival_state":
            if (
                not isinstance(command.provenance, RegisteredStateApplySurvivalProvenance)
                or application is None
                or resistance is None
                or state is None
                or application.effect_ref != command.effect_ref
                or application.target_component_ref != command.target_ref
                or command.stream_id != f"gameplay:survival:{command.target_ref}"
                or command.provenance.semantic_revision
                != command.semantic_snapshot.source_revision_vector.get("semantic")
            ):
                return self._registered_state_failure(command, "semantic_registered_state_route_mismatch")
            return self.settle_closed_survival_state(
                self._to_semantic_effect_command(command),
                application=application,
                resistance=resistance,
                state=state,
            )
        if route.adapter_ref == "SemanticSettlementAuthority.settle_closed_construction_maintenance_state":
            if (
                not isinstance(command.provenance, RegisteredStateApplyConstructionProvenance)
                or application is None
                or resistance is None
                or state is None
                or application.effect_ref != command.effect_ref
                or application.target_component_ref != command.target_ref
                or command.stream_id != f"gameplay:construction_production:{command.target_ref}"
                or command.provenance.semantic_revision
                != command.semantic_snapshot.source_revision_vector.get("semantic")
            ):
                return self._registered_state_failure(command, "semantic_registered_state_route_mismatch")
            return self.settle_closed_construction_maintenance_state(
                self._to_semantic_effect_command(command),
                application=application,
                resistance=resistance,
                state=state,
            )
        if route.adapter_ref == "SemanticSettlementAuthority.settle_closed_ecology_frost":
            if (
                not isinstance(command.provenance, RegisteredStateApplyEcologyFrostProvenance)
                or command.stream_id != f"gameplay:ecology:{command.provenance.region_ref}"
            ):
                return self._registered_state_failure(command, "semantic_registered_state_route_mismatch")
            return self.settle_closed_ecology_frost(
                SemanticEcologyFrostCommand(
                    command_id=command.command_id,
                    idempotency_key=command.idempotency_key,
                    principal_ref="authority:semantic",
                    hazard_ref=command.provenance.hazard_ref,
                    crop_ref=command.target_ref,
                    region_ref=command.provenance.region_ref,
                    expected_revision=command.expected_revision,
                    magnitude=command.provenance.magnitude,
                    due_tick=command.provenance.due_tick,
                    resistance_revision=command.provenance.resistance_revision,
                    semantic_snapshot=command.semantic_snapshot,
                    expected_snapshot_digest=command.expected_snapshot_digest,
                )
            )
        if route.adapter_ref == "SemanticSettlementAuthority.settle_closed_ecology_drought":
            if (
                not isinstance(command.provenance, RegisteredStateApplyEcologyDroughtProvenance)
                or command.stream_id != f"gameplay:ecology:{command.target_ref}"
            ):
                return self._registered_state_failure(command, "semantic_registered_state_route_mismatch")
            return self.settle_closed_ecology_drought(
                SemanticEcologyDroughtCommand(
                    command_id=command.command_id,
                    idempotency_key=command.idempotency_key,
                    principal_ref="authority:semantic",
                    region_ref=command.target_ref,
                    source_event_id=command.provenance.source_event_id,
                    source_event_revision=command.provenance.source_event_revision,
                    expected_revision=command.expected_revision,
                    due_tick=command.provenance.due_tick,
                    resistance_revision=command.provenance.resistance_revision,
                    semantic_snapshot=command.semantic_snapshot,
                    expected_snapshot_digest=command.expected_snapshot_digest,
                )
            )
        return self._registered_state_failure(command, "semantic_registered_state_route_unknown")

    def settle_registered_wage_obligation(self, command: SemanticWageObligationCommand) -> AppendBatchResult:
        """Delegate the one closed semantic wage-effect row to its Economy owner."""
        try:
            route = self.registry.registered_effect_owner_route(effect_ref=command.effect_ref)
            lifecycle = self.registry.require_closed_lifecycle_owner_contract(effect_ref=command.effect_ref)
        except ValueError:
            return self._wage_failure(command, "semantic_effect_owner_route_unknown")
        expected_stream = f"gameplay:economy:wage:{command.target_ref}"
        if (
            command.principal_ref != "authority:semantic"
            or command.owner_ref != route.owner_ref
            or command.stream_id != expected_stream
            or route.stream_pattern != "gameplay:economy:wage:{worker_ref}"
            or route.opened_event_type != "gameplay.economy.wage_obligation_opened"
            or route.projection_scope != command.privacy_scope
            or lifecycle.owner_ref != route.owner_ref
            or lifecycle.stream_pattern != route.stream_pattern
            or lifecycle.projection_scope != route.projection_scope
            or route.opened_event_type not in lifecycle.event_types
            or command.semantic_snapshot.entity_ref != command.target_ref
            or command.semantic_snapshot.digest != command.expected_snapshot_digest
            or command.semantic_snapshot.source_revision_vector != {"semantic": 1}
            or not isinstance(command.accrual_ref, str)
            or not command.accrual_ref.strip()
            or not isinstance(command.organization_ref, str)
            or not command.organization_ref.strip()
            or not command.work_evidence_refs
            or any(not isinstance(reference, str) or not reference.strip() for reference in command.work_evidence_refs)
            or command.wage_amount_minor <= 0
            or command.due_tick < 0
            or not isinstance(command.policy_revision, str)
            or not command.policy_revision.strip()
        ):
            return self._wage_failure(command, "semantic_effect_owner_route_mismatch")
        envelope = GameplayCommandEnvelope(
            command_id=command.command_id,
            command_type="gameplay.economy.open_wage_obligation",
            command_version=1,
            principal_ref=EconomyAuthority._PRINCIPAL,
            actor_ref=command.target_ref,
            idempotency_key=command.idempotency_key,
            expected_revisions={expected_stream: command.expected_revision},
            causation_id=command.causal_parent_refs[0] if command.causal_parent_refs else command.command_id,
            correlation_id=f"semantic-wage:{command.target_ref}:{command.accrual_ref}",
            source_ref=EconomyAuthority._PRINCIPAL,
            submitted_at="semantic-authority",
            pinned_revisions=dict(command.semantic_snapshot.source_revision_vector),
            payload={
                "visibility_scope": "project",
                "semantic_effect_ref": command.effect_ref,
                "semantic_snapshot_digest": command.semantic_snapshot.digest,
            },
        )
        return EconomyAuthority(store=self.store).open_wage_obligation(
            command=envelope,
            accrual_ref=command.accrual_ref,
            organization_ref=command.organization_ref,
            work_evidence_refs=command.work_evidence_refs,
            wage_amount_minor=command.wage_amount_minor,
            due_tick=command.due_tick,
            policy_revision=command.policy_revision,
        )

    def settle_registered_survival_state_action(
        self, command: SemanticSurvivalStateActionCommand
    ) -> AppendBatchResult:
        """Delegate one closed state action to existing Survival fragments."""
        try:
            route = self.registry.registered_survival_state_action_route(effect_ref=command.effect_ref)
        except ValueError:
            return self._state_action_failure(command, "semantic_survival_state_action_route_unknown")
        stream_id = f"gameplay:survival:{command.target_ref}"
        if (
            command.principal_ref != "authority:semantic"
            or command.owner_ref != route.owner_ref
            or command.stream_id != stream_id
            or route.stream_pattern != "gameplay:survival:{actor_ref}"
            or command.state_ref not in route.source_state_refs
            or command.privacy_scope != route.projection_scope
            or command.semantic_snapshot.entity_ref != command.target_ref
            or command.semantic_snapshot.digest != command.expected_snapshot_digest
            or command.semantic_snapshot.source_revision_vector != {"semantic": 1}
            or not command.reason_ref.strip()
        ):
            return self._state_action_failure(command, "semantic_survival_state_action_route_mismatch")
        try:
            state_contract = self.registry.require_closed_survival_state_action_contract(state_ref=command.state_ref)
            self.registry.require_closed_state_lifecycle_adapter(
                effect_ref=state_contract.effect_ref,
                state_ref=command.state_ref,
                operation="dispel" if command.effect_ref == "effect:state_dispel" else "transform",
            )
        except ValueError:
            return self._state_action_failure(command, "semantic_survival_state_action_contract_unknown")
        if state_contract.projection_scope != route.projection_scope:
            return self._state_action_failure(command, "semantic_survival_state_action_contract_mismatch")
        policy = SurvivalStateExpiryPolicy()
        obligation_id = policy.obligation_id_for(actor_ref=command.target_ref, state_ref=command.state_ref)
        existing = self.store.get_by_idempotency(command.principal_ref, command.idempotency_key)
        action = None
        if existing is not None and existing.committed:
            due_tick = self._state_action_opened_due_tick(stream_id=stream_id, obligation_id=obligation_id)
            if due_tick is None:
                return self._state_action_failure(command, "idempotency_key_reused")
        else:
            if self.store.get_stream_head(stream_id) != command.expected_revision:
                return self._state_action_failure(command, "revision_conflict")
            projection = SurvivalAuthority(store=self.store).projector()
            due_tick = projection.open_obligations.get(obligation_id)
            if due_tick is None or (command.target_ref, command.state_ref) not in projection.states:
                return self._state_action_failure(command, "semantic_survival_state_action_source_not_open")
            existing_state = projection.states[(command.target_ref, command.state_ref)]
            evaluator = EffectLifecycleEvaluator()
            action = (
                evaluator.resolve_dispel(state=state_contract.definition, existing_stacks=existing_state.stacks)
                if command.effect_ref == "effect:state_dispel"
                else evaluator.resolve_transform(
                    state=state_contract.definition,
                    existing_stacks=existing_state.stacks,
                    target_state_ref="state:recovering",
                )
            )
            if not action.accepted:
                return self._state_action_failure(command, action.error_code or "semantic_survival_state_action_rejected")
        obligation = policy.build_obligation(
            actor_ref=command.target_ref,
            state_ref=command.state_ref,
            due_tick=due_tick,
            expected_revision=command.expected_revision,
            status="open",
        ).model_copy(update={"idempotency_key": command.idempotency_key})
        try:
            if command.effect_ref == "effect:state_dispel":
                fragment = SurvivalAuthority.build_state_dispel_fragment(
                    obligation=obligation,
                    actor_ref=command.target_ref,
                    state_ref=command.state_ref,
                    expected_revision=command.expected_revision,
                    reason_ref=command.reason_ref,
                )
            else:
                fragment = SurvivalAuthority.build_state_transform_fragment(
                    obligation=obligation,
                    actor_ref=command.target_ref,
                    state_ref=command.state_ref,
                    replacement=SurvivalState(
                        state_ref=action.next_state_ref if action is not None else "state:recovering",
                        effect_ref="effect:remedy",
                        stacks=1,
                        effective_magnitude=50,
                    ),
                    expected_revision=command.expected_revision,
                    reason_ref=command.reason_ref,
                )
            coordinator = ObligationSettlementCoordinator(
                store=self.store,
                lifecycle_registrations=(
                    ObligationLifecycleRegistration(
                        policy_ref=policy.policy_ref,
                        policy_revision=policy.policy_revision,
                        owner_ref=SurvivalAuthority._PRINCIPAL,
                        stream_pattern="gameplay:survival:{actor_ref}",
                        opened_event_type="gameplay.survival.obligation_opened",
                        settled_event_type="gameplay.survival.obligation_settled",
                        cancelled_event_type="gameplay.survival.obligation_cancelled",
                        visibility_scope="project",
                    ),
                ),
            )
            plan = coordinator.plan_cancel(
                obligation=obligation,
                fragment=fragment,
                principal_ref=command.principal_ref,
                reason_ref=command.reason_ref,
                idempotency_key=command.idempotency_key,
                idempotency_context={"semantic_survival_state_action": command.model_dump(mode="json")},
            )
        except ValueError as exc:
            return self._state_action_failure(command, str(exc) or "semantic_survival_state_action_rejected")
        if not plan.ready:
            if plan.duplicate_result is None:
                return self._state_action_failure(command, plan.error_code or "semantic_survival_state_action_rejected")
            result = plan.duplicate_result
        else:
            assert plan.owner_commit_batch is not None
            result = SurvivalAuthority(store=self.store).commit_obligation_batch(plan.owner_commit_batch)
        if not result.committed:
            return self._state_action_failure(command, result.failure.error_code if result.failure else "semantic_survival_state_action_rejected")
        append = self.store.get_by_idempotency(command.principal_ref, command.idempotency_key)
        if append is None:
            return self._state_action_failure(command, "semantic_survival_state_action_receipt_missing")
        if plan.idempotency_status == "duplicate_replayed":
            return append.model_copy(update={"idempotency_status": "duplicate_replayed"})
        return append

    def settle_registered_construction_maintenance_state_action(
        self, command: SemanticConstructionMaintenanceDispelCommand
    ) -> AppendBatchResult:
        """Delegate the fixed maintenance dispel action to the existing Construction owner."""
        try:
            route = self.registry.registered_construction_maintenance_state_action_route(
                effect_ref=command.effect_ref
            )
        except ValueError:
            return self._construction_state_action_failure(
                command,
                "semantic_construction_maintenance_state_action_route_unknown",
            )
        stream_id = f"gameplay:construction_production:{command.target_ref}"
        if (
            command.principal_ref != "authority:semantic"
            or command.owner_ref != route.owner_ref
            or command.stream_id != stream_id
            or route.stream_pattern != "gameplay:construction_production:{facility_ref}"
            or command.state_ref != route.state_ref
            or command.semantic_snapshot.entity_ref != command.target_ref
            or command.semantic_snapshot.digest != command.expected_snapshot_digest
            or command.semantic_snapshot.source_revision_vector != {"semantic": 1}
            or not command.reason_ref.strip()
        ):
            return self._construction_state_action_failure(
                command,
                "semantic_construction_maintenance_state_action_route_mismatch",
            )
        try:
            state_contract = self.registry.require_closed_state_owner_contract(
                effect_ref="effect:maintenance_required",
                state_ref=command.state_ref,
            )
            lifecycle = self.registry.require_closed_lifecycle_owner_contract(
                effect_ref="effect:maintenance_required",
                state_ref=command.state_ref,
            )
            self.registry.require_closed_state_lifecycle_adapter(
                effect_ref=state_contract.effect_ref,
                state_ref=command.state_ref,
                operation="dispel",
            )
        except ValueError:
            return self._construction_state_action_failure(
                command,
                "semantic_construction_maintenance_state_action_contract_unknown",
            )
        if (
            state_contract.owner_ref != "actor_gameplay.construction_production_domain"
            or state_contract.stream_pattern != "gameplay:construction_production:{facility_ref}"
            or state_contract.apply_event_type
            != "gameplay.construction_production.maintenance_state_applied"
            or state_contract.projection_scope != "project"
            or command.effect_ref not in lifecycle.action_effect_refs
            or route.event_type not in lifecycle.event_types
            or lifecycle.projection_scope != route.projection_scope
        ):
            return self._construction_state_action_failure(
                command,
                "semantic_construction_maintenance_state_action_contract_mismatch",
            )
        if command.privacy_scope != route.projection_scope:
            return self._construction_state_action_failure(command, "semantic_construction_privacy_scope_denied")
        existing = self.store.get_by_idempotency(command.principal_ref, command.idempotency_key)
        if existing is not None and existing.committed:
            obligation_id = self._construction_state_action_obligation_id(
                committed_event_ids=existing.committed_event_ids
            )
            if obligation_id is None:
                return self._construction_state_action_failure(command, "idempotency_key_reused")
            obligation = self._construction_maintenance_obligation(
                stream_id=stream_id,
                facility_ref=command.target_ref,
                obligation_id=obligation_id,
                expected_revision=command.expected_revision,
                idempotency_key=command.idempotency_key,
                require_open=False,
            )
            if obligation is None:
                return self._construction_state_action_failure(command, "idempotency_key_reused")
        else:
            if self.store.get_stream_head(stream_id) != command.expected_revision:
                return self._construction_state_action_failure(command, "revision_conflict")
            projection = ConstructionProductionAuthority(store=self.store).projector()
            existing_state = projection.maintenance_states.get(command.target_ref)
            if existing_state is None or existing_state.state_ref != command.state_ref:
                return self._construction_state_action_failure(
                    command,
                    "semantic_construction_maintenance_state_action_source_not_open",
                )
            action = EffectLifecycleEvaluator().resolve_dispel(
                state=state_contract.definition,
                existing_stacks=existing_state.stacks,
            )
            if not action.accepted:
                return self._construction_state_action_failure(
                    command,
                    action.error_code or "semantic_construction_maintenance_state_action_rejected",
                )
            obligation = self._construction_maintenance_obligation(
                stream_id=stream_id,
                facility_ref=command.target_ref,
                obligation_id=None,
                expected_revision=command.expected_revision,
                idempotency_key=command.idempotency_key,
                require_open=True,
            )
            if obligation is None:
                return self._construction_state_action_failure(
                    command,
                    "semantic_construction_maintenance_state_action_source_not_open",
                )
        try:
            fragment = ConstructionProductionAuthority.build_maintenance_state_dispel_fragment(
                obligation=obligation,
                facility_ref=command.target_ref,
                state_ref=command.state_ref,
                expected_revision=command.expected_revision,
                reason_ref=command.reason_ref,
            )
            coordinator = ObligationSettlementCoordinator(
                store=self.store,
                lifecycle_registrations=(
                    ConstructionProductionAuthority.maintenance_state_obligation_registration(
                        include_semantic_action_cancellation=True
                    ),
                ),
            )
            plan = coordinator.plan_cancel(
                obligation=obligation,
                fragment=fragment,
                principal_ref=command.principal_ref,
                reason_ref=command.reason_ref,
                idempotency_key=command.idempotency_key,
                idempotency_context={
                    "semantic_construction_maintenance_state_action": command.model_dump(mode="json")
                },
            )
        except ValueError as exc:
            return self._construction_state_action_failure(
                command,
                str(exc) or "semantic_construction_maintenance_state_action_rejected",
            )
        if not plan.ready:
            if plan.duplicate_result is None:
                return self._construction_state_action_failure(
                    command,
                    plan.error_code or "semantic_construction_maintenance_state_action_rejected",
                )
            result = plan.duplicate_result
        else:
            assert plan.owner_commit_batch is not None
            result = ConstructionProductionAuthority(store=self.store).commit_obligation_batch(plan.owner_commit_batch)
        if not result.committed:
            return self._construction_state_action_failure(
                command,
                result.failure.error_code if result.failure else "semantic_construction_maintenance_state_action_rejected",
            )
        append = self.store.get_by_idempotency(command.principal_ref, command.idempotency_key)
        if append is None:
            return self._construction_state_action_failure(
                command,
                "semantic_construction_maintenance_state_action_receipt_missing",
            )
        if plan.idempotency_status == "duplicate_replayed":
            return append.model_copy(update={"idempotency_status": "duplicate_replayed"})
        return append

    def settle_closed_survival_state(
        self,
        command: SemanticEffectCommand,
        *,
        application: EffectApplication,
        resistance: ResistanceProfile,
        state: StateDefinition,
    ) -> AppendBatchResult:
        """Submit the sole registered semantic state proposal to its Survival owner."""
        stream_id = f"gameplay:survival:{command.target_ref}"
        try:
            self.registry.state_lifecycle(state.state_ref)
        except ValueError:
            return self._failure(command, "semantic_state_lifecycle_unknown")
        try:
            lifecycle = self.registry.scheduled_state_owner_row(state_ref=state.state_ref, effect_ref=command.effect_ref)
            row = self.registry.registered_state_owner_row(state_ref=state.state_ref, effect_ref=command.effect_ref)
        except ValueError:
            return self._failure(command, "semantic_survival_owner_mapping_unregistered")
        if row.owner_ref != SurvivalAuthority._PRINCIPAL:
            return self._failure(command, "semantic_survival_owner_mapping_unregistered")
        if (
            command.principal_ref != "authority:semantic"
            or command.owner_ref != SurvivalAuthority._PRINCIPAL
            or command.stream_id != stream_id
            or application.effect_ref != command.effect_ref
            or application.target_component_ref != command.target_ref
            or state.expiry_policy != "scheduled"
            or lifecycle.owner_ref != SurvivalAuthority._PRINCIPAL
            or lifecycle.stream_pattern != "gameplay:survival:{actor_ref}"
            or lifecycle.opened_event_type != "gameplay.survival.obligation_opened"
            or lifecycle.settled_event_type != "gameplay.survival.obligation_settled"
            or lifecycle.cancelled_event_type != "gameplay.survival.obligation_cancelled"
            or lifecycle.fragment_builder_ref != "SurvivalAuthority.build_state_expiry_fragment"
            or lifecycle.projection_scope != "project"
            or state.model_dump(exclude={"dispel_allowed", "transform_targets"})
            != row.definition.model_dump(exclude={"dispel_allowed", "transform_targets"})
        ):
            return self._failure(command, "semantic_survival_owner_mapping_unregistered")
        if command.privacy_scope != "project":
            return self._failure(command, "semantic_survival_privacy_scope_denied")
        if command.semantic_snapshot.digest != command.expected_snapshot_digest:
            return self._failure(command, "semantic_snapshot_digest_mismatch")
        if command.semantic_snapshot.entity_ref != command.target_ref:
            return self._failure(command, "semantic_target_mismatch")
        try:
            self.registry.require_closed_semantic_source_vector(command.semantic_snapshot)
        except ValueError:
            return self._failure(command, "semantic_closed_registry_revision_mismatch")
        envelope = GameplayCommandEnvelope(
            command_id=command.command_id,
            command_type="gameplay.survival.apply_state",
            command_version=1,
            principal_ref=SurvivalAuthority._PRINCIPAL,
            actor_ref=command.target_ref,
            idempotency_key=command.idempotency_key,
            expected_revisions={stream_id: command.expected_revision},
            causation_id=command.causal_parent_refs[0] if command.causal_parent_refs else command.command_id,
            correlation_id=f"semantic-survival:{command.target_ref}",
            source_ref="semantic_registry",
            submitted_at="semantic-authority",
            pinned_revisions={
                **command.semantic_snapshot.source_revision_vector,
            },
            payload={
                "semantic_snapshot_digest": command.semantic_snapshot.digest,
                "effect_ref": command.effect_ref,
            },
        )
        return SurvivalAuthority(store=self.store).apply_effect_state(
            command=envelope,
            application=application,
            resistance=resistance,
            definition=state,
        )

    def settle_closed_ecology_frost(self, command: SemanticEcologyFrostCommand) -> AppendBatchResult:
        """Map one closed frost proposal to the existing Ecology owner command."""
        if (
            command.semantic_snapshot.digest != command.expected_snapshot_digest
            or command.semantic_snapshot.entity_ref != command.crop_ref
        ):
            return self._failure(command, "semantic_ecology_snapshot_mismatch")
        try:
            adapter = self.registry.require_closed_state_lifecycle_adapter(
                effect_ref=command.effect_ref,
                state_ref=command.state_ref,
                operation="apply",
            )
        except ValueError:
            return self._failure(command, "semantic_ecology_adapter_unregistered")
        if (
            adapter.owner_ref != "authority:ecology"
            or adapter.adapter_ref != "SemanticSettlementAuthority.settle_closed_ecology_frost"
            or adapter.revision != "1"
        ):
            return self._failure(command, "semantic_ecology_adapter_unregistered")
        from app.gameplay.ecology_runtime import EcologyHazardAuthority

        authority = EcologyHazardAuthority(store=self.store)
        stream_id = authority.ecology_stream_id(region_ref=command.region_ref)
        envelope = GameplayCommandEnvelope(
            command_id=command.command_id,
            command_type="gameplay.ecology.apply_crop_state",
            command_version=1,
            principal_ref=authority._PRINCIPAL,
            actor_ref=command.crop_ref,
            idempotency_key=command.idempotency_key,
            expected_revisions={stream_id: command.expected_revision},
            causation_id=command.hazard_ref,
            correlation_id=f"semantic-ecology:{command.hazard_ref}:{command.crop_ref}",
            source_ref=authority._PRINCIPAL,
            submitted_at="semantic-authority",
            pinned_revisions={"ecology": command.expected_revision, "semantic": command.semantic_snapshot.source_revision_vector.get("semantic", 0)},
            payload={"visibility_scope": "project"},
        )
        return authority.apply_crop_state(
            command=envelope,
            hazard_ref=command.hazard_ref,
            crop_ref=command.crop_ref,
            application=EffectApplication(effect_ref="effect:frost", target_component_ref=command.crop_ref, magnitude=command.magnitude, stack_key="crop-state:frost", expires_at_tick=command.due_tick, causal_chain_id=command.hazard_ref),
            resistance=ResistanceProfile(effect_ref="effect:frost", source_ref=command.crop_ref, modifier_basis_points=0, revision=command.resistance_revision),
            definition=StateDefinition(state_ref="state:frosted@1", stack_policy="refresh", stack_limit=1, expiry_policy="scheduled"),
        )

    def settle_closed_ecology_drought(self, command: SemanticEcologyDroughtCommand) -> AppendBatchResult:
        """Map one closed drought proposal to the existing Ecology owner command."""
        if (
            command.semantic_snapshot.digest != command.expected_snapshot_digest
            or command.semantic_snapshot.entity_ref != command.region_ref
        ):
            return self._failure(command, "semantic_ecology_snapshot_mismatch")
        try:
            adapter = self.registry.require_closed_state_lifecycle_adapter(
                effect_ref=command.effect_ref,
                state_ref=command.state_ref,
                operation="apply",
            )
        except ValueError:
            return self._failure(command, "semantic_ecology_drought_adapter_unregistered")
        if (
            adapter.owner_ref != "authority:ecology"
            or adapter.adapter_ref != "SemanticSettlementAuthority.settle_closed_ecology_drought"
            or adapter.revision != "1"
        ):
            return self._failure(command, "semantic_ecology_drought_adapter_unregistered")
        from app.gameplay.ecology_runtime import EcologyHazardAuthority

        authority = EcologyHazardAuthority(store=self.store)
        stream_id = authority.ecology_stream_id(region_ref=command.region_ref)
        envelope = GameplayCommandEnvelope(
            command_id=command.command_id,
            command_type="gameplay.ecology.apply_drought_state",
            command_version=1,
            principal_ref=authority._PRINCIPAL,
            actor_ref=command.region_ref,
            idempotency_key=command.idempotency_key,
            expected_revisions={stream_id: command.expected_revision},
            causation_id=command.source_event_id,
            correlation_id=f"semantic-ecology-drought:{command.region_ref}:{command.source_event_id}",
            source_ref=authority._PRINCIPAL,
            submitted_at="semantic-authority",
            pinned_revisions={
                "ecology": command.expected_revision,
                "semantic": command.semantic_snapshot.source_revision_vector.get("semantic", 0),
            },
            payload={"visibility_scope": "project"},
        )
        return authority.apply_drought_state(
            command=envelope,
            region_ref=command.region_ref,
            source_event_id=command.source_event_id,
            source_event_revision=command.source_event_revision,
            application=EffectApplication(
                effect_ref="effect:drought",
                target_component_ref=command.region_ref,
                magnitude=1,
                stack_key="ecology-state:drought",
                expires_at_tick=command.due_tick,
                causal_chain_id=command.source_event_id,
            ),
            resistance=ResistanceProfile(
                effect_ref="effect:drought",
                source_ref=command.region_ref,
                modifier_basis_points=0,
                revision=command.resistance_revision,
            ),
            definition=StateDefinition(
                state_ref="state:drought@1",
                stack_policy="refresh",
                stack_limit=1,
                expiry_policy="scheduled",
            ),
        )

    def settle_closed_ecology_frost_state_action(
        self, command: SemanticEcologyFrostStateActionCommand
    ) -> AppendBatchResult:
        """Propose one fixed frost dispel; Ecology retains the only write path."""
        if (
            command.semantic_snapshot.digest != command.expected_snapshot_digest
            or command.semantic_snapshot.entity_ref != command.crop_ref
        ):
            return self._failure(command, "semantic_ecology_snapshot_mismatch")
        if command.privacy_scope != "project":
            return self._failure(command, "semantic_ecology_action_privacy_denied")
        try:
            lifecycle = self.registry.require_closed_lifecycle_owner_contract(
                effect_ref="effect:frost", state_ref=command.state_ref
            )
            state_contract = self.registry.require_closed_state_owner_contract(
                effect_ref="effect:frost", state_ref=command.state_ref
            )
        except ValueError:
            return self._failure(command, "semantic_ecology_action_unregistered")
        if (
            lifecycle.owner_ref != "authority:ecology"
            or command.effect_ref not in lifecycle.action_effect_refs
            or lifecycle.projection_scope != "project"
            or state_contract.definition.dispel_allowed is not True
            or "gameplay.ecology.crop_state_dispelled" not in lifecycle.event_types
            or "gameplay.ecology.crop_state_obligation_cancelled" not in lifecycle.event_types
        ):
            return self._failure(command, "semantic_ecology_action_unregistered")
        from app.gameplay.ecology_runtime import EcologyHazardAuthority

        authority = EcologyHazardAuthority(store=self.store)
        stream_id = authority.ecology_stream_id(region_ref=command.region_ref)
        envelope = GameplayCommandEnvelope(
            command_id=command.command_id,
            command_type="gameplay.ecology.dispel_frost_crop_state",
            command_version=1,
            principal_ref=authority._PRINCIPAL,
            actor_ref=command.crop_ref,
            idempotency_key=command.idempotency_key,
            expected_revisions={stream_id: command.expected_revision},
            causation_id=command.hazard_ref,
            correlation_id=f"semantic-ecology-action:{command.hazard_ref}:{command.crop_ref}",
            source_ref=authority._PRINCIPAL,
            submitted_at="semantic-authority",
            pinned_revisions={
                "ecology": command.expected_revision,
                "semantic": command.semantic_snapshot.source_revision_vector.get("semantic", 0),
            },
            payload={
                "visibility_scope": "project",
                "effect_ref": command.effect_ref,
                "semantic_snapshot_digest": command.semantic_snapshot.digest,
            },
        )
        return authority.dispel_frost_crop_state(
            command=envelope,
            hazard_ref=command.hazard_ref,
            crop_ref=command.crop_ref,
            definition=state_contract.definition,
        )

    def settle_production_finish(self, command: SemanticProductionFinishCommand) -> AppendBatchResult:
        """Map one closed semantic proposal through the production owner's fragment."""
        existing = self.store.get_by_idempotency(command.principal_ref, command.idempotency_key)
        if existing is not None and existing.committed:
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"})
        stream_id = f"gameplay:construction_production:{command.run.facility_ref}"
        try:
            if command.semantic_snapshot.digest != command.expected_snapshot_digest:
                return self._production_failure(command, "semantic_snapshot_digest_mismatch")
            if command.semantic_snapshot.entity_ref != command.run.facility_ref:
                return self._production_failure(command, "semantic_target_mismatch")
            if command.privacy_scope == "private_evidence":
                return self._production_failure(command, "semantic_privacy_scope_denied")
            if self.store.get_stream_head(stream_id) != command.expected_revision:
                return self._production_failure(command, "revision_conflict")
            fragment = ConstructionProductionAuthority.build_due_finish_fragment(
                run=command.run,
                recipe=command.recipe,
                tick=command.tick,
                expected_revision=command.expected_revision,
            )
            payload = fragment.event_specs[stream_id][0][1]
            fragment = fragment.model_copy(
                update={
                    "source_rule_ref": command.source_rule_ref,
                    "pinned_revisions": {
                        **fragment.pinned_revisions,
                        "semantic": command.semantic_snapshot.source_revision_vector.get("semantic", 0),
                    },
                    "event_specs": {
                        stream_id: (
                            (
                                "gameplay.construction_production.run_finished",
                                {
                                    **payload,
                                    "effect_ref": command.effect_ref,
                                    "rule_set_revision": command.rule_set_revision,
                                    "semantic_snapshot_digest": command.semantic_snapshot.digest,
                                    "causal_chain_id": command.causal_chain_id,
                                    "trace_digest": command.trace_digest,
                                },
                            ),
                        )
                    },
                },
                deep=True,
            )
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=command.command_id,
                idempotency_principal_ref=command.principal_ref,
                idempotency_key=command.idempotency_key,
                causation_id=command.causal_chain_id,
                correlation_id=f"semantic-production:{command.run.run_ref}",
                fragments=(fragment,),
            )
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="construction_production.scoped_projection",
                            audience=command.privacy_scope,
                            payload_projection={
                                "facility_ref": command.run.facility_ref,
                                "run_ref": command.run.run_ref,
                                "effect_ref": command.effect_ref,
                                "trace_digest": command.trace_digest,
                            },
                        )
                    ]
                },
                deep=True,
            )
            return self.store.append_batch(batch)
        except ValueError as exc:
            return self._production_failure(command, str(exc) or "semantic_production_settlement_rejected")

    def settle_closed_production_finish(self, command: SemanticProductionFinishCommand) -> AppendBatchResult:
        """Admit the production row only when the closed registry confirms it."""
        try:
            existing = self.store.get_by_idempotency(command.principal_ref, command.idempotency_key)
            command_digest = _digest(command.model_dump(mode="json"))
            if existing is not None and existing.committed:
                stored = self.store.get_idempotency_record(command.principal_ref, command.idempotency_key)
                if stored is None or stored.payload_digest != command_digest:
                    return self._production_failure(command, "idempotency_key_reused_with_different_payload")
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"})
            evaluation = self.registry.evaluate_closed_rule_set(
                rule_set_ref=command.rule_set_revision,
                effect_ref=command.effect_ref,
                target_ref=command.run.facility_ref,
                semantic_snapshot_digest=command.semantic_snapshot.digest,
            )
            if command.source_rule_ref not in evaluation.rule_refs:
                return self._production_failure(command, "semantic_closed_rule_unknown")
            if evaluation.owner_mapping.owner_ref != ConstructionProductionAuthority._PRINCIPAL:
                return self._production_failure(command, "semantic_owner_mapping_unregistered")
            return self._settle_closed_production_finish(command, trace_digest=evaluation.trace_digest, command_digest=command_digest)
        except ValueError as exc:
            return self._production_failure(command, str(exc) or "semantic_closed_rule_rejected")

    def settle_closed_construction_maintenance_state(
        self,
        command: SemanticEffectCommand,
        *,
        application: EffectApplication,
        resistance: ResistanceProfile,
        state: StateDefinition,
    ) -> AppendBatchResult:
        stream_id = f"gameplay:construction_production:{command.target_ref}"
        try:
            row = self.registry.construction_maintenance_owner_row(
                state_ref=state.state_ref,
                effect_ref=command.effect_ref,
            )
        except ValueError:
            return self._failure(command, "semantic_construction_owner_mapping_unregistered")
        if (
            command.principal_ref != "authority:semantic"
            or command.owner_ref != ConstructionProductionAuthority._PRINCIPAL
            or command.stream_id != stream_id
            or row.owner_ref != ConstructionProductionAuthority._PRINCIPAL
            or row.stream_pattern != "gameplay:construction_production:{facility_ref}"
            or row.event_type != "gameplay.construction_production.maintenance_state_applied"
            or row.projection_scope != "project"
            or application.effect_ref != command.effect_ref
            or application.target_component_ref != command.target_ref
            or state != row.definition
        ):
            return self._failure(command, "semantic_construction_owner_mapping_unregistered")
        if command.privacy_scope != "project":
            return self._failure(command, "semantic_construction_privacy_scope_denied")
        if command.semantic_snapshot.digest != command.expected_snapshot_digest:
            return self._failure(command, "semantic_snapshot_digest_mismatch")
        if command.semantic_snapshot.entity_ref != command.target_ref:
            return self._failure(command, "semantic_target_mismatch")
        try:
            self.registry.require_closed_semantic_source_vector(command.semantic_snapshot)
        except ValueError:
            return self._failure(command, "semantic_closed_registry_revision_mismatch")
        return ConstructionProductionAuthority(store=self.store).apply_maintenance_state(
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            facility_ref=command.target_ref,
            expected_revision=command.expected_revision,
            causation_id=command.causal_parent_refs[0] if command.causal_parent_refs else command.command_id,
            correlation_id=f"semantic-construction:{command.target_ref}",
            source_ref="semantic_registry",
            submitted_at="semantic-authority",
            pinned_revisions=dict(command.semantic_snapshot.source_revision_vector),
            semantic_snapshot_digest=command.semantic_snapshot.digest,
            application=application,
            resistance=resistance,
            definition=state,
        )

    def _settle_closed_production_finish(
        self, command: SemanticProductionFinishCommand, *, trace_digest: str, command_digest: str
    ) -> AppendBatchResult:
        stream_id = f"gameplay:construction_production:{command.run.facility_ref}"
        try:
            if command.semantic_snapshot.digest != command.expected_snapshot_digest:
                return self._production_failure(command, "semantic_snapshot_digest_mismatch")
            if command.semantic_snapshot.entity_ref != command.run.facility_ref:
                return self._production_failure(command, "semantic_target_mismatch")
            if command.privacy_scope == "private_evidence":
                return self._production_failure(command, "semantic_privacy_scope_denied")
            if self.store.get_stream_head(stream_id) != command.expected_revision:
                return self._production_failure(command, "revision_conflict")
            fragment = ConstructionProductionAuthority.build_due_finish_fragment(run=command.run, recipe=command.recipe, tick=command.tick, expected_revision=command.expected_revision)
            payload = fragment.event_specs[stream_id][0][1]
            fragment = fragment.model_copy(update={"source_rule_ref": command.source_rule_ref, "pinned_revisions": {**fragment.pinned_revisions, "semantic": command.semantic_snapshot.source_revision_vector.get("semantic", 0)}, "event_specs": {stream_id: (("gameplay.construction_production.run_finished", {**payload, "effect_ref": command.effect_ref, "rule_set_revision": command.rule_set_revision, "semantic_snapshot_digest": command.semantic_snapshot.digest, "causal_chain_id": command.causal_chain_id, "trace_digest": trace_digest}),)}}, deep=True)
            batch = build_multi_stream_atomic_event_batch_from_fragments(command_id=command.command_id, idempotency_principal_ref=command.principal_ref, idempotency_key=command.idempotency_key, causation_id=command.causal_chain_id, correlation_id=f"semantic-production:{command.run.run_ref}", fragments=(fragment,))
            event = batch.events[0]
            batch = batch.model_copy(update={"idempotency_record": batch.idempotency_record.model_copy(update={"payload_digest": command_digest}), "outbox_entries": [GameplayOutboxEntry(outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id, event_id=event.event_id, global_sequence=0, topic="construction_production.scoped_projection", audience=command.privacy_scope, payload_projection={"facility_ref": command.run.facility_ref, "run_ref": command.run.run_ref, "effect_ref": command.effect_ref, "trace_digest": trace_digest})]}, deep=True)
            return self.store.append_batch(batch)
        except ValueError as exc:
            return self._production_failure(command, str(exc) or "semantic_closed_rule_rejected")

    def project_scope(self, target_ref: str, *, scope: Literal["public", "authority"] = "public") -> dict[str, object]:
        projection = EntityCausalProjection().rebuild(self.store.read_events())
        dossier = projection.dossier(target_ref)
        causal_refs = tuple(sorted(event.event_ref for event in projection.causal_events.values() if any(ref.entity_type + ":" + ref.entity_id == target_ref for ref in event.affected_entity_refs)))
        result = {
            "entity": dossier["entity"],
            "causal_event_refs": causal_refs,
            "evidence_refs": () if scope == "public" else tuple(
                ref for event in projection.causal_events.values() if event.event_ref in causal_refs for ref in event.evidence_refs
            ),
        }
        return result

    def replay_projection(self, *, checkpoint_at: int | None = None):
        events = self.store.read_events()
        replay = GameplayProjectionReplay(projector_id="semantic-authority", projector_version="1")
        full = replay.full_replay(events)
        if checkpoint_at is None:
            return full
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    @staticmethod
    def _to_semantic_effect_command(command: RegisteredStateApplyCommand) -> SemanticEffectCommand:
        return SemanticEffectCommand(
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            principal_ref=command.principal_ref,
            owner_ref=command.owner_ref,
            stream_id=command.stream_id,
            expected_revision=command.expected_revision,
            effect_ref=command.effect_ref,
            target_ref=command.target_ref,
            semantic_snapshot=command.semantic_snapshot,
            expected_snapshot_digest=command.expected_snapshot_digest,
            privacy_scope=command.privacy_scope,
        )

    @staticmethod
    def _registered_state_failure(command: RegisteredStateApplyCommand, code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command.command_id}",
            command_id=command.command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=code, message=code, failed_stage="semantic_authority"),
        )

    def _failure(self, command: SemanticEffectCommand, code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command.command_id}",
            command_id=command.command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=code, message=code, failed_stage="semantic_authority"),
        )

    def _wage_failure(self, command: SemanticWageObligationCommand, code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command.command_id}",
            command_id=command.command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=code, message=code, failed_stage="semantic_authority"),
        )

    @staticmethod
    def _state_action_failure(command: SemanticSurvivalStateActionCommand, code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command.command_id}",
            command_id=command.command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=code, message=code, failed_stage="semantic_authority"),
        )

    @staticmethod
    def _construction_state_action_failure(
        command: SemanticConstructionMaintenanceDispelCommand, code: str
    ) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command.command_id}",
            command_id=command.command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=code, message=code, failed_stage="semantic_authority"),
        )

    def _state_action_opened_due_tick(self, *, stream_id: str, obligation_id: str) -> int | None:
        for event in reversed(self.store.read_events()):
            if (
                event.stream_id == stream_id
                and event.event_type == "gameplay.survival.obligation_opened"
                and event.payload.get("obligation_id") == obligation_id
                and isinstance(event.payload.get("due_tick"), int)
                and not isinstance(event.payload.get("due_tick"), bool)
            ):
                return int(event.payload["due_tick"])
        return None

    def _construction_maintenance_obligation(
        self,
        *,
        stream_id: str,
        facility_ref: str,
        obligation_id: str | None,
        expected_revision: int,
        idempotency_key: str,
        require_open: bool,
    ):
        terminal_ids = {
            str(event.payload.get("obligation_id", ""))
            for event in self.store.read_stream(stream_id)
            if event.event_type
            in {
                "gameplay.construction_production.maintenance_state_expired",
                "gameplay.construction_production.maintenance_state_obligation_settled",
                "gameplay.construction_production.maintenance_state_obligation_cancelled",
            }
        }
        for event in reversed(self.store.read_stream(stream_id)):
            if event.event_type != "gameplay.construction_production.maintenance_state_obligation_opened":
                continue
            payload = event.payload
            candidate_id = str(payload.get("obligation_id", ""))
            due_tick = payload.get("due_tick")
            state_event_id = payload.get("state_event_id")
            if (
                payload.get("facility_ref") != facility_ref
                or (obligation_id is not None and candidate_id != obligation_id)
                or not candidate_id
                or not isinstance(due_tick, int)
                or isinstance(due_tick, bool)
                or not isinstance(state_event_id, str)
                or not state_event_id
            ):
                continue
            if require_open and candidate_id in terminal_ids:
                continue
            return ConstructionProductionAuthority.build_maintenance_state_obligation(
                facility_ref=facility_ref,
                obligation_id=candidate_id,
                state_event_id=state_event_id,
                due_tick=due_tick,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
            )
        return None

    def _construction_state_action_obligation_id(
        self, *, committed_event_ids: tuple[str, ...]
    ) -> str | None:
        for event_id in committed_event_ids:
            event = self.store.get_event(event_id)
            if event.event_type == "gameplay.construction_production.maintenance_state_dispelled":
                obligation_id = event.payload.get("obligation_id")
                if isinstance(obligation_id, str) and obligation_id:
                    return obligation_id
        return None

    @staticmethod
    def _production_failure(command: SemanticProductionFinishCommand, code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command.command_id}",
            command_id=command.command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=code, message=code, failed_stage="semantic_production_authority"),
        )


__all__ = [
    "RegisteredStateApplyCommand",
    "RegisteredStateApplyConstructionProvenance",
    "RegisteredStateApplyEcologyDroughtProvenance",
    "RegisteredStateApplyEcologyFrostProvenance",
    "RegisteredStateApplySurvivalProvenance",
    "SemanticConstructionMaintenanceDispelCommand",
    "SemanticEcologyDroughtCommand",
    "SemanticEffectCommand",
    "SemanticProductionFinishCommand",
    "SemanticSettlementAuthority",
    "SemanticSurvivalStateActionCommand",
    "SemanticWageObligationCommand",
]
