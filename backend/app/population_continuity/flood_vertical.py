"""固定洪灾样板装配：使用原 World、Siming、Owner 和 Core。"""
from pathlib import Path
from tempfile import TemporaryDirectory

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.character_agent.models.simulation_seed import CharacterContinuityCommand
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.services.character_continuity import CharacterRuntimeContinuityPort
from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from app.gameplay.production_package_registry import build_production_social_policy_registry
from app.models.siming_event import SimingInput
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_population_capability import PopulationSimulationCapability
from app.services.siming_runtime import SimingRuntime

from .activation import ProfileActivationAuthority
from .activation_policy import resolve_participation
from .batch import ContinuityMergeAuthority
from .character_modules import evaluate_modules, farmer_module_definitions
from .flood_scenario import FLOOD_ACTORS, flood_module_states, flood_participation_policies
from .member_ledger import MemberEntry, PopulationMemberLedger, partition_members, register_population_member_ledger_schemas
from .models import BatchIntentCandidate, WorldModeProfile
from .owner_adapters import ScheduleGatedSupplyOwnerExecutor
from .roster import PopulationRoster
from .runtime_publication import RuntimeCadencePublisher
from .simulation_contracts import simulation_digest
from .simulation_frame import build_simulation_frame
from .siming_contracts import PopulationProjection, PopulationReadSet
from .social_input import FrozenSocialPlanningInput
from .source_inputs import HouseholdScheduleInput, OrganizationScheduleInput
from .world import WorldContinuityRuntime


class _ObservedCapability(PopulationSimulationCapability):
    def run_default_decision_cycle(self, cadence_input, read_set):
        result = super().run_default_decision_cycle(cadence_input, read_set)
        self.last_result = result
        return result


