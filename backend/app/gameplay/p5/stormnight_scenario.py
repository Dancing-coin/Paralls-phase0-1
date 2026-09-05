"""Deterministic Stormnight reference-game scenario composition."""

from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.action_window_runtime import ActionWindowIntent, SpatialSnapshotRef
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.investigation_conflict import InvestigationConflictAuthority
from app.gameplay.p5.scripted_mystery_case_runtime import CaseOpenIntent, ScriptedMysteryCaseAuthority
from app.gameplay.p5.scripted_mystery_case_package import StormnightCasePackage, load_stormnight_case_package
from app.gameplay.p5.scripted_mystery_content import stormnight_case_content
from app.gameplay.p5.scripted_mystery_evidence import AccusationIntent, ScriptedMysteryEvidenceAdapter
from app.gameplay.p5.scripted_mystery_owner_handoff import StormnightOwnerHandoffService
from app.gameplay.p5.stormnight_action_graph import stormnight_action_graph, stormnight_action_registry
from app.gameplay.p5.contracts import canonical_sha256_digest
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from app.gameplay.p5.quest_evidence import QuestEvidenceAuthority
from app.gameplay.p5.stormnight_owner_registries import stormnight_quest_registry, stormnight_social_registry
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.scripted_mystery_agent_turns import ScriptedMysteryAgentTurnService


@dataclass(frozen=True)
class StormnightScenarioResult:
    case_opened: bool
    action_window_committed: bool
    statement_committed: bool
    clue_committed: bool
    custody_committed: bool
    accusation_committed: bool
    outcome_kind: str
    outcome_committed: bool
    full_replay_hash: str
    tail_replay_hash: str
    owner_replay_hash: str
    phases_completed: int
    agent_turn_proposed: bool
    owner_replay_consistent: bool
    owner_projection_consistent: bool


