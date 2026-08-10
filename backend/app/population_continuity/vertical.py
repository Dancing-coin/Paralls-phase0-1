from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.bakery_mirror_source import BakeryMirrorSource
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay

from .activation import ProfileActivationAuthority
from .batch import ContinuityMergeAuthority, PopulationPlanner
from .models import ActivationProposal, BatchIntentCandidate, WorldModeProfile
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
        candidates = tuple(
            BatchIntentCandidate(
                intent_ref=f"intent:district:{kind}",
                profile_ref=actor,
                intent_kind=kind,
                payload={
                    "stream_ref": f"population:{actor}",
                    "event_type": f"population.intent.{kind}",
                    "district_ref": "world:bakery-district",
                },
                priority=2 if kind == "work" else 1,
                claim_refs=(f"claim:{kind}",),
                expected_revisions={f"population:{actor}": 0},
                policy_revision=self.mode.revision,
                package_revision="package:bakery-authored-agents:v1",
                idempotency_key=f"intent:district:{kind}",
                correlation_id="correlation:district",
                source_ref="population:district-planner",
                privacy_scope="actor:self",
            )
            for actor, kind in (
                ("character:char_b", "work"),
                ("character:char_c", "supply"),
                ("character:char_a", "inspection"),
                ("character:char_a", "work"),
            )
        )
        candidates = tuple(
            item.model_copy(
                update={
                    "claim_refs": ("claim:work",)
                    if item.intent_kind == "work"
                    else item.claim_refs,
                    "intent_ref": item.intent_ref
                    + (
                        ":contention"
                        if item.intent_kind == "work"
                        and item.profile_ref == "character:char_a"
                        else ""
                    ),
                    "idempotency_key": item.idempotency_key
                    + (
                        ":contention"
                        if item.intent_kind == "work"
                        and item.profile_ref == "character:char_a"
                        else ""
                    ),
                }
            )
            for item in candidates
        )
        plan = PopulationPlanner().plan(
            batch_ref="batch:district:1",
            world_ref=self.mode.world_ref,
            mode=self.mode,
            candidates=candidates,
            input_digest="sha256:district-input",
            deterministic_seed="seed:district:1",
        )
        merged = ContinuityMergeAuthority(
            store=self.store, registry=self.registry, mode=self.mode
        ).merge(plan)
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
            "zero_write": all(
                receipt.zero_write is False for receipt in activation_receipts
            )
            and merged.zero_write is False,
            "stop_reason": None,
            "restricted_market": {
                "customer_demand": "aggregate-policy",
                "supplier_quote": "fixed-quote",
                "competitor_profile": "public-profile",
            },
        }