class FloodPopulationFixture:
    actors = FLOOD_ACTORS
    cohort_ref = "cohort:flood:20260918"

    @classmethod
    def create(cls, *, storage_root=None):
        value = cls()
        value._temporary = TemporaryDirectory(prefix="paralls-flood-") if storage_root is None else None
        value.storage_root = Path(storage_root or value._temporary.name)
        value.storage_root.mkdir(parents=True, exist_ok=True)
        value.registry = CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[3] / "assets/characters/profiles")
        value.schemas = EventSchemaRegistry()
        register_population_member_ledger_schemas(value.schemas)
        for event_type in ("population.world.resume", "population.cadence.admitted",
                "population.activation.locked", "population.activation.released", "population.activation.requeued",
                "gameplay.organization.membership_recorded", "gameplay.organization.role_term_recorded",
                "gameplay.organization.shift_offer_recorded", "gameplay.organization.work_order_recorded",
                "gameplay.organization.commerce_commitment_accepted"):
            value.schemas.register(EventSchemaRegistration(event_type, 1, f"schema:{event_type}:1"))
        value.mode = WorldModeProfile(world_ref="world:default", mode="simulation", revision="1",
            cadence_class="population", batch_limit=3, wake_budget=3, catch_up_limit=3, degraded_threshold=3)
        value.roster = PopulationRoster(actor_ids=tuple(actor.removeprefix("character:") for actor in value.actors))
        value.resolutions = {actor: resolve_participation(policies=flood_participation_policies(
            actor_ref=actor, scenario_revision="flood:v1"), tick=0) for actor in value.actors}
        value.intersections, value.events = [], {}
        value.module_proposals = {}
        value.current_situation = "flood:v1"
        value.siming_tick_count = 0
        value._open()
        members = tuple(MemberEntry(actor_ref=actor, entry_character_revision=0,
            participation_policy_pins=value.resolutions[actor].source_policy_pins,
            aggregatable_field_refs=("needs.fatigue", "needs.need_pressure") if actor == value.actors[1] else (),
            protected_field_refs=value.resolutions[actor].forbidden_dimensions,
            protected_code_refs=()) for actor in value.actors)
        ledger = partition_members(PopulationMemberLedger(cohort_ref=value.cohort_ref,
            member_source_ref="roster:flood@1", member_source_revision="1", situation_revision="flood:v1",
            ruleset_revision="rules:farmer@1", partition_revision="partition:flood@1", seed="flood:20260918",
            member_entries=members), seed="flood:20260918", partition_revision="partition:flood@1")
        assert value.world.register_member_ledger(ledger, continuity_runtime=value.character_runtime,
            idempotency_key="register:flood").committed
        value.world.configure_character_participation(resolutions=value.resolutions,
            activation_authority=value.activation_authority, cohort_ref=value.cohort_ref)
        assert value.world.resume().committed
        value.schedule = OrganizationAuthority(store=value.store).record_schedule(command_id="flood:schedule",
            organization_ref="org:flood-supply", recipient_ref=value.actors[0], membership_ref="membership:flood:char_a",
            assignment_ref="assignment:flood:char_a", role="farmer", shift_ref="shift:flood:char_a",
            operating_window_ref="window:flood", work_order_ref="work:flood-supply",
            effective_from="1970-01-01T00:00:00Z", effective_to=None, visibility_scope="public")
        assert value.schedule.committed
        for actor in (value.actors[0], value.actors[2]):
            assert value.activation_authority.lock(world_ref=value.mode.world_ref, profile_ref=actor,
                expected_revision=value.store.get_stream_head(f"population:{value.mode.world_ref}")).committed
        value._wire_publisher()
        return value

    def _open(self):
        self.store = DurableGameplayEventStore(self.storage_root / "world.sqlite3", event_schema_registry=self.schemas)
        self.character_runtime = CharacterAgentRuntime(storage_root=self.storage_root / "character")
        self.activation_authority = ProfileActivationAuthority(registry=self.registry, store=self.store)
        self.character_runtime.set_activation_authority(self.activation_authority)
        self.world = WorldContinuityRuntime(store=self.store, mode=self.mode, roster=self.roster)
        self.bus = InMemoryAuthorityEventBus()
        merger = ContinuityMergeAuthority(store=self.store, registry=self.registry, mode=self.mode)
        self.capability = _ObservedCapability(continuity_port=CharacterRuntimeContinuityPort(self.character_runtime),
            owner_executor=ScheduleGatedSupplyOwnerExecutor(merger=merger,
                context_builder=ScheduleGatedSupplyOwnerExecutor.context_from_intent_payload))
        self.siming = SimingRuntime(population_capability=self.capability)
        self.bus.subscribe("population_cadence_event", self._tick)

    def _wire_publisher(self):
        self.publisher = RuntimeCadencePublisher(world_runtime=self.world, event_bus=self.bus,
            room_id="room:flood", scene_id="scene:flood", zone_id="zone:village")

    def _tick(self, event):
        result = self.siming.tick([SimingInput(input_type="population_cadence_input", source_event=event)])
        self.siming_tick_count += 1
        self.last_siming_result = result

    def run_window(self, *, from_tick, to_tick, player_actor_ref=None, budget=3):
        if self.current_situation is None:
            raise ValueError("flood_situation_not_active")
        if player_actor_ref is not None and player_actor_ref not in self.actors:
            raise ValueError("flood_actor_unknown")
        cadence = self.world.build_population_cadence(window_start=from_tick, window_end=to_tick,
            selector_revision="selector:generic:population:v1", ruleset_revision="flood:v1", budget=budget)
        personal = self._personal_inputs(cadence)
        cadence, projections = personal
        event = self.publisher(cadence, population_projections=projections)
        if event is None:
            raise ValueError("flood_publication_rejected")
        self.events[(from_tick, to_tick)] = event
        self._settle_schedule_member(from_tick=from_tick, to_tick=to_tick)
        if player_actor_ref is not None:
            self._intersect(player_actor_ref, cadence)
        return self.capability.last_result

    def _settle_schedule_member(self, *, from_tick, to_tick):
        # 组织承诺不归个人分摊；这里只消费另一份确有 actor 归因的班表成员事件。
        if from_tick != 0 or self.character_runtime.get_character_simulation_cursor("char_a") != to_tick:
            return
        result_ref = self.schedule.committed_event_ids[0]
        stream = self.world.member_ledger_stream(self.cohort_ref)
        self.world.confirm_member_result(cohort_ref=self.cohort_ref, actor_ref=self.actors[0], result_ref=result_ref,
            expected_revision=self.store.get_stream_head(stream), idempotency_key="confirm:flood-schedule")
        key = "consume:flood-schedule:core"
        if self.character_runtime.get_character_continuity_receipt("char_a", idempotency_key=key) is None:
            lock = self.character_runtime.get_character_activation_lock("char_a")
            command = CharacterContinuityCommand(command_id=key, actor_ref=self.actors[0],
                expected_character_revision=self.character_runtime.get_continuity_revision("char_a"),
                from_tick=from_tick, to_tick=to_tick, simulation_tick_cursor=to_tick,
                source_owner_receipt_refs=(result_ref,), source_revision_vector=dict(self.schedule.resulting_stream_revisions),
                state_delta={**self.needs(self.actors[0]), "presentation_seed": {"task": "confirmed_schedule"}},
                policy_revision="policy:character-continuity:v1", idempotency_key=key,
                activation_lock_ref=lock.lock_ref, activation_lock_revision=lock.held_revision)
            if self.character_runtime.apply_character_continuity_command(command).status != "committed":
                raise ValueError("flood_schedule_core_rejected")
        consumed = self.world.consume_member_result(cohort_ref=self.cohort_ref, actor_ref=self.actors[0], result_ref=result_ref,
            continuity_runtime=self.character_runtime, continuity_idempotency_key=key,
            expected_revision=self.store.get_stream_head(stream), idempotency_key="consume:flood-schedule")
        if not consumed.committed:
            raise ValueError("flood_schedule_consumption_rejected")

    def _personal_inputs(self, cadence):
        # 原 Owner 的空社会/家庭读侧仍是正式输入，不能虚构家庭、库存或旧识事实。
        observed = "1970-01-01T00:00:00Z"
        actor = self.actors[0]
        social_owner = SocialFactAuthority(store=self.store, registry=build_production_social_policy_registry())
        social = FrozenSocialPlanningInput.freeze(recipient_ref=actor, observed_at=observed,
            view=social_owner.view_for(recipient_ref=actor, now=observed))
        household = HouseholdScheduleInput.freeze(recipient_ref=actor, observed_at=observed,
            view=social_owner.household_view_for(recipient_ref=actor, now=observed))
        organization = OrganizationScheduleInput.freeze(recipient_ref=actor, observed_at=observed,
            view=OrganizationAuthority(store=self.store).schedule_view_for(organization_ref="org:flood-supply",
                recipient_ref=actor, observed_at=observed))
        vector = dict(cadence.base_revision_vector)
        for source in (social, household, organization):
            vector.update(source.source_revision_vector)
        cadence = cadence.model_copy(update={"base_revision_vector": vector, "deterministic_seed": "flood:20260918"})
        read_set = PopulationReadSet.from_inputs(cadence, ())
        projections = []
        for actor in self.actors:
            if actor == self.actors[1] and self.member_state(actor) != "handoff":
                continue
            frame = self._frame(actor, read_set)
            proposals = evaluate_modules(frame, to_tick=cadence.window_end)
            self.module_proposals[(cadence.window_start, cadence.window_end, actor)] = proposals
            delta = next(item.typed_payload.state_delta for item in proposals if item.proposal_kind == "continuity_delta")
            lock = self.activation_authority.active_lock(world_ref=self.mode.world_ref, profile_ref=actor)
            payload = dict(actor_ref=actor, candidate_kind="routine_work", fidelity_tier=frame.participation_resolution.recommended_tier,
                due=True, state_deltas=dict(delta), budget_cost=1, activation_lock_ref=lock.lock_ref,
                activation_lock_revision=lock.held_revision,
                evidence_refs=tuple(item.proposal_ref for item in proposals),
                presentation_seed={"task": "care_obligation" if actor == self.actors[0] else "personal_routine"})
            if actor == self.actors[0] and self.member_state(actor) == "active":
                # 工作单授权的供应请求只提交组织承诺，不能声称已收到粮食。
                action = next(item for item in proposals if item.proposal_kind == "action_candidate")
                candidate = BatchIntentCandidate(intent_ref=action.typed_payload.intent_ref, profile_ref=actor,
                    intent_kind="supply", payload={"organization_ref": "org:flood-supply",
                        "counterparty_organization_ref": "org:flood-supplier", "commitment_ref": f"commitment:flood:{cadence.window_start}",
                        "organization_grant_refs": [], "budget_reservation_refs": [], "schedule_work_order_ref": "work:flood-supply"},
                    priority=2, expected_revisions=vector, policy_revision=self.mode.revision, package_revision="package:farmer@1",
                    idempotency_key=action.typed_payload.intent_ref, correlation_id=cadence.cadence_id,
                    source_ref="population:flood-schedule", privacy_scope="public")
                payload.update(candidate_kind="schedule_gated_supply", schedule_gated_supply_source_context={
                    "mode": self.mode.model_dump(mode="json"), "candidate": candidate.model_dump(mode="json"),
                    "social_input": social.model_dump(mode="json"), "household_input": household.model_dump(mode="json"),
                    "organization_input": organization.model_dump(mode="json"),
                    "base_event_digest": simulation_digest([event.model_dump(mode="json") for event in self.store.read_events()]),
                    "base_checkpoint_sequence": 0, "tail_boundary": len(self.store.read_events())})
            projections.append(PopulationProjection(ref=f"projection:flood:{actor}:{cadence.window_start}",
                scope="public", revision_vector=vector, payload=payload))
        return cadence, tuple(projections)

    def _frame(self, actor, read_set):
        states = flood_module_states(actor_ref=actor)
        states["needs"] = {**self.needs(actor), "revision": self.character_runtime.get_continuity_revision(actor.removeprefix("character:"))}
        resolution = resolve_participation(policies=flood_participation_policies(actor_ref=actor, scenario_revision="flood:v1"),
            tick=read_set.cadence.window_end)
        if self.member_state(actor) == "handoff":
            packet = self.world.read_member_handoff(cohort_ref=self.cohort_ref, actor_ref=actor)
            resolution = resolution.model_copy(update={"recommended_tier": packet.target_fidelity})
        lock = self.activation_authority.active_lock(world_ref=self.mode.world_ref, profile_ref=actor)
        return build_simulation_frame(actor_ref=actor, profile_ref=actor, profile_revision="1",
            character_revision=self.character_runtime.get_continuity_revision(actor.removeprefix("character:")),
            tick_cursor=self.character_runtime.get_character_simulation_cursor(actor.removeprefix("character:")),
            read_set=read_set, module_states=states, participation=resolution, codebook_refs=(),
            activation_lock_ref=lock.lock_ref if lock else None, module_definitions=farmer_module_definitions())

    def _intersect(self, actor, cadence):
        if actor == self.actors[1]:
            receipt = self.world.latest_confirmation
            if receipt is None or receipt.window_end != cadence.window_end:
                raise ValueError("flood_intersection_requires_personal_anchor")
            assert self.activation_authority.lock(world_ref=self.mode.world_ref, profile_ref=actor,
                expected_revision=self.store.get_stream_head(f"population:{self.mode.world_ref}")).committed
            lock = self.character_runtime.get_character_activation_lock("char_b")
            values = self.world.population_hot_state.read("char_b")
            source = dict(cadence.base_revision_vector)
            cadence_stream = f"population-cadence:{self.mode.world_ref}"
            source[cadence_stream] = self.store.get_stream_head(cadence_stream)
            key = f"handoff-anchor:{actor}:{cadence.window_end}"
            command = CharacterContinuityCommand(command_id=key, actor_ref=actor,
                expected_character_revision=self.character_runtime.get_continuity_revision("char_b"),
                from_tick=self.character_runtime.get_character_simulation_cursor("char_b"),
                to_tick=cadence.window_end, simulation_tick_cursor=cadence.window_end,
                state_delta={field: values[field] for field in ("fatigue", "need_pressure")},
                source_revision_vector=source, policy_revision="policy:character-continuity:v1", idempotency_key=key,
                activation_lock_ref=lock.lock_ref, activation_lock_revision=lock.held_revision)
            if self.character_runtime.apply_character_continuity_command(command).status != "committed":
                raise ValueError("flood_intersection_anchor_rejected")
        current = {stream: self.store.get_stream_head(stream) for stream in cadence.base_revision_vector}
        stream = self.world.member_ledger_stream(self.cohort_ref)
        current[stream] = self.store.get_stream_head(stream)
        frame = self._frame(actor, PopulationReadSet.from_inputs(cadence.model_copy(update={"base_revision_vector": current}), ()))
        packet, result = self.world.prepare_member_handoff(cohort_ref=self.cohort_ref, frame=frame,
            trigger_kind="player_proximity", target_fidelity="B3", activation_authority=self.activation_authority,
            continuity_runtime=self.character_runtime, expected_revision=self.store.get_stream_head(stream),
            idempotency_key=f"intersection:{actor}:{cadence.window_end}")
        if not result.committed:
            raise ValueError("flood_intersection_rejected")
        self.intersections.append(packet)

    def identity_digest(self, actor_ref):
        return self.character_runtime.character_identity_digest(actor_ref.removeprefix("character:"))

    def exit_situation(self):
        # 仅卸载此受信样板内容，不伪造天气 Owner 的洪灾结束事实。
        self.current_situation = None

    def return_to_population(self, actor_ref):
        tick = self.publisher.confirmed_tick
        policies = flood_participation_policies(actor_ref=actor_ref, scenario_revision="flood:v1")
        resolution = resolve_participation(policies=policies, tick=tick)
        if (resolution.status != "resolved" or "B0" not in resolution.allowed_tiers
                or tick >= min(resolution.b0_expiry_tick, resolution.review_tick)
                or self.member_state(actor_ref) != "handoff"):
            raise ValueError("flood_b0_return_denied")
        old = self.world.read_member_ledger(self.cohort_ref)
        if (self.character_runtime.get_character_simulation_cursor(actor_ref.removeprefix("character:")) != tick
                or any(item.actor_ref == actor_ref and item.consumed_core_receipt_ref is None
                    for item in old.confirmed_results)):
            raise ValueError("character_readmission_pending_personal_work")
        resolutions = {actor: resolve_participation(policies=flood_participation_policies(
            actor_ref=actor, scenario_revision="flood:v1"), tick=tick) for actor in self.actors}
        lock = self.activation_authority.active_lock(world_ref=self.mode.world_ref, profile_ref=actor_ref)
        if lock is not None and not self.activation_authority.release_lock(lock_ref=lock.lock_ref,
                expected_revision=self.store.get_stream_head(f"population:{self.mode.world_ref}")).committed:
            raise ValueError("flood_b0_return_lock_pending")
        cohort = f"{self.cohort_ref}:return:{actor_ref}:{tick}"
        if not self.world.register_member_reentry(source_cohort_ref=self.cohort_ref, cohort_ref=cohort,
                actor_ref=actor_ref, resolution=resolution, continuity_runtime=self.character_runtime,
                activation_authority=self.activation_authority,
                idempotency_key=f"register:{cohort}").committed:
            raise ValueError("flood_b0_return_anchor_rejected")
        self.publisher.replace_character_participation(resolutions=resolutions, cohort_ref=cohort,
            continuity_runtime=self.character_runtime)
        self.resolutions, self.cohort_ref = resolutions, cohort

    def member_state(self, actor_ref):
        return next(item.lifecycle for item in self.world.read_member_ledger(self.cohort_ref).member_entries
            if item.actor_ref == actor_ref)

    def business_events(self):
        return tuple(event for event in self.store.read_events() if event.event_type.startswith("gameplay."))

    def needs(self, actor_ref):
        actor_id = actor_ref.removeprefix("character:")
        if actor_ref == self.actors[1] and self.member_state(actor_ref) == "active":
            row = self.world.population_hot_state.read(actor_id)
        else:
            row = self.character_runtime.get_seed_projection(actor_id).get("state_deltas", {})
        return {field: row.get(field, flood_module_states(actor_ref=actor_ref)["needs"][field])
            for field in ("fatigue", "need_pressure")}

    def statistics(self):
        members = tuple(entry.actor_ref for entry in self.world.read_member_ledger(self.cohort_ref).member_entries
            if entry.lifecycle == "active" and set(("needs.fatigue", "needs.need_pressure")) <= set(entry.aggregatable_field_refs))
        return dict(members=members, count=len(members),
            fatigue=tuple(self.needs(actor)["fatigue"] for actor in members),
            need_pressure=tuple(self.needs(actor)["need_pressure"] for actor in members))

    def authority_snapshot(self):
        return dict(events=tuple(event.model_dump(mode="json") for event in self.store.read_events()),
            hot=self.world.population_hot_state.export_rows(),
            members=self.world.read_member_ledger(self.cohort_ref).model_dump(mode="json"),
            characters={actor: dict(revision=self.character_runtime.get_continuity_revision(actor.removeprefix("character:")),
                projection=self.character_runtime.get_seed_projection(actor.removeprefix("character:")),
                timeline=self.character_runtime.get_session_timeline(actor.removeprefix("character:"))) for actor in self.actors})

    def redeliver(self, *, from_tick, to_tick):
        self.bus.publish(self.events[(from_tick, to_tick)])
        self._settle_schedule_member(from_tick=from_tick, to_tick=to_tick)
        return self.capability.last_result

    def restart(self):
        self.character_runtime.close()
        self.store.close()
        self._open()
        self.world.configure_character_participation(resolutions=self.resolutions,
            activation_authority=self.activation_authority, cohort_ref=self.cohort_ref)
        self._wire_publisher()

        self.cohort_ref = self.world._character_cohort_ref

    def close(self):
        self.character_runtime.close()
        self.store.close()
        if self._temporary is not None:
            self._temporary.cleanup()