class StormnightScenarioRunner:
    """Run one deterministic content-backed scenario on one event store."""

    def __init__(self, *, store: GameplayEventStore | None = None, package: StormnightCasePackage | None = None) -> None:
        self.store = store or GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
        self.package = package or load_stormnight_case_package()
        self.case = ScriptedMysteryCaseAuthority.create(self.store, self.package)
        self.content = self.package.content
        self.social_authority = SocialFactAuthority(registry=stormnight_social_registry(), store=self.store)
        self.quest_authority = QuestEvidenceAuthority(registry=stormnight_quest_registry(), store=self.store)
        self.handoff = StormnightOwnerHandoffService(self.store, social_authority=self.social_authority, quest_authority=self.quest_authority)
        self._source_stream = "world:stormnight:scene"

    def run(self, *, outcome_kind: str = "case_solved") -> StormnightScenarioResult:
        if outcome_kind not in {item.outcome_kind for item in self.content.outcome_definitions}:
            raise ValueError("stormnight_outcome_unadmitted")
        opened = self.case.open_case(CaseOpenIntent(case_ref=self.content.case_ref, case_revision=self.content.case_revision, command_id="stormnight:open", idempotency_key="stormnight:open", causation_id="stormnight", correlation_id="stormnight", submitted_at="2026-09-05T00:00:00Z"))
        self._seed_spatial_source()
        action = self._resolve_action_window()
        phase_two = self.case.advance_phase(command_id="stormnight:phase-2", idempotency_key="stormnight:phase-2", phase_ref="phase:stormnight:investigation@1", expected_revision=1, causation_id="stormnight", correlation_id="stormnight")
        phase_three = self.case.advance_phase(command_id="stormnight:phase-3", idempotency_key="stormnight:phase-3", phase_ref="phase:stormnight:storm-night@1", expected_revision=2, causation_id="stormnight", correlation_id="stormnight")
        statement = self.content.statement_definitions[0]
        social, quest = self.case.handoff_statement_and_clue(
            handoff=self.handoff,
            statement_ref=statement.statement_ref,
            speaker_ref=statement.speaker_ref,
            target_ref=statement.target_ref,
            mode="reveal",
            clue_ref=self.content.clue_definitions[0].clue_ref,
            discoverer_ref=statement.speaker_ref,
            social_expected_revision=0,
            quest_expected_revision=0,
            command_id="stormnight:handoff",
            idempotency_key="stormnight:handoff",
            causation_id="stormnight",
            correlation_id="stormnight",
        )
        inventory_registry = InventoryDefinitionRegistry()
        inventory_registry.register_item(ItemDefinition("item:stormnight:clue@1", "1", 1, 1))
        inventory = InventoryAuthorityService(store=self.store, registry=inventory_registry)
        discoverer = statement.speaker_ref
        container_id = f"container:stormnight:{discoverer}:evidence"
        inventory.create_container(command_id="stormnight:container", actor_ref=discoverer, spec=ContainerSpec(container_id, 10, 10, 10), idempotency_key="stormnight:container", causation_id="stormnight", correlation_id="stormnight")
        custody = self.handoff.record_inventory_clue_custody(
            inventory_authority=inventory,
            case_ref=self.content.case_ref,
            clue_ref=self.content.clue_definitions[0].clue_ref,
            discoverer_ref=discoverer,
            container_id=container_id,
            command_id="stormnight:custody",
            idempotency_key="stormnight:custody",
            causation_id="stormnight",
            correlation_id="stormnight",
        )
        projection = self.case.project()
        context = ScriptedMysteryEvidenceAdapter(content=self.content).build_turn_context(projection, statement.speaker_ref)
        agent_turn = ScriptedMysteryAgentTurnService().propose_turn_from_character_runtime(
            CharacterAgentRuntime(),
            CharacterPerceivedEvent(
                actor_id=statement.speaker_ref,
                percept_channel="visual",
                producer_ts=1,
                room_id="stormnight",
                scene_id="stormnight",
                zone_id="investigation",
                perceived_summary="A copper mark is visible near the evidence table.",
                source_candidate_event_id="source:stormnight:agent-perception@1",
            ),
            context=context,
            case_ref=self.content.case_ref,
            turn_id="stormnight:agent-turn",
            policy="investigator",
        )
        accusation = self.case.submit_accusation(
            accuser_ref=statement.speaker_ref,
            target_ref=statement.target_ref,
            evidence_refs=(context.public_fact_refs[0], context.public_fact_refs[1]),
            command_id="stormnight:accusation",
            idempotency_key="stormnight:accusation",
            expected_revision=3,
            causation_id="stormnight",
            correlation_id="stormnight",
        )
        resolved = self.case.resolve_outcome(command_id="stormnight:outcome", idempotency_key="stormnight:outcome", outcome_kind=outcome_kind, expected_revision=4, causation_id="stormnight", correlation_id="stormnight")
        full = self.case.replay_full()
        events = self.store.read_events()
        checkpoint = self.case.create_checkpoint(events[: max(1, len(events) // 2)])
        tail = self.case.replay_checkpoint_tail(checkpoint)
        owner_replay_hash = self._owner_replay_hash()
        owner_replay_hash_again = self._owner_replay_hash()
        owner_projection_consistent = (
            self.quest_authority.scripted_mystery_evidence_view(case_ref=self.content.case_ref)["projection_hash"]
            == self.quest_authority.scripted_mystery_evidence_view(case_ref=self.content.case_ref)["projection_hash"]
            and self.social_authority.scripted_mystery_statement_view(case_ref=self.content.case_ref, recipient_ref=statement.speaker_ref)["projection_hash"]
            == self.social_authority.scripted_mystery_statement_view(case_ref=self.content.case_ref, recipient_ref=statement.speaker_ref)["projection_hash"]
        )
        return StormnightScenarioResult(
            case_opened=opened.committed,
            action_window_committed=action.committed,
            statement_committed=bool(getattr(social, "committed_event_ids", ())) and not bool(getattr(social, "zero_write", False)),
            clue_committed=bool(getattr(quest, "committed_event_ids", ())) and not bool(getattr(quest, "zero_write", False)),
            custody_committed=custody.committed,
            accusation_committed=accusation.committed,
            outcome_kind=outcome_kind,
            outcome_committed=resolved.committed,
            full_replay_hash=full.projection_hash,
            tail_replay_hash=tail.projection_hash,
            owner_replay_hash=owner_replay_hash,
            phases_completed=sum(1 for phase in (opened, phase_two, phase_three) if phase.committed),
            agent_turn_proposed=agent_turn.accepted,
            owner_replay_consistent=owner_replay_hash == owner_replay_hash_again,
            owner_projection_consistent=owner_projection_consistent,
        )

    def _owner_replay_hash(self) -> str:
        """Hash all owner streams touched by the scenario for reconnect evidence."""
        rows = []
        for event in self.store.read_events():
            if event.event_type.startswith(("gameplay.p5.mystery.", "gameplay.social.", "gameplay.quest.", "gameplay.inventory.")):
                rows.append({"event_id": event.event_id, "event_type": event.event_type, "stream_id": event.stream_id, "stream_revision": event.stream_revision, "visibility_policy": event.visibility_policy, "payload": dict(event.payload)})
        return canonical_sha256_digest(rows)

    def _seed_spatial_source(self) -> None:
        if self.store.get_stream_head(self._source_stream) > 0:
            return
        self.store.append_batch(
            build_atomic_event_batch(
                command_id="stormnight:spatial-source",
                principal_ref="authority:stormnight:spatial",
                stream_id=self._source_stream,
                expected_revision=0,
                read_stream_revisions={self._source_stream: 0},
                event_specs=(("world.stormnight.spatial_snapshot_committed", {"actor_ref": self.content.actor_refs[0], "visibility_policy": "project"}),),
                idempotency_key="stormnight:spatial-source",
                causation_id="stormnight",
                correlation_id="stormnight",
            )
        )

    def _resolve_action_window(self):
        graph = stormnight_action_graph()
        intent = ActionWindowIntent(
            attempt_ref="attempt:stormnight:arrival",
            encounter_ref="encounter:stormnight",
            actor_ref=self.content.actor_refs[0],
            window_index=0,
            window_start_tick=0,
            window_end_tick=1,
            graph_ref=graph.graph_ref,
            graph_revision=graph.graph_revision,
            node_ref="arrival",
            target_refs=("location:stormnight:arrival@1",),
            expected_revision_vector={self._source_stream: 1},
            local_position_sample=(0.0, 0.0, 0.0),
            facing_sample=(0.0, 0.0, 1.0),
            visibility_sample={"visible": True},
            sound_sample={"heard": False},
            contact_sample={"in_contact": False},
            navigation_revision="nav:stormnight@1",
            collision_revision="collision:stormnight@1",
            occlusion_revision="occlusion:stormnight@1",
            sound_zone_revision="sound:stormnight@1",
            deterministic_seed="seed:stormnight:arrival",
            evidence_refs=("evidence:stormnight:arrival@1",),
        )
        snapshot = SpatialSnapshotRef(
            snapshot_ref="snapshot:stormnight@1",
            navigation_revision="nav:stormnight@1",
            collision_revision="collision:stormnight@1",
            occlusion_revision="occlusion:stormnight@1",
            sound_zone_revision="sound:stormnight@1",
            source_revision_vector={self._source_stream: 1},
            visibility_by_target={"location:stormnight:arrival@1": True},
            sound_by_target={"location:stormnight:arrival@1": False},
            contact_by_target={"location:stormnight:arrival@1": False},
            distance_band_by_target={"location:stormnight:arrival@1": "near"},
        )
        command = GameplayCommandEnvelope(
            command_id="stormnight:action",
            command_type="gameplay.conflict.resolve_action_window",
            command_version=1,
            principal_ref="authority:p5:investigation-conflict",
            actor_ref=self.content.actor_refs[0],
            project_ref="project:stormnight",
            transaction_id="stormnight:action",
            idempotency_key="stormnight:action",
            expected_revisions={"gameplay:conflict:encounter:stormnight": 0},
            read_set_revisions={self._source_stream: 1},
            causation_id="stormnight",
            correlation_id="stormnight",
            source_ref=self._source_stream,
            submitted_at="2026-09-05T00:00:00Z",
        )
        return InvestigationConflictAuthority(registry=stormnight_action_registry(), store=self.store).resolve_action_window(command=command, intent=intent, graph=graph, spatial_snapshot=snapshot, role_ref="role:survivor@1", now="2026-09-05T00:00:00Z")


__all__ = ["StormnightScenarioResult", "StormnightScenarioRunner"]
