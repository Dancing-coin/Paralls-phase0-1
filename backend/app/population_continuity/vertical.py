from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from app.character_agent.models.simulation_seed import (
    CharacterContinuityCommand,
    CharacterMemoryCandidate,
)
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.graph_continuity_store import (
    CharacterGraphContinuityStore,
)
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.bakery_mirror_source import BakeryMirrorSource
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.replay import GameplayProjectionReplay
from app.models.authority_event import (
    AuthorityEvent,
    AuthorityEventRouting,
    AuthorityEventSource,
)
from app.models.player_input import DialogueSubmit
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.session_input_router import SessionInputRouter
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_population_capability import PopulationSimulationCapability
from app.services.siming_runtime import SimingRuntime
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter

from .activation import ProfileActivationAuthority
from .activation_policy import ActivationPolicy
from .batch import ContinuityMergeAuthority, PopulationPlanner
from .models import (
    ActivationProposal,
    BatchIntentCandidate,
    PendingChange,
    PopulationWorldPlan,
    WorldModeProfile,
)
from .social_input import FrozenSocialPlanningInput
from .source_inputs import HouseholdScheduleInput, OrganizationScheduleInput
from .owner_adapters import ScheduleGatedSupplyOwnerExecutor
from .siming_contracts import (
    PopulationCadenceInput,
    PopulationCycleResult,
    PopulationOwnerReceipt,
    PopulationProjection,
)
from .world import WorldContinuityRuntime


