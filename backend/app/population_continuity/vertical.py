from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.bakery_mirror_source import BakeryMirrorSource
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.replay import GameplayProjectionReplay

from .activation import ProfileActivationAuthority
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
        merged_duplicate = merger.merge_world_plan(
            scheduled.plan.model_copy(
                update={"activation_lock_refs": (), "activation_locks": ()},
                deep=True,
            )
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