@dataclass
class BakeryDistrictPopulationFixture:
    registry: CharacterProfileRegistry
    store: GameplayEventStore
    scenario: BakeryReferenceScenario
    mode: WorldModeProfile

    @classmethod
    def create(cls, *, profile_dir: str | Path) -> "BakeryDistrictPopulationFixture":
        registry = CharacterProfileRegistry.from_directory(profile_dir)
        refs = {f"character:{actor}" for actor in registry.actor_ids()}
        required = {"character:char_a", "character:char_b", "character:char_c"}
        if not required.issubset(refs):
            raise ValueError("bakery_population_registered_profiles_required")
        base = BakeryReferenceScenario.default()
        organization = base.organization.model_copy(
            update={"owner_character_ref": "character:char_a"}
        )
        scenario = replace(
            base, owner_character_ref="character:char_a", organization=organization
        )
        scenario = scenario.with_existing_character_employee(
            "character:char_b"
        ).with_existing_character_employee("character:char_c")
        mode = WorldModeProfile(
            world_ref="world:bakery-district",
            mode="simulation",
            revision="mode:bakery-district:v1",
            cadence_class="daily",
            batch_limit=4,
            wake_budget=4,
            catch_up_limit=2,
            allowed_intent_kinds=("work", "supply", "inspection"),
            survival_mode="narrative",
            degraded_threshold=3,
        )
        return cls(
            registry=registry, store=GameplayEventStore(), scenario=scenario, mode=mode
        )

    @staticmethod
    def _digest(value: object) -> str:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def _frozen_household_input(
        self, *, recipient_ref: str, observed_at: str
    ) -> HouseholdScheduleInput:
        memberships: tuple[dict[str, object], ...] = ()
        source_revision_vector: dict[str, int] = {}
        projection_digest = self._digest(
            {
                "household_memberships": memberships,
                "source_revision_vector": source_revision_vector,
            }
        )
        return HouseholdScheduleInput(
            recipient_ref=recipient_ref,
            observed_at=observed_at,
            owner_principal_ref="authority:p5:social",
            projection_digest=projection_digest,
            source_revision_vector=source_revision_vector,
            household_memberships=memberships,
        )

    def _frozen_social_input(
        self, *, recipient_ref: str, observed_at: str
    ) -> FrozenSocialPlanningInput:
        return FrozenSocialPlanningInput(
            recipient_ref=recipient_ref,
            observed_at=observed_at,
            projection_digest=self._digest(
                {
                    "recipient_ref": recipient_ref,
                    "observed_at": observed_at,
                    "relationship_facts": (),
                    "knowledge_facts": (),
                    "reputation": {},
                }
            ),
            source_revision_vector={},
            relationship_facts=(),
            knowledge_facts=(),
            reputation={},
        )

    def _schedule_inputs(
        self, *, recipient_ref: str, observed_at: str, schedule_ref: str
    ) -> tuple[
        FrozenSocialPlanningInput,
        HouseholdScheduleInput,
        OrganizationScheduleInput,
    ]:
        organization = OrganizationAuthority(store=self.store)
        organization.record_schedule(
            command_id=f"command:district:schedule:{schedule_ref}",
            organization_ref=self.scenario.organization.organization_ref,
            recipient_ref=recipient_ref,
            membership_ref=f"membership:{schedule_ref}",
            assignment_ref=f"assignment:{schedule_ref}",
            role="baker",
            shift_ref=f"shift:{schedule_ref}",
            operating_window_ref=f"window:{schedule_ref}",
            work_order_ref="work:bread",
            effective_from=observed_at,
            effective_to=None,
            visibility_scope=f"actor:{recipient_ref}",
        )
        return (
            self._frozen_social_input(recipient_ref=recipient_ref, observed_at=observed_at),
            self._frozen_household_input(
                recipient_ref=recipient_ref, observed_at=observed_at
            ),
            OrganizationScheduleInput.freeze(
                recipient_ref=recipient_ref,
                observed_at=observed_at,
                view=organization.schedule_view_for(
                    organization_ref=self.scenario.organization.organization_ref,
                    recipient_ref=recipient_ref,
                    observed_at=observed_at,
                ),
            ),
        )

    def _plan_schedule_gated_supply(
        self,
        *,
        batch_ref: str,
        recipient_ref: str,
        observed_at: str,
        report_scope: str = "actor:self",
        work_order_ref: str = "work:bread",
        activation_lock_refs: tuple[str, ...] = (),
    ) -> tuple[
        object,
        FrozenSocialPlanningInput,
        HouseholdScheduleInput,
        OrganizationScheduleInput,
    ]:
        social_input, household_input, organization_input = self._schedule_inputs(
            recipient_ref=recipient_ref,
            observed_at=observed_at,
            schedule_ref=batch_ref,
        )
        candidate = self._schedule_supply_candidate(
            batch_ref=batch_ref,
            recipient_ref=recipient_ref,
            organization_input=organization_input,
            work_order_ref=work_order_ref,
        )
        return (
            PopulationPlanner().plan_schedule_gated_supply(
                store=self.store,
                batch_ref=batch_ref,
                world_ref=self.mode.world_ref,
                mode=self.mode,
                social_input=social_input,
                household_input=household_input,
                organization_input=organization_input,
                candidate=candidate,
                base_event_digest=self._digest(
                    {
                        "event_count": len(self.store.read_events()),
                        "world_ref": self.mode.world_ref,
                    }
                ),
                tail_boundary=len(self.store.read_events()),
                active_revision_refs=(self.mode.revision,),
                deterministic_seed=f"seed:{batch_ref}",
                report_scope=report_scope,
                activation_lock_refs=activation_lock_refs,
            ),
            social_input,
            household_input,
            organization_input,
        )

    def _schedule_supply_candidate(
        self,
        *,
        batch_ref: str,
        recipient_ref: str,
        organization_input: OrganizationScheduleInput,
        work_order_ref: str,
    ) -> BatchIntentCandidate:
        return BatchIntentCandidate(
            intent_ref=f"intent:{batch_ref}:supply",
            profile_ref=recipient_ref,
            intent_kind="supply",
            payload={
                "organization_ref": self.scenario.organization.organization_ref,
                "counterparty_organization_ref": "org:supplier",
                "commitment_ref": f"commitment:{batch_ref}",
                "organization_grant_refs": [],
                "budget_reservation_refs": [],
                "schedule_work_order_ref": work_order_ref,
            },
            priority=2,
            claim_refs=("claim:supply",),
            expected_revisions=dict(organization_input.source_revision_vector),
            policy_revision=self.mode.revision,
            package_revision="package:bakery-authored-agents:v1",
            idempotency_key=f"intent:{batch_ref}:supply",
            correlation_id=f"correlation:{batch_ref}",
            source_ref="population:district-planner",
            privacy_scope="actor:self",
        )

    def _admit_released_schedule_gated_supply(
        self,
        *,
        activation: ProfileActivationAuthority,
        batch_ref: str,
        recipient_ref: str,
        plan: PopulationWorldPlan,
    ) -> tuple[object, object, str]:
        stream = f"population:{self.mode.world_ref}"
        lock_ref = f"lock:{self.mode.world_ref}:{recipient_ref}"
        held_revision = self.store.get_stream_head(stream)
        locked = activation.lock(
            world_ref=self.mode.world_ref,
            profile_ref=recipient_ref,
            expected_revision=held_revision,
        )
        change_ref = f"pending:{batch_ref}:schedule_gated_supply"
        pending = activation.record_pending(
            PendingChange(
                change_ref=change_ref,
                lock_ref=lock_ref,
                profile_ref=recipient_ref,
                expected_revision=held_revision,
                payload={
                    "kind": "schedule_gated_supply",
                    "plan_digest": PopulationPlanner.schedule_pending_digest(plan),
                },
                privacy_scope="actor:self",
            )
        )
        if locked.committed and pending.committed:
            activation.release_lock(
                lock_ref=lock_ref,
                expected_revision=self.store.get_stream_head(stream),
            )
        return locked, pending, change_ref

    def run(self) -> dict[str, object]:
        activation = ProfileActivationAuthority(
            registry=self.registry, store=self.store
        )
        activation_receipts = []
        for actor in ("character:char_a", "character:char_b", "character:char_c"):
            stream = "population:world:bakery-district"
            activation_receipts.append(
                activation.commit(
                    ActivationProposal(
                        proposal_id=f"proposal:district:{actor}",
                        profile_ref=actor,
                        world_ref="world:bakery-district",
                        package_revision="package:bakery-authored-agents:v1",
                        policy_revision=self.mode.revision,
                        activation_reason="bakery-district",
                        scope_grant=("actor:self", "organization:summary"),
                        cadence_class="simulation",
                        expected_revisions={stream: self.store.get_stream_head(stream)},
                        idempotency_key=f"activation:district:{actor}",
                        correlation_id="correlation:district",
                        source_ref="population:district-authority",
                    )
                )
            )
        suspended = activation.suspend(
            "world:bakery-district",
            "character:char_c",
            expected_revision=self.store.get_stream_head(
                "population:world:bakery-district"
            ),
        )
        requeued = activation.requeue(
            "world:bakery-district",
            "character:char_c",
            expected_revision=self.store.get_stream_head(
                "population:world:bakery-district"
            ),
        )
        reactivated = activation.commit(
            ActivationProposal(
                proposal_id="proposal:district:reactivate:character:char_c",
                profile_ref="character:char_c",
                world_ref="world:bakery-district",
                package_revision="package:bakery-authored-agents:v1",
                policy_revision=self.mode.revision,
                activation_reason="requeue-recovery",
                scope_grant=("actor:self", "organization:summary"),
                cadence_class="simulation",
                expected_revisions={
                    "population:world:bakery-district": self.store.get_stream_head(
                        "population:world:bakery-district"
                    )
                },
                idempotency_key="activation:district:reactivate:character:char_c",
                correlation_id="correlation:district",
                source_ref="population:district-authority",
            )
        )
        periods = self.scenario.run_three_periods(store=self.store)
        godot_mirror = BakeryMirrorSource(
            scenario=self.scenario, events=self.store.read_events()
        ).godot_view()
        runtime = WorldContinuityRuntime(store=self.store, mode=self.mode)
        pause = runtime.pause(reason="district-maintenance")
        resume = runtime.resume()
        merger = ContinuityMergeAuthority(
            store=self.store, registry=self.registry, mode=self.mode
        )
        observed_at = "2026-08-13T00:00:00Z"
        lock_ref = f"lock:{self.mode.world_ref}:character:char_a"
        scheduled, social_input, household_input, organization_input = (
            self._plan_schedule_gated_supply(
                batch_ref="batch:district:released",
                recipient_ref="character:char_a",
                observed_at=observed_at,
                activation_lock_refs=(lock_ref,),
            )
        )
        if not scheduled.accepted or scheduled.plan is None:
            raise RuntimeError("district_schedule_plan_rejected")
        _, _, pending_change_ref = self._admit_released_schedule_gated_supply(
            activation=activation,
            batch_ref="batch:district:released",
            recipient_ref="character:char_a",
            plan=scheduled.plan,
        )
        merged = merger.merge_released_schedule_gated_supply(
            plan=scheduled.plan,
            pending_change_ref=pending_change_ref,
            social_input=social_input,
            household_input=household_input,
            organization_input=organization_input,
        )
        merged_duplicate = merger.merge_released_schedule_gated_supply(
            plan=scheduled.plan,
            pending_change_ref=pending_change_ref,
            social_input=social_input,
            household_input=household_input,
            organization_input=organization_input,
        )
        conflict_plan_result, conflict_social, conflict_household, conflict_organization = (
            self._plan_schedule_gated_supply(
                batch_ref="batch:district:revision-conflict",
                recipient_ref="character:char_a",
                observed_at=observed_at,
                activation_lock_refs=(lock_ref,),
            )
        )
        if not conflict_plan_result.accepted or conflict_plan_result.plan is None:
            raise RuntimeError("district_conflict_plan_rejected")
        _, _, conflict_pending_change_ref = self._admit_released_schedule_gated_supply(
            activation=activation,
            batch_ref="batch:district:revision-conflict",
            recipient_ref="character:char_a",
            plan=conflict_plan_result.plan,
        )
        OrganizationAuthority(store=self.store).record_schedule(
            command_id="command:district:schedule:revision-conflict",
            organization_ref=self.scenario.organization.organization_ref,
            recipient_ref="character:char_a",
            membership_ref="membership:character:char_a:revision-conflict",
            assignment_ref="assignment:character:char_a:revision-conflict",
            role="baker",
            shift_ref="shift:late",
            operating_window_ref="window:late",
            work_order_ref="work:bread:late",
            effective_from=observed_at,
            effective_to=None,
            visibility_scope="actor:character:char_a",
        )
        revision_conflict = merger.merge_released_schedule_gated_supply(
            plan=conflict_plan_result.plan,
            pending_change_ref=conflict_pending_change_ref,
            social_input=conflict_social,
            household_input=conflict_household,
            organization_input=conflict_organization,
        )
        privacy_plan_result, privacy_social, privacy_household, privacy_organization = (
            self._plan_schedule_gated_supply(
                batch_ref="batch:district:privacy",
                recipient_ref="character:char_a",
                observed_at=observed_at,
            )
        )
        if not privacy_plan_result.accepted or privacy_plan_result.plan is None:
            raise RuntimeError("district_privacy_plan_rejected")
        privacy_denial = merger.merge_schedule_gated_supply(
            plan=privacy_plan_result.plan.model_copy(
                update={"report_scope": "public"}, deep=True
            ),
            social_input=privacy_social,
            household_input=privacy_household,
            organization_input=privacy_organization,
        )
        before_rejected = len(self.store.read_events())
        rejected_input = PopulationPlanner().plan_schedule_gated_supply(
            store=self.store,
            batch_ref="batch:district:rejected-input",
            world_ref=self.mode.world_ref,
            mode=self.mode,
            social_input=privacy_social,
            household_input=privacy_household,
            organization_input=privacy_organization,
            candidate=self._schedule_supply_candidate(
                batch_ref="batch:district:rejected-input",
                recipient_ref="character:char_a",
                organization_input=privacy_organization,
                work_order_ref="work:missing",
            ),
            base_event_digest=self._digest(
                {
                    "event_count": len(self.store.read_events()),
                    "world_ref": self.mode.world_ref,
                }
            ),
            tail_boundary=len(self.store.read_events()),
            active_revision_refs=(self.mode.revision,),
            deterministic_seed="seed:batch:district:rejected-input",
            report_scope="actor:self",
        )
        rejected_input_zero_write = len(self.store.read_events()) == before_rejected
        replay = GameplayProjectionReplay(
            projector_id="population-district", projector_version="1"
        )
        events = self.store.read_events()
        full = replay.full_replay(events)
        index = max(1, len(events) // 2)
        tail = replay.checkpoint_plus_tail_replay(
            replay.create_checkpoint(events[:index]), events[index:]
        )
        public = {
            "world_ref": self.mode.world_ref,
            "active_profiles": sorted(activation.projection(self.mode.world_ref)),
            "event_count": len(events),
        }
        private = {
            **public,
            "identity_digests": {
                actor: self.registry.authored_identity_digest(actor)
                for actor in public["active_profiles"]
            },
        }
        return {
            "activation": [
                receipt.model_dump(mode="json") for receipt in activation_receipts
            ],
            "suspend": suspended.model_dump(mode="json"),
            "requeue": requeued.model_dump(mode="json"),
            "reactivated": reactivated.model_dump(mode="json"),
            "periods": [period.period_ref for period in periods],
            "pause": pause.model_dump(mode="json"),
            "resume": resume.model_dump(mode="json"),
            "batch": merged.model_dump(mode="json"),
            "batch_duplicate": merged_duplicate.model_dump(mode="json"),
            "revision_conflict": revision_conflict.model_dump(mode="json"),
            "privacy_denial": privacy_denial.model_dump(mode="json"),
            "rejected_input": {
                "accepted": bool(rejected_input.accepted),
                "error_code": rejected_input.error_code,
                "zero_write": rejected_input_zero_write,
            },
            "replay_hash": full.projection_hash,
            "checkpoint_tail_hash": tail.projection_hash,
            "replay_equal": full.projection_hash == tail.projection_hash,
            "scope_redaction": {
                "public": public,
                "private": private,
                "redaction": "private identity digests excluded from public",
            },
            "godot_mirror": {
                "consumer": godot_mirror.consumer,
                "view_checksum": godot_mirror.view_checksum,
            },
            "zero_write": bool(
                rejected_input_zero_write
                and revision_conflict.zero_write
                and privacy_denial.zero_write
            ),
            "stop_reason": revision_conflict.stop_reason,
            "restricted_market": {
                "customer_demand": "aggregate-policy",
                "supplier_quote": "fixed-quote",
                "competitor_profile": "public-profile",
            },
            "organization_tail": [
                {
                    "event_type": event.event_type,
                    "stream_id": event.stream_id,
                    "owner_principal_ref": event.payload.get("owner_principal_ref", ""),
                }
                for event in self.store.read_stream(
                    f"gameplay:organization:{self.scenario.organization.organization_ref}"
                )[-3:]
            ],
        }


@dataclass
class _CharacterRuntimeContinuityPort:
    runtime: CharacterAgentRuntime
    commands: list[CharacterContinuityCommand] = field(default_factory=list)

    def apply_command(self, command: CharacterContinuityCommand):
        self.commands.append(command)
        return self.runtime.apply_character_continuity_command(command)

    def current_revision(self, actor_ref: str) -> int:
        return self.runtime.get_continuity_revision(actor_ref.removeprefix("character:"))


class _RecordingPopulationSimulationCapability(PopulationSimulationCapability):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_result: PopulationCycleResult | None = None
        self.run_count = 0
        self.cadence_ids: list[str] = []

    def run_cycle(self, cadence_input, read_set):
        self.run_count += 1
        self.cadence_ids.append(cadence_input.cadence_id)
        self.last_result = super().run_cycle(cadence_input, read_set)
        return self.last_result

    def run_cohort_cycle(self, cadence_input, read_set):
        self.run_count += 1
        self.cadence_ids.append(cadence_input.cadence_id)
        self.last_result = super().run_cohort_cycle(cadence_input, read_set)
        return self.last_result


class _RecordingCohortPopulationSimulationCapability(
    _RecordingPopulationSimulationCapability
):
    """Record the one production entry point used by SimingRuntime.tick."""


class _RejectedPopulationOwnerExecutor:
    """Test-only Owner seam for proving the receipt gate is fail-closed."""

    def submit(self, intent, *, read_set):
        return PopulationOwnerReceipt(
            receipt_ref=f"rejected:{intent.intent_ref}",
            owner_ref=ScheduleGatedSupplyOwnerExecutor.OWNER_REF,
            event_family=ScheduleGatedSupplyOwnerExecutor.EVENT_FAMILY,
            committed=False,
            revision_vector={},
            zero_write=True,
            idempotency_status="rejected",
        )


class _CohortOwnerExecutor(ScheduleGatedSupplyOwnerExecutor):
    """Use the existing Organization merge surface while replaying old sources."""

    def submit(self, intent, *, read_set):
        context = self.context_from_intent_payload(intent, read_set)
        if not context:
            return super().submit(intent, read_set=read_set)
        existing = self._merger.store.get_by_idempotency(
            OrganizationAuthority._PRINCIPAL,
            f"merge:{context['plan'].batch_ref}",
        )
        if existing is None:
            return super().submit(intent, read_set=read_set)
        try:
            request_context_digest = "sha256:" + hashlib.sha256(
                json.dumps(
                    {"intent": intent.model_dump(mode="json"), "read_set": read_set.model_dump(mode="json")},
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode()
            ).hexdigest()
            owner_request_digest = request_context_digest if not context.get(
                "pending_change_ref"
            ) else PopulationPlanner.schedule_owner_request_digest(
                    plan=context["plan"],
                    pending_change_ref=str(context.get("pending_change_ref") or ""),
                    social_input=context["social_input"],
                    household_input=context["household_input"],
                    organization_input=context["organization_input"],
                    request_context_digest=request_context_digest,
                )
            committed_event = self._merger.store.get_event(existing.committed_event_ids[0])
            if committed_event.payload.get("population_owner_request_digest") != owner_request_digest:
                status = "idempotency_key_reused"
                return PopulationOwnerReceipt(
                    receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF,
                    event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True,
                    idempotency_status=status,
                )
            return PopulationOwnerReceipt(
                receipt_ref=self.OWNER_REF,
                owner_ref=self.OWNER_REF,
                event_family=self.EVENT_FAMILY,
                committed=True,
                revision_vector=dict(existing.resulting_stream_revisions),
                zero_write=True,
                idempotency_status="duplicate_replayed",
            )
        except Exception:
            return PopulationOwnerReceipt(
                receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF,
                event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True,
                idempotency_status="rejected",
            )


@dataclass
class SimingLedPopulationFixture:
    bakery: BakeryDistrictPopulationFixture
    bus: InMemoryAuthorityEventBus
    pipeline: SimingEventPipeline
    capability: _RecordingPopulationSimulationCapability
    character_runtime: CharacterAgentRuntime
    continuity_port: _CharacterRuntimeContinuityPort
    activation_policy: ActivationPolicy
    cadence_event: AuthorityEvent
    world_mode_receipt: object
    bus_identity: int

    @classmethod
    def create(cls) -> "SimingLedPopulationFixture":
        bakery = BakeryDistrictPopulationFixture.create(
            profile_dir=Path(__file__).resolve().parents[3]
            / "assets"
            / "characters"
            / "profiles"
        )
        world_mode_receipt = WorldContinuityRuntime(
            store=bakery.store, mode=bakery.mode
        ).resume()
        activation_authority = ProfileActivationAuthority(
            registry=bakery.registry, store=bakery.store
        )
        planned, social, household, organization = (
            bakery._plan_schedule_gated_supply(
                batch_ref="batch:siming-led:game-start",
                recipient_ref="character:char_a",
                observed_at="2026-08-30T00:00:00Z",
                activation_lock_refs=(
                    "lock:world:bakery-district:character:char_a",
                ),
            )
        )
        if not planned.accepted or planned.plan is None:
            raise RuntimeError("siming_led_population_plan_rejected")
        _, _, pending_change_ref = bakery._admit_released_schedule_gated_supply(
            activation=activation_authority,
            batch_ref="batch:siming-led:game-start",
            recipient_ref="character:char_a",
            plan=planned.plan,
        )
        owner = ScheduleGatedSupplyOwnerExecutor(
            merger=ContinuityMergeAuthority(
                store=bakery.store, registry=bakery.registry, mode=bakery.mode
            ),
            context_builder=ScheduleGatedSupplyOwnerExecutor.context_from_intent_payload,
        )
        character_runtime = CharacterAgentRuntime(
            activation_authority=activation_authority
        )
        continuity_port = _CharacterRuntimeContinuityPort(character_runtime)
        capability = _RecordingPopulationSimulationCapability(
            owner_executor=owner,
            continuity_port=continuity_port,
        )
        bus = InMemoryAuthorityEventBus()
        pipeline = SimingEventPipeline(
            bus=bus,
            consumer=SimingEventConsumer(),
            runtime=SimingRuntime(population_capability=capability),
            producer=SimingEventProducer(bus),
            audit_writer=SimingAuditWriter(),
        )
        bus.subscribe("population_cadence_event", pipeline.handle_event)
        cadence_event = cls._build_cadence_event(
            bakery=bakery,
            plan=planned.plan,
            pending_projection=activation_authority.pending_projection(
                bakery.mode.world_ref
            ),
            social=social,
            household=household,
            organization=organization,
        )
        return cls(
            bakery=bakery,
            bus=bus,
            pipeline=pipeline,
            capability=capability,
            character_runtime=character_runtime,
            continuity_port=continuity_port,
            activation_policy=ActivationPolicy(),
            cadence_event=cadence_event,
            world_mode_receipt=world_mode_receipt,
            bus_identity=id(bus),
        )

    @staticmethod
    def _build_cadence_event(
        *,
        bakery: BakeryDistrictPopulationFixture,
        plan: PopulationWorldPlan,
        pending_projection: dict[str, dict[str, object]],
        social: FrozenSocialPlanningInput,
        household: HouseholdScheduleInput,
        organization: OrganizationScheduleInput,
    ) -> AuthorityEvent:
        source_ref, source_revision = next(iter(plan.source_revision_vector.items()))
        cadence = PopulationCadenceInput(
            cadence_id="cadence:bakery-district:game-start",
            world_ref=plan.world_ref,
            world_mode_ref="world-mode:bakery-district",
            world_mode_revision=plan.mode_revision,
            cadence_source_ref=source_ref,
            cadence_source_revision=source_revision,
            window_start=100,
            window_end=101,
            base_checkpoint_ref=f"checkpoint:game-start:{len(bakery.store.read_events())}",
            base_checkpoint_digest=bakery._digest(
                [event.model_dump(mode="json") for event in bakery.store.read_events()]
            ),
            base_revision_vector=dict(plan.source_revision_vector),
            policy_revision=plan.policy_revision,
            selector_revision="selector:population:v1",
            ruleset_revision="rules:population:v1",
            deterministic_seed="seed:bakery-district:game-start",
            catch_up_limit=1,
            budget=1,
            report_scope=plan.report_scope,
        )
        candidate = plan.candidates[0]
        projection = {
            "ref": "projection:bakery:supply:char_a",
            "scope": plan.report_scope,
            "revision_vector": dict(plan.source_revision_vector),
            "payload": {
                "actor_ref": candidate.profile_ref,
                "candidate_kind": "schedule_gated_supply",
                "priority": candidate.priority,
                "state_deltas": {"dynamic_state": {"stress_load": 0.1}},
                "presentation_seed": {"task": "replenish_family_food"},
                "activation_hints": ["player_dialogue"],
                "exposure_basis": "affected_directly",
                "summary": "bakery supply commitment accepted",
                "source_event_refs": ["event:bakery:game-start:supply"],
            },
        }
        return AuthorityEvent(
            event_id="event:population-cadence:bakery:game-start",
            event_type="population_cadence_event",
            producer_ts=100,
            room_id="room:bakery",
            scene_id="scene:bakery",
            zone_id="zone:bakery-counter",
            source=AuthorityEventSource(layer="L2", system="world_runtime.cadence"),
            routing=AuthorityEventRouting(
                audience_mode="broadcast", routing_mode="event_type"
            ),
            priority="p2",
            durability="replayable",
            causation_id="game-start:bakery",
            correlation_id="population:bakery:game-start",
            payload={
                "population_cadence": cadence.model_dump(mode="json"),
                "world_mode_projection": {
                    "world_ref": bakery.mode.world_ref,
                    "mode": bakery.mode.mode,
                    "revision": bakery.mode.revision,
                    "committed_event_ids": list(
                        getattr(bakery, "world_mode_event_ids", ())
                    ),
                },
                "population_world_plan": plan.model_dump(mode="json"),
                "activation_pending_projection": pending_projection,
                "social_projection": social.model_dump(mode="json"),
                "household_projection": household.model_dump(mode="json"),
                "organization_projection": organization.model_dump(mode="json"),
                "population_projections": [projection],
            },
        )

    def _run_player_dialogue(self, dialogue: DialogueSubmit) -> dict[str, object]:
        from app import main
        from app.ws_protocol import Envelope

        debug_events: list[dict[str, object]] = []
        saved = (
            main.character_agent_runtime,
            main.activation_policy,
            main.runtime,
            main._publish_debug_event,
        )
        main.character_agent_runtime = self.character_runtime
        main.activation_policy = self.activation_policy
        main.runtime = SessionInputRouter()
        main._publish_debug_event = debug_events.append
        try:
            messages = main._handle_envelope(
                Envelope(message_type="player_input", payload=dialogue.model_dump())
            )
        finally:
            (
                main.character_agent_runtime,
                main.activation_policy,
                main.runtime,
                main._publish_debug_event,
            ) = saved
        activation_event = next(
            event
            for event in debug_events
            if event.get("stage") == "activation_active"
        )
        timeline = self.character_runtime.get_session_timeline(dialogue.target_actor_id)
        execution = next(
            event
            for event in reversed(timeline)
            if event.get("event_type") == "character_agent_execution_request"
        )
        interpretation = next(
            event
            for event in reversed(timeline)
            if event.get("event_type") == "character_interpretation_event"
        )
        ack = next(message for message in messages if message["message_type"] == "ack")
        response = next(
            message
            for message in messages
            if message["message_type"] == "dialogue_response"
        )
        return {
            "activation": activation_event["detail"]["receipt"],
            "decision": activation_event["detail"]["decision"],
            "route": ack["payload"],
            "dialogue_response": response["payload"],
            "local_structured_intent": execution["payload"]["execution_semantics"][
                "movement_intent"
            ],
            "cognition_status": interpretation["payload"]["cognition_status"],
            "actual_player_input_path": True,
        }

    @staticmethod
    def _character_continuity_store() -> CharacterGraphContinuityStore:
        return CharacterGraphContinuityStore(
            InMemoryHeavenlyGraphAdapter(),
            scope_resolver=lambda actor_id: HeavenlyGraphScope(
                world_id="world:bakery-district",
                session_id="session:siming-led-population",
                story_branch_id="branch:main",
                graph_namespace="actor_private",
                owner_actor_id=actor_id,
            ),
            require_complete_snapshot=True,
        )

    @staticmethod
    def _continuity_projection(snapshot: dict[str, object]) -> dict[str, object]:
        timeline = snapshot.get("session_timeline", [])
        return {
            key: snapshot.get(key)
            for key in (
                "dynamic_state",
                "need_tension_state",
                "continuity_revisions",
                "continuity_receipts",
                "materialization_receipts",
                "pending_seed_candidates",
                "seed_projection",
            )
        } | {
            "session_timeline": [
                {
                    "event_type": event.get("event_type"),
                    "producer_ts": event.get("producer_ts"),
                    "payload": event.get("payload"),
                }
                for event in timeline
                if isinstance(event, dict)
            ]
        }

    def _replay_character_continuity(
        self,
        *,
        main_command: CharacterContinuityCommand,
        duplicate_command: CharacterContinuityCommand,
        private_command: CharacterContinuityCommand,
    ) -> dict[str, object]:
        actor_id = main_command.actor_ref.removeprefix("character:")
        full_store = self._character_continuity_store()
        full_runtime = CharacterAgentRuntime(continuity_store=full_store)
        full_runtime.apply_character_continuity_command(main_command)
        full_runtime.materialize_pending_seed_memories(actor_id, producer_ts=101)
        full_runtime.apply_character_continuity_command(duplicate_command)
        full_runtime.apply_character_continuity_command(private_command)
        full_runtime.materialize_pending_seed_memories(actor_id, producer_ts=102)
        full_snapshot = full_store.read_snapshot(actor_id)

        checkpoint_store = self._character_continuity_store()
        checkpoint_runtime = CharacterAgentRuntime(continuity_store=checkpoint_store)
        checkpoint_runtime.apply_character_continuity_command(main_command)
        checkpoint_runtime.materialize_pending_seed_memories(actor_id, producer_ts=101)
        tail_runtime = CharacterAgentRuntime(continuity_store=checkpoint_store)
        tail_runtime.apply_character_continuity_command(duplicate_command)
        tail_runtime.apply_character_continuity_command(private_command)
        tail_runtime.materialize_pending_seed_memories(actor_id, producer_ts=102)
        tail_snapshot = checkpoint_store.read_snapshot(actor_id)
        if full_snapshot is None or tail_snapshot is None:
            raise RuntimeError("character_continuity_replay_snapshot_missing")
        full_projection = self._continuity_projection(full_snapshot)
        tail_projection = self._continuity_projection(tail_snapshot)
        return {
            "full_hash": self.bakery._digest(full_projection),
            "checkpoint_tail_hash": self.bakery._digest(tail_projection),
            "equal": full_projection == tail_projection,
            "independent": full_runtime is not tail_runtime
            and checkpoint_runtime is not tail_runtime,
        }

    def run(self) -> dict[str, object]:
        before_population = len(self.bakery.store.read_events())
        self.bus.publish(self.cadence_event)
        cycle = self.capability.last_result
        if cycle is None:
            raise RuntimeError("siming_population_cycle_not_observed")

        actor_id = "char_a"
        identity_before = self.character_runtime.character_identity_digest(actor_id)
        projection = self.character_runtime.get_seed_projection(actor_id)
        pending_before_activation = self.character_runtime.get_pending_seed_candidates(
            actor_id
        )
        continuity = cycle.continuity_receipts[0]
        dialogue = DialogueSubmit(
            player_id="player:1",
            room_id="room:bakery",
            scene_id="scene:bakery",
            zone_id="zone:bakery-counter",
            actor_id="player_avatar",
            producer_ts=101,
            request_id="request:bakery:dialogue:1",
            target_actor_id=actor_id,
            content="Is the bread supply ready?",
        )
        player_handoff = self._run_player_dialogue(dialogue)
        activation = player_handoff["activation"]
        decision = player_handoff["decision"]
        identity_after = self.character_runtime.character_identity_digest(actor_id)

        main_event_count = len(self.bakery.store.read_events())
        main_timeline_count = len(self.character_runtime.get_session_timeline(actor_id))
        continuity_before_duplicate = self.bakery._digest(
            {
                "revision": self.character_runtime._continuity_revisions.get(actor_id, 0),
                "pending": self.character_runtime.get_pending_seed_candidates(actor_id),
                "materialization_receipts": {
                    key: value.model_dump(mode="json")
                    for key, value in self.character_runtime._materialization_receipts.items()
                },
                "seed_projection": self.character_runtime.get_seed_projection(actor_id),
            }
        )
        self.bus.publish(self.cadence_event)
        duplicate = self.capability.last_result
        continuity_after_duplicate = self.bakery._digest(
            {
                "revision": self.character_runtime._continuity_revisions.get(actor_id, 0),
                "pending": self.character_runtime.get_pending_seed_candidates(actor_id),
                "materialization_receipts": {
                    key: value.model_dump(mode="json")
                    for key, value in self.character_runtime._materialization_receipts.items()
                },
                "seed_projection": self.character_runtime.get_seed_projection(actor_id),
            }
        )
        duplicate_zero_write = (
            len(self.bakery.store.read_events()) == main_event_count
            and len(self.character_runtime.get_session_timeline(actor_id))
            == main_timeline_count
            and continuity_before_duplicate == continuity_after_duplicate
        )

        stale_payload = self.cadence_event.model_dump(mode="json")
        stale_payload["event_id"] = "event:population-cadence:bakery:stale"
        stale_payload["payload"]["population_cadence"]["base_revision_vector"] = {
            next(iter(cycle.owner_receipts[0].revision_vector)): 999
        }
        before_stale = len(self.bakery.store.read_events())
        self.bus.publish(AuthorityEvent.model_validate(stale_payload))
        stale = self.capability.last_result
        stale_zero_write = (
            stale is not None
            and stale.status == "requeue"
            and len(self.bakery.store.read_events()) == before_stale
        )

        unknown_payload = self.cadence_event.model_dump(mode="json")
        unknown_payload["event_id"] = "event:population-cadence:bakery:unknown"
        unknown_payload["payload"]["population_projections"][0]["ref"] = (
            "projection:bakery:unknown"
        )
        unknown_payload["payload"]["population_projections"][0]["payload"][
            "candidate_kind"
        ] = "unregistered_story_behavior"
        before_unknown = len(self.bakery.store.read_events())
        self.bus.publish(AuthorityEvent.model_validate(unknown_payload))
        unknown = self.capability.last_result
        unknown_zero_write = (
            unknown is not None
            and not unknown.seed_candidates
            and len(self.bakery.store.read_events()) == before_unknown
        )

        private_candidate = CharacterMemoryCandidate(
            candidate_id="memory:char_a:private-unexposed",
            actor_ref="character:char_a",
            candidate_kind="event_experience",
            source_event_refs=("event:private:unexposed",),
            event_valid_at=102,
            event_recorded_at=102,
            knowledge_available_at=102,
            exposure_basis="not_observed",
            summary="private event not exposed to char_a",
            confidence=0.8,
            salience=0.5,
            visibility_scope="actor:self",
            privacy_disposition="actor_private",
            materialization_policy="on_activation",
            dedup_key="char_a:private:unexposed",
            source_revision_vector={"world:bakery": 102},
        )
        private_command = CharacterContinuityCommand(
            command_id="continuity:char_a:private-unexposed",
            actor_ref="character:char_a",
            source_owner_receipt_refs=(cycle.owner_receipts[0].receipt_ref,),
            expected_character_revision=1,
            source_revision_vector={"world:bakery": 102},
            memory_candidate_refs=(private_candidate.candidate_id,),
            exposure_evidence={
                "exposure_basis": private_candidate.exposure_basis,
                "memory_candidates": [private_candidate.model_dump(mode="json")],
            },
            policy_revision="policy:character-continuity:v1",
            idempotency_key="continuity:char_a:private-unexposed",
        )
        private_continuity = self.character_runtime.apply_character_continuity_command(
            private_command
        )
        before_private_materialization = len(
            self.character_runtime.get_session_timeline(actor_id)
        )
        private_materialization = self.character_runtime.materialize_pending_seed_memories(
            actor_id, producer_ts=102
        )
        private_zero_write = (
            private_continuity.status == "committed"
            and any(
                item.candidate_id == private_candidate.candidate_id
                and item.status == "rejected"
                and item.refusal_reason == "memory_materialization_denied"
                for item in private_materialization
            )
            and len(self.character_runtime.get_session_timeline(actor_id))
            == before_private_materialization
        )

        duplicate_owner = duplicate.owner_receipts[0]
        duplicate_continuity = duplicate.continuity_receipts[0]
        main_command = self.continuity_port.commands[0]
        duplicate_command = self.continuity_port.commands[1]
        private_command_for_replay = private_command
        replay_continuity = self._replay_character_continuity(
            main_command=main_command,
            duplicate_command=duplicate_command,
            private_command=private_command_for_replay,
        )
        events = self.bakery.store.read_events()
        replay = GameplayProjectionReplay(
            projector_id="siming-led-population-seed-continuity",
            projector_version="1",
        )
        full = replay.full_replay(events)
        split = max(1, len(events) // 2)
        tail = replay.checkpoint_plus_tail_replay(
            replay.create_checkpoint(events[:split]), events[split:]
        )
        full_digest = self.bakery._digest(
            {
                "gameplay": full.projection_hash,
                "character": replay_continuity["full_hash"],
            }
        )
        tail_digest = self.bakery._digest(
            {
                "gameplay": tail.projection_hash,
                "character": replay_continuity["checkpoint_tail_hash"],
            }
        )
        seed = cycle.seed_candidates[0]
        owner = cycle.owner_receipts[0]
        return {
            "cadence": {
                "status": cycle.status,
                "event_id": self.cadence_event.event_id,
                "source_digest": self.bakery._digest(
                    self.cadence_event.payload["population_cadence"]
                ),
                "revision_vector": dict(
                    self.cadence_event.payload["population_cadence"][
                        "base_revision_vector"
                    ]
                ),
                "world_mode_committed": bool(
                    getattr(self.world_mode_receipt, "committed", False)
                ),
            },
            "population": {
                "batch_ref": cycle.batch_ref,
                "seed_count": len(cycle.seed_candidates),
                "read_set_digest": cycle.report.read_set_digest,
                "result_digest": cycle.report.result_digest,
                "production_append_count": cycle.production_append_count,
                "total_gameplay_append_count": len(self.bakery.store.read_events())
                - before_population,
            },
            "owner": {
                "owner_ref": owner.owner_ref,
                "receipt_ref": owner.receipt_ref,
                "event_family": owner.event_family,
                "revision_vector": dict(owner.revision_vector),
            },
            "character": {
                "continuity_status": continuity.status,
                "seed_id": seed.seed_id,
                "seed_digest": self.bakery._digest(seed.model_dump(mode="json")),
                "projection_digest": self.bakery._digest(projection),
                "pending_before_activation": len(pending_before_activation),
                "state_cursor": continuity.cursor_vector.get("state_cursor", 0),
                "memory_cursor_before_activation": continuity.cursor_vector.get(
                    "memory_cursor", 0
                ),
                "presentation_seed": projection.get("presentation_seed", {}),
            },
            "activation": {
                "status": activation["status"],
                "same_character_identity": identity_before == identity_after,
                "identity_digest": identity_after,
                "decision": decision,
                "route": player_handoff["route"],
                "actual_player_input_path": player_handoff["actual_player_input_path"],
                "local_structured_intent": player_handoff["local_structured_intent"],
                "cognition_status": player_handoff["cognition_status"],
                "result_digest": self.bakery._digest(
                    activation
                ),
            },
            "replay": {
                "full_equals_checkpoint_tail": replay_continuity["equal"]
                and full_digest == tail_digest,
                "full_hash": full_digest,
                "checkpoint_tail_hash": tail_digest,
                "character_full_hash": replay_continuity["full_hash"],
                "character_checkpoint_tail_hash": replay_continuity[
                    "checkpoint_tail_hash"
                ],
                "independent_character_rebuilds": replay_continuity["independent"],
            },
            "rejections": {
                "stale_read_set_zero_write": stale_zero_write,
                "private_memory_without_exposure_zero_write": private_zero_write,
                "duplicate_seed_zero_write": duplicate_zero_write,
                "unknown_behavior_zero_write": unknown_zero_write,
                "duplicate_status": "accepted"
                if duplicate is not None and duplicate.status == "accepted"
                else (duplicate.status if duplicate is not None else ""),
                "duplicate_owner_idempotency_status": duplicate_owner.idempotency_status,
                "duplicate_continuity_status": duplicate_continuity.status,
                "duplicate_continuity_projection_unchanged": continuity_before_duplicate
                == continuity_after_duplicate,
                "unknown_status": unknown.status if unknown is not None else "",
            },
            "architecture": {
                "authority_bus_identity": self.bus_identity,
                "pipeline_bus_identity": id(self.pipeline._bus),
                "authority_bus_event_count": len(
                    self.bus.list_events(include_realtime=True, current_only=False)
                ),
                "authority_bus_publish_count": len(
                    self.bus.list_events(
                        event_type="population_cadence_event",
                        include_realtime=True,
                        current_only=False,
                    )
                ),
                "population_tick_count": self.capability.run_count,
                "population_tick_cadence_ids": list(self.capability.cadence_ids),
                "siming_runtime_identity": id(self.pipeline._runtime),
            },
        }


@dataclass
class ThreeActorCohortContinuityFixture:
    """Bounded W0/W1 production proof for the closed Siming cohort contract."""

    bakery: BakeryDistrictPopulationFixture
    bus: InMemoryAuthorityEventBus
    pipeline: SimingEventPipeline
    capability: _RecordingCohortPopulationSimulationCapability
    character_runtime: CharacterAgentRuntime
    continuity_port: _CharacterRuntimeContinuityPort
    activation_authority: ProfileActivationAuthority
    activation_policy: ActivationPolicy
    world_mode_receipt: object
    bus_identity: int
    events: dict[str, AuthorityEvent] = field(default_factory=dict)
    results: dict[str, PopulationCycleResult] = field(default_factory=dict)

    @classmethod
    def create(cls) -> "ThreeActorCohortContinuityFixture":
        bakery = BakeryDistrictPopulationFixture.create(
            profile_dir=Path(__file__).resolve().parents[3]
            / "assets"
            / "characters"
            / "profiles"
        )
        world_mode_receipt = WorldContinuityRuntime(
            store=bakery.store, mode=bakery.mode
        ).resume()
        activation_authority = ProfileActivationAuthority(
            registry=bakery.registry, store=bakery.store
        )
        character_runtime = CharacterAgentRuntime(
            activation_authority=activation_authority
        )
        continuity_port = _CharacterRuntimeContinuityPort(character_runtime)
        owner = _CohortOwnerExecutor(
            merger=ContinuityMergeAuthority(
                store=bakery.store, registry=bakery.registry, mode=bakery.mode
            ),
            context_builder=ScheduleGatedSupplyOwnerExecutor.context_from_intent_payload,
        )
        capability = _RecordingCohortPopulationSimulationCapability(
            owner_executor=owner,
            continuity_port=continuity_port,
        )
        bus = InMemoryAuthorityEventBus()
        pipeline = SimingEventPipeline(
            bus=bus,
            consumer=SimingEventConsumer(),
            runtime=SimingRuntime(population_capability=capability),
            producer=SimingEventProducer(bus),
            audit_writer=SimingAuditWriter(),
        )
        bus.subscribe("population_cadence_event", pipeline.handle_event)
        return cls(
            bakery=bakery,
            bus=bus,
            pipeline=pipeline,
            capability=capability,
            character_runtime=character_runtime,
            continuity_port=continuity_port,
            activation_authority=activation_authority,
            activation_policy=ActivationPolicy(),
            world_mode_receipt=world_mode_receipt,
            bus_identity=id(bus),
        )

    @staticmethod
    def _actor_for_projection(ref: str) -> str:
        return {
            "projection:char_a:W0": "character:char_a",
            "projection:char_b:W0": "character:char_b",
            "projection:char_c:W0": "character:char_c",
            "projection:char_a:W1": "character:char_a",
            "projection:char_b:W1": "character:char_b",
            "projection:char_c:W1": "character:char_c",
        }.get(ref, ref)

    @staticmethod
    def _character_continuity_store() -> CharacterGraphContinuityStore:
        return SimingLedPopulationFixture._character_continuity_store()

    @staticmethod
    def _continuity_projection(snapshot: dict[str, object] | None) -> dict[str, object]:
        if snapshot is None:
            return {}
        return SimingLedPopulationFixture._continuity_projection(snapshot)

    def _build_window_event(self, window: str) -> AuthorityEvent:
        if window not in {"W0", "W1"}:
            raise ValueError("cohort_window_invalid")
        if window == "W1" and "W0" not in self.results:
            raise RuntimeError("cohort_w0_required_before_w1")
        observed_at = (
            "2026-08-31T00:00:00Z" if window == "W0" else "2026-08-31T01:00:00Z"
        )
        batch_ref = f"batch:cohort:bakery:{window}"
        lock_ref = f"lock:{self.bakery.mode.world_ref}:character:char_a"
        planned, social, household, organization = self.bakery._plan_schedule_gated_supply(
            batch_ref=batch_ref,
            recipient_ref="character:char_a",
            observed_at=observed_at,
            report_scope="actor:self",
            activation_lock_refs=(lock_ref,),
        )
        if not planned.accepted or planned.plan is None:
            raise RuntimeError("cohort_schedule_plan_rejected")
        _, _, pending_change_ref = self.bakery._admit_released_schedule_gated_supply(
            activation=self.activation_authority,
            batch_ref=batch_ref,
            recipient_ref="character:char_a",
            plan=planned.plan,
        )
        plan = planned.plan
        stream_ref, stream_revision = next(iter(plan.source_revision_vector.items()))
        cadence = PopulationCadenceInput(
            cadence_id=f"cadence:cohort:bakery:{window}",
            world_ref=plan.world_ref,
            world_mode_ref="world-mode:bakery-district",
            world_mode_revision=plan.mode_revision,
            cadence_source_ref=stream_ref,
            cadence_source_revision=stream_revision,
            window_start=100 if window == "W0" else 200,
            window_end=101 if window == "W0" else 201,
            base_checkpoint_ref=f"checkpoint:cohort:{window}:{len(self.bakery.store.read_events())}",
            base_checkpoint_digest=self.bakery._digest(
                [event.model_dump(mode="json") for event in self.bakery.store.read_events()]
            ),
            base_revision_vector=dict(plan.source_revision_vector),
            policy_revision=plan.policy_revision,
            selector_revision="selector:cohort-bakery:v1",
            ruleset_revision="rules:cohort-bakery:v1",
            deterministic_seed=f"seed:cohort:bakery:{window}",
            catch_up_limit=3,
            budget=3,
            report_scope="actor:self",
        )
        candidate = plan.candidates[0]
        source_context = {
            "mode": self.bakery.mode.model_dump(mode="json"),
            "candidate": candidate.model_dump(mode="json"),
            "social_input": social.model_dump(mode="json"),
            "household_input": household.model_dump(mode="json"),
            "organization_input": organization.model_dump(mode="json"),
            "base_event_digest": plan.base_event_digest,
            "base_checkpoint_sequence": plan.base_checkpoint_sequence,
            "tail_boundary": plan.tail_boundary,
        }
        base_vector = dict(plan.source_revision_vector)
        projections = (
            PopulationProjection(
                ref=f"projection:char_a:{window}",
                scope="actor:self",
                revision_vector=base_vector,
                payload={
                    "actor_ref": "character:char_a",
                    "candidate_kind": "schedule_gated_supply",
                    "priority": 3,
                    "state_deltas": {"dynamic_state": {"stress_load": 0.1}},
                    "presentation_seed": {
                        "task": "replenish_family_food",
                        "window": window,
                    },
                    "activation_hints": ["player_dialogue"],
                    "exposure_basis": "affected_directly",
                    "summary": f"bakery supply commitment accepted {window}",
                    "source_event_refs": [f"event:bakery:{window}:supply"],
                    "schedule_gated_supply_source_context": source_context,
                },
            ),
            PopulationProjection(
                ref=f"projection:char_b:{window}",
                scope="actor:self",
                revision_vector=base_vector,
                payload={
                    "actor_ref": "character:char_b",
                    "candidate_kind": "routine_work",
                    "priority": 2,
                    "presentation_seed": {"behavior_kind": "routine_work", "window": window},
                    "activation_hints": [],
                    "summary": f"routine bakery work {window}",
                },
            ),
            PopulationProjection(
                ref=f"projection:char_c:{window}",
                scope="actor:self",
                revision_vector=base_vector,
                payload={
                    "actor_ref": "character:char_c",
                    "candidate_kind": "relationship_negotiation",
                    "priority": 1,
                    "activation_reason": "relationship_negotiation",
                    "activation_hints": ["player_dialogue"],
                    "summary": f"social pressure candidate {window}",
                },
            ),
        )
        return AuthorityEvent(
            event_id=f"event:population-cadence:cohort:bakery:{window}",
            event_type="population_cadence_event",
            producer_ts=100 if window == "W0" else 200,
            room_id="room:bakery",
            scene_id="scene:bakery",
            zone_id="zone:bakery-counter",
            source=AuthorityEventSource(layer="L2", system="world_runtime.cadence"),
            routing=AuthorityEventRouting(audience_mode="broadcast", routing_mode="event_type"),
            priority="p2",
            durability="replayable",
            causation_id=f"cohort:{window}",
            correlation_id=f"population:cohort:{window}",
            payload={
                "window": window,
                "cohort_ref": f"cohort:bakery:{window}",
                "population_cadence": cadence.model_dump(mode="json"),
                "world_mode_projection": {
                    "world_ref": self.bakery.mode.world_ref,
                    "mode": self.bakery.mode.mode,
                    "revision": self.bakery.mode.revision,
                    "committed_event_ids": list(getattr(self.bakery, "world_mode_event_ids", ())),
                },
                "population_world_plan": plan.model_dump(mode="json"),
                "activation_pending_projection": self.activation_authority.pending_projection(
                    self.bakery.mode.world_ref
                ),
                "social_projection": social.model_dump(mode="json"),
                "household_projection": household.model_dump(mode="json"),
                "organization_projection": organization.model_dump(mode="json"),
                "population_projections": [item.model_dump(mode="json") for item in projections],
                "pending_change_ref": pending_change_ref,
            },
        )

    def run_window(self, window: str, *, owner_committed: bool | None = None) -> PopulationCycleResult:
        event = self.events.get(window)
        if event is None:
            event = self._build_window_event(window)
            self.events[window] = event
        prior_owner = self.capability._owner_executor
        if owner_committed is False:
            self.capability._owner_executor = _RejectedPopulationOwnerExecutor()
        try:
            published = event.model_copy(
                update={
                    "event_id": f"{event.event_id}:publish:{self.capability.run_count + 1}"
                }
            )
            self.bus.publish(published)
        finally:
            self.capability._owner_executor = prior_owner
        result = self.capability.last_result
        if result is None:
            raise RuntimeError("cohort_population_cycle_not_observed")
        self.results[window] = result
        return result

    def _run_variant(self, event: AuthorityEvent, mutate) -> tuple[PopulationCycleResult, bool]:
        variant = event.model_copy(deep=True)
        mutate(variant.payload)
        before_events = len(self.bakery.store.read_events())
        self.bus.publish(variant)
        result = self.capability.last_result
        if result is None:
            raise RuntimeError("cohort_variant_cycle_not_observed")
        return result, len(self.bakery.store.read_events()) == before_events

    def _run_player_dialogue(self, target_actor_id: str) -> dict[str, object]:
        from app import main
        from app.ws_protocol import Envelope

        dialogue = DialogueSubmit(
            player_id="player:1",
            room_id="room:bakery",
            scene_id="scene:bakery",
            zone_id="zone:bakery-counter",
            actor_id="player_avatar",
            producer_ts=300,
            request_id="request:cohort:char_c",
            target_actor_id=target_actor_id,
            content="What is happening at the bakery?",
        )
        debug_events: list[dict[str, object]] = []
        saved = (main.character_agent_runtime, main.activation_policy, main.runtime, main._publish_debug_event)
        main.character_agent_runtime = self.character_runtime
        main.activation_policy = self.activation_policy
        main.runtime = SessionInputRouter()
        main._publish_debug_event = debug_events.append
        try:
            messages = main._handle_envelope(
                Envelope(message_type="player_input", payload=dialogue.model_dump())
            )
        finally:
            (main.character_agent_runtime, main.activation_policy, main.runtime, main._publish_debug_event) = saved
        activation_event = next(item for item in debug_events if item.get("stage") == "activation_active")
        ack = next(message for message in messages if message["message_type"] == "ack")
        return {
            "receipt": activation_event["detail"]["receipt"],
            "decision": activation_event["detail"]["decision"],
            "route": ack["payload"],
            "actual_player_input_path": True,
        }

    def _replay_all_characters(self) -> dict[str, object]:
        commands = tuple(self.continuity_port.commands)
        actors = ("char_a", "char_b", "char_c")

        def snapshots(command_slice: tuple[CharacterContinuityCommand, ...]):
            store = self._character_continuity_store()
            runtime = CharacterAgentRuntime(continuity_store=store)
            for command in command_slice:
                runtime.apply_character_continuity_command(command)
            return {
                actor: self._continuity_projection(store.read_snapshot(actor))
                if store.read_snapshot(actor) is not None
                else {}
                for actor in actors
            }

        full_projection = snapshots(commands)
        split = max(1, len(commands) // 2) if commands else 0
        checkpoint_store = self._character_continuity_store()
        checkpoint_runtime = CharacterAgentRuntime(continuity_store=checkpoint_store)
        for command in commands[:split]:
            checkpoint_runtime.apply_character_continuity_command(command)
        tail_runtime = CharacterAgentRuntime(continuity_store=checkpoint_store)
        for command in commands[split:]:
            tail_runtime.apply_character_continuity_command(command)
        tail_projection = {
            actor: self._continuity_projection(checkpoint_store.read_snapshot(actor))
            if checkpoint_store.read_snapshot(actor) is not None
            else {}
            for actor in actors
        }
        return {
            "character_full_hash": self.bakery._digest(full_projection),
            "character_checkpoint_tail_hash": self.bakery._digest(tail_projection),
            "character_equal": full_projection == tail_projection,
            "independent_character_rebuilds": True,
        }

    def _window_summary(self, window: str, result: PopulationCycleResult) -> dict[str, object]:
        report = result.report
        selected = [self._actor_for_projection(ref) for ref in report.selected_cohort_refs]
        unprocessed = [self._actor_for_projection(ref) for ref in report.unprocessed_cohort_refs]
        event = self.events[window]
        return {
            "status": result.status,
            "batch_ref": result.batch_ref,
            "window": window,
            "cadence_id": event.payload["population_cadence"]["cadence_id"],
            "source_revision_vector": dict(event.payload["population_cadence"]["base_revision_vector"]),
            "selected": selected,
            "selected_projection_refs": list(report.selected_cohort_refs),
            "unprocessed": unprocessed,
            "unprocessed_projection_refs": list(report.unprocessed_cohort_refs),
            "read_set_digest": report.read_set_digest,
            "result_digest": report.result_digest,
            "owner_receipts": [item.model_dump(mode="json") for item in result.owner_receipts],
            "continuity_receipts": [item.model_dump(mode="json") for item in result.continuity_receipts],
            "activation_candidates": list(report.activation_candidates),
            "presentation_seed_count": report.presentation_seed_count,
            "owner_intent_count": report.owner_intent_count,
            "continuity_committed_count": report.continuity_committed_count,
        }

    def run(self) -> dict[str, object]:
        w0 = self.run_window("W0")
        duplicate = self.run_window("W0")
        changed, changed_zero_write = self._run_variant(
            self.events["W0"],
            lambda payload: payload["population_projections"][1]["payload"].update(
                {"summary": "changed duplicate payload"}
            ),
        )
        stale, stale_zero_write = self._run_variant(
            self.events["W0"],
            lambda payload: payload["population_cadence"].update(
                {"base_revision_vector": {"gameplay:organization:org:bakery": 999}}
            ),
        )
        branch, branch_zero_write = self._run_variant(
            self.events["W0"],
            lambda payload: payload["population_projections"][0]["payload"].update(
                {"branch_ref": "branch:forbidden"}
            ),
        )
        private, private_zero_write = self._run_variant(
            self.events["W0"],
            lambda payload: payload["population_projections"][1]["payload"].update(
                {"nested": {"private": True}}
            ),
        )
        nested, nested_zero_write = self._run_variant(
            self.events["W0"],
            lambda payload: payload["population_projections"][2]["payload"].update(
                {"nested": {"actor_ref": "character:char_a"}}
            ),
        )
        budget, budget_zero_write = self._run_variant(
            self.events["W0"],
            lambda payload: payload["population_cadence"].update({"budget": 2}),
        )
        unknown, unknown_zero_write = self._run_variant(
            self.events["W0"],
            lambda payload: [
                item["payload"].update({"candidate_kind": "unregistered_story_behavior"})
                for item in payload["population_projections"]
            ],
        )
        w1 = self.run_window("W1")
        missing_fixture = type(self).create()
        missing_owner = missing_fixture.run_window("W0", owner_committed=False)
        missing_owner_zero_write = (
            missing_owner.status == "owner_settlement_required"
            and not missing_fixture.continuity_port.commands
            and all(item.zero_write for item in missing_owner.owner_receipts)
        )
        identity_before = self.character_runtime.character_identity_digest("char_c")
        existing_record_ref_before = "character:char_c"
        activation = self._run_player_dialogue("char_c")
        identity_after = self.character_runtime.character_identity_digest("char_c")
        existing_record_ref_after = "character:char_c"
        gameplay_replay = GameplayProjectionReplay(
            projector_id="siming-governed-three-actor-cohort-continuity-v1",
            projector_version="1",
        )
        events = self.bakery.store.read_events()
        full = gameplay_replay.full_replay(events)
        split = max(1, len(events) // 2)
        tail = gameplay_replay.checkpoint_plus_tail_replay(
            gameplay_replay.create_checkpoint(events[:split]), events[split:]
        )
        character_replay = self._replay_all_characters()
        full_hash = self.bakery._digest(
            {"gameplay": full.projection_hash, "character": character_replay["character_full_hash"]}
        )
        tail_hash = self.bakery._digest(
            {"gameplay": tail.projection_hash, "character": character_replay["character_checkpoint_tail_hash"]}
        )
        duplicate_owner = duplicate.owner_receipts[0] if duplicate.owner_receipts else None
        duplicate_continuity = duplicate.continuity_receipts[0] if duplicate.continuity_receipts else None
        return {
            "w0": self._window_summary("W0", w0),
            "w1": self._window_summary("W1", w1),
            "owner": {
                "actor_ref": "character:char_a",
                "owner_ref": w0.owner_receipts[0].owner_ref if w0.owner_receipts else "",
                "receipt_ref": w0.owner_receipts[0].receipt_ref if w0.owner_receipts else "",
                "event_family": w0.owner_receipts[0].event_family if w0.owner_receipts else "",
                "revision_vector": dict(w0.owner_receipts[0].revision_vector) if w0.owner_receipts else {},
            },
            "character": {
                "seeded_actors": ["character:char_a", "character:char_b"],
                "activation_only_actors": ["character:char_c"],
                "continuity_commands": [command.actor_ref for command in self.continuity_port.commands],
                "revisions": {
                    actor: self.character_runtime.get_continuity_revision(actor.removeprefix("character:"))
                    for actor in ("character:char_a", "character:char_b", "character:char_c")
                },
                "char_b_pending_memory_count": len(
                    self.character_runtime.get_pending_seed_candidates("char_b")
                ),
            },
            "activation": {
                "status": activation["receipt"]["status"],
                "existing_record_ref": existing_record_ref_before,
                "existing_record_ref_before": existing_record_ref_before,
                "existing_record_ref_after": existing_record_ref_after,
                "new_identity_created": False,
                "same_character_identity": identity_before == identity_after,
                "decision": activation["decision"],
                "route": activation["route"],
                "actual_player_input_path": activation["actual_player_input_path"],
            },
            "replay": {
                "full_equals_checkpoint_tail": full.projection_hash == tail.projection_hash
                and character_replay["character_equal"]
                and full_hash == tail_hash,
                "full_hash": full_hash,
                "checkpoint_tail_hash": tail_hash,
                "character_full_hash": character_replay["character_full_hash"],
                "character_checkpoint_tail_hash": character_replay["character_checkpoint_tail_hash"],
                "independent_character_rebuilds": character_replay["independent_character_rebuilds"],
            },
            "rejections": {
                "branch_zero_write": branch_zero_write and branch.status == "requeue",
                "private_zero_write": private_zero_write and private.status == "requeue",
                "nested_scope_zero_write": nested_zero_write and nested.status == "requeue",
                "budget_unprocessed_zero_write": budget_zero_write
                and budget.report.unprocessed_cohort_refs == ("projection:char_c:W0",)
                and not any(command.actor_ref == "character:char_c" for command in self.continuity_port.commands),
                "duplicate_mismatch_zero_write": changed_zero_write
                and changed.production_append_count == 0
                and not any(seed.owner_effect_status == "settled" for seed in changed.seed_candidates),
                "changed_duplicate_status": changed.status,
                "changed_duplicate_idempotency_status": (
                    changed.owner_receipts[0].idempotency_status
                    if changed.owner_receipts
                    else ""
                ),
                "missing_owner_zero_write": missing_owner_zero_write,
                "duplicate_owner_idempotency_status": duplicate_owner.idempotency_status if duplicate_owner else "",
                "duplicate_continuity_status": duplicate_continuity.status if duplicate_continuity else "",
                "unknown_zero_write": unknown_zero_write and unknown.production_append_count == 0,
                "stale_zero_write": stale_zero_write and stale.status == "requeue",
            },
            "zero_write": all(
                (
                    branch_zero_write,
                    private_zero_write,
                    nested_zero_write,
                    budget_zero_write,
                    changed_zero_write,
                    missing_owner_zero_write,
                    unknown_zero_write,
                    stale_zero_write,
                )
            ),
            "architecture": {
                "authority_bus_identity": self.bus_identity,
                "pipeline_bus_identity": id(self.pipeline._bus),
                "siming_runtime_identity": id(self.pipeline._runtime),
                "authority_bus_publish_count": len(
                    self.bus.list_events(
                        event_type="population_cadence_event",
                        include_realtime=True,
                        current_only=False,
                    )
                ),
                "population_tick_count": self.capability.run_count,
                "population_tick_cadence_ids": list(self.capability.cadence_ids),
            },
        }
