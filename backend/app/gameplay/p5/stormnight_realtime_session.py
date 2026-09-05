"""Finite realtime player adapter for the admitted Stormnight case.

This module deliberately owns no world store.  It binds one local player to
the already existing GameplayEventStore and derives every owner coordinate
from frozen case content and committed stream heads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import ConfigDict, Field

from app.gameplay.action_window_runtime import ActionWindowIntent, SpatialSnapshotRef
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.models import StrictGameplayModel
from app.gameplay.p5.contracts import canonical_sha256_digest
from app.gameplay.p5.investigation_conflict import InvestigationConflictAuthority
from app.gameplay.p5.quest_evidence import QuestEvidenceAuthority
from app.gameplay.p5.scripted_mystery_case_runtime import CaseOpenIntent, ScriptedMysteryCaseAuthority
from app.gameplay.p5.scripted_mystery_evidence import ScriptedMysteryEvidenceAdapter
from app.gameplay.p5.scripted_mystery_owner_handoff import StormnightOwnerHandoffService
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from app.gameplay.p5.stormnight_action_graph import stormnight_action_graph, stormnight_action_registry
from app.gameplay.p5.stormnight_owner_registries import stormnight_quest_registry, stormnight_social_registry
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.scripted_mystery_agent_turns import ScriptedMysteryAgentTurnService


PLAYER_REF = "character:stormnight-investigator@1"
SESSION_REF = "session:stormnight:local@1"
_SOURCE_STREAM = "world:stormnight:realtime-spatial"
_CONTAINER_ID = "container:stormnight:character:stormnight-investigator@1:evidence"
_CLUE_ITEM_DEFINITION = "item:stormnight:clue@1"


class StormnightPlayerIntent(StrictGameplayModel):
    """Only player choices; all authority-shaped data is derived server-side."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["start", "advance", "inspect", "question", "hide", "pursue", "accuse"]
    request_id: str = Field(min_length=1, max_length=128)
    target_ref: str | None = None
    actor_ref: str | None = None


class StormnightRealtimeResponse(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    session_ref: str
    player_ref: str
    idempotency_status: Literal["committed", "duplicate_replayed", "rejected"]
    error_code: str | None = None
    receipt_event_ids: tuple[str, ...] = ()
    projection: dict[str, object] = {}
    npc_proposal: dict[str, object] | None = None


@dataclass
class StormnightRealtimeSessionService:
    """Owner-bound realtime facade over the application's shared store."""

    store: GameplayEventStore

    def __post_init__(self) -> None:
        self.case = ScriptedMysteryCaseAuthority.create(self.store)
        self.content = self.case.package.content
        self.social = SocialFactAuthority(registry=stormnight_social_registry(), store=self.store)
        self.quest = QuestEvidenceAuthority(registry=stormnight_quest_registry(), store=self.store)
        self.handoff = StormnightOwnerHandoffService(self.store, social_authority=self.social, quest_authority=self.quest)
        registry = InventoryDefinitionRegistry()
        registry.register_item(ItemDefinition(_CLUE_ITEM_DEFINITION, "1", 1, 1))
        self.inventory = InventoryAuthorityService(store=self.store, registry=registry)
        self._request_digests: dict[str, str] = {}

    def handle(self, intent: StormnightPlayerIntent) -> StormnightRealtimeResponse:
        digest = canonical_sha256_digest(intent.model_dump(mode="json"))
        prior = self._request_digests.get(intent.request_id)
        if prior is not None:
            if prior != digest:
                return self._rejected("stormnight_player_idempotency_reused")
            return self._response(accepted=True, status="duplicate_replayed")
        if intent.actor_ref not in {None, PLAYER_REF}:
            return self._rejected("stormnight_player_actor_forbidden")
        handler = {
            "start": self._start,
            "advance": self._advance,
            "inspect": self._inspect,
            "question": self._question,
            "hide": self._action,
            "pursue": self._action,
            "accuse": self._accuse,
        }[intent.kind]
        result = handler(intent)
        if result.accepted:
            self._request_digests[intent.request_id] = digest
        return result

    def _start(self, intent: StormnightPlayerIntent) -> StormnightRealtimeResponse:
        result = self.case.open_case(
            CaseOpenIntent(
                case_ref=self.content.case_ref,
                case_revision=self.content.case_revision,
                expected_stream_revision=self.store.get_stream_head(self.case.stream_id),
                command_id=f"stormnight:player:{intent.request_id}:start",
                idempotency_key=f"stormnight:player:{intent.request_id}:start",
                causation_id=intent.request_id,
                correlation_id=SESSION_REF,
                submitted_at="2026-09-06T00:00:00Z",
            )
        )
        if not result.committed:
            return self._rejected(result.error_code or "stormnight_start_rejected")
        self._seed_spatial_source()
        return self._response(accepted=True, status="committed", event_ids=(result.event_id,) if result.event_id else ())

    def _advance(self, intent: StormnightPlayerIntent) -> StormnightRealtimeResponse:
        projection = self.case.project()
        if not projection.opened:
            return self._rejected("case_not_open")
        if not projection.committed_clue_refs:
            return self._rejected("stormnight_phase_clue_prerequisite_missing")
        phase = {"phase:stormnight:arrival@1": "phase:stormnight:investigation@1", "phase:stormnight:investigation@1": "phase:stormnight:storm-night@1"}.get(projection.phase_ref or "")
        if phase is None:
            return self._rejected("case_phase_order_invalid")
        result = self.case.advance_phase(
            command_id=f"stormnight:player:{intent.request_id}:advance",
            idempotency_key=f"stormnight:player:{intent.request_id}:advance",
            phase_ref=phase,
            expected_revision=self.store.get_stream_head(self.case.stream_id),
            causation_id=intent.request_id,
            correlation_id=SESSION_REF,
        )
        return self._response_from_result(result)

    def _inspect(self, intent: StormnightPlayerIntent) -> StormnightRealtimeResponse:
        projection = self.case.project()
        if not projection.opened:
            return self._rejected("case_not_open")
        clue = next((item for item in self.content.clue_definitions if item.clue_ref not in projection.committed_clue_refs), None)
        if clue is None:
            return self._rejected("stormnight_all_clues_collected")
        inventory_view = self.inventory._projector.rebuild(PLAYER_REF, self.store.read_events())
        if _CONTAINER_ID not in inventory_view.containers:
            created = self.inventory.create_container(
                command_id=f"stormnight:player:{intent.request_id}:container",
                actor_ref=PLAYER_REF,
                spec=ContainerSpec(_CONTAINER_ID, 20, 20, 20),
                idempotency_key=f"stormnight:player:{intent.request_id}:container",
                causation_id=intent.request_id,
                correlation_id=SESSION_REF,
            )
            if not created.committed:
                return self._rejected(created.failure.error_code if created.failure else "stormnight_inventory_container_rejected")
        quest = self.handoff.record_quest_evidence(
            case_ref=self.content.case_ref,
            clue_ref=clue.clue_ref,
            discoverer_ref=PLAYER_REF,
            expected_revision=self.store.get_stream_head(f"gameplay:evidence:{clue.clue_ref}"),
            command_id=f"stormnight:player:{intent.request_id}:quest",
            idempotency_key=f"stormnight:player:{intent.request_id}:quest",
            causation_id=intent.request_id,
            correlation_id=SESSION_REF,
        )
        if bool(getattr(quest, "zero_write", False)) or not tuple(getattr(quest, "committed_event_ids", ())):
            return self._rejected(str(getattr(quest, "error_code", "") or "stormnight_quest_evidence_rejected"))
        custody = self.handoff.record_inventory_clue_custody(
            inventory_authority=self.inventory,
            case_ref=self.content.case_ref,
            clue_ref=clue.clue_ref,
            discoverer_ref=PLAYER_REF,
            container_id=_CONTAINER_ID,
            command_id=f"stormnight:player:{intent.request_id}:custody",
            idempotency_key=f"stormnight:player:{intent.request_id}:custody",
            causation_id=intent.request_id,
            correlation_id=SESSION_REF,
        )
        if not custody.committed:
            return self._rejected(custody.failure.error_code if custody.failure else "stormnight_inventory_custody_rejected")
        return self._response(accepted=True, status="committed", event_ids=tuple(getattr(quest, "committed_event_ids", ())) + tuple(custody.committed_event_ids))

    def _question(self, intent: StormnightPlayerIntent) -> StormnightRealtimeResponse:
        if not intent.target_ref:
            return self._rejected("stormnight_question_target_required")
        statement = next((item for item in self.content.statement_definitions if item.speaker_ref == intent.target_ref), None)
        if statement is None:
            return self._rejected("stormnight_question_target_unadmitted")
        if not self.case.project().opened:
            return self._rejected("case_not_open")
        case_result = self.case.record_statement(
            statement_ref=statement.statement_ref,
            speaker_ref=statement.speaker_ref,
            target_ref=statement.target_ref,
            mode="reveal",
            command_id=f"stormnight:player:{intent.request_id}:statement",
            idempotency_key=f"stormnight:player:{intent.request_id}:statement",
            expected_revision=self.store.get_stream_head(self.case.stream_id),
            causation_id=intent.request_id,
            correlation_id=SESSION_REF,
        )
        if not case_result.committed:
            return self._rejected(case_result.error_code or "stormnight_statement_rejected")
        knowledge_stream = "gameplay:knowledge:" + canonical_sha256_digest(
            {"case_ref": self.content.case_ref, "statement_ref": statement.statement_ref, "speaker_ref": statement.speaker_ref}
        ).split(":", 1)[1]
        social = self.handoff.record_social_statement(
            case_ref=self.content.case_ref,
            statement_ref=statement.statement_ref,
            speaker_ref=statement.speaker_ref,
            target_ref=statement.target_ref,
            mode="reveal",
            expected_revision=self.store.get_stream_head(knowledge_stream),
            command_id=f"stormnight:player:{intent.request_id}:social",
            idempotency_key=f"stormnight:player:{intent.request_id}:social",
            causation_id=intent.request_id,
            correlation_id=SESSION_REF,
        )
        if bool(getattr(social, "zero_write", False)) or not tuple(getattr(social, "committed_event_ids", ())):
            return self._rejected(str(getattr(social, "error_code", "") or "stormnight_social_statement_rejected"))
        return self._response(accepted=True, status="committed", event_ids=(case_result.event_id,) if case_result.event_id else ())

    def _action(self, intent: StormnightPlayerIntent) -> StormnightRealtimeResponse:
        if not self.case.project().opened:
            return self._rejected("case_not_open")
        action_count = self.case.project().action_window_count
        nodes = ("arrival", "investigate", "recover")
        if action_count >= len(nodes):
            return self._rejected("stormnight_action_window_exhausted")
        graph = stormnight_action_graph()
        target_ref = ("location:stormnight:arrival@1", "location:stormnight:records@1", "location:stormnight:courtyard@1")[action_count]
        contact = intent.kind == "pursue"
        window = ActionWindowIntent(
            attempt_ref=f"attempt:stormnight:player:{action_count}", encounter_ref="encounter:stormnight", actor_ref=PLAYER_REF,
            window_index=action_count, window_start_tick=action_count, window_end_tick=action_count + 1,
            graph_ref=graph.graph_ref, graph_revision=graph.graph_revision, node_ref=nodes[action_count], target_refs=(target_ref,),
            expected_revision_vector={_SOURCE_STREAM: self.store.get_stream_head(_SOURCE_STREAM)}, local_position_sample=(0.0, 0.0, 0.0),
            facing_sample=(0.0, 0.0, 1.0), visibility_sample={"visible": True}, sound_sample={"heard": False}, contact_sample={"in_contact": contact},
            navigation_revision="nav:stormnight@1", collision_revision="collision:stormnight@1", occlusion_revision="occlusion:stormnight@1", sound_zone_revision="sound:stormnight@1",
            deterministic_seed=f"seed:stormnight:player:{action_count}", evidence_refs=(f"evidence:stormnight:window:{action_count}@1",),
        )
        snapshot = SpatialSnapshotRef(
            snapshot_ref="snapshot:stormnight:realtime@1", navigation_revision="nav:stormnight@1", collision_revision="collision:stormnight@1", occlusion_revision="occlusion:stormnight@1", sound_zone_revision="sound:stormnight@1",
            source_revision_vector={_SOURCE_STREAM: self.store.get_stream_head(_SOURCE_STREAM)}, visibility_by_target={target_ref: True}, sound_by_target={target_ref: False}, contact_by_target={target_ref: contact}, distance_band_by_target={target_ref: "near"},
        )
        conflict_stream = "gameplay:conflict:encounter:stormnight"
        command = GameplayCommandEnvelope(
            command_id=f"stormnight:player:{intent.request_id}:action", command_type="gameplay.conflict.resolve_action_window", command_version=1,
            principal_ref="authority:p5:investigation-conflict", actor_ref=PLAYER_REF, project_ref="project:stormnight", transaction_id=f"stormnight:player:{intent.request_id}:action",
            idempotency_key=f"stormnight:player:{intent.request_id}:action", expected_revisions={conflict_stream: self.store.get_stream_head(conflict_stream)}, read_set_revisions={_SOURCE_STREAM: self.store.get_stream_head(_SOURCE_STREAM)}, causation_id=intent.request_id, correlation_id=SESSION_REF, source_ref=_SOURCE_STREAM, submitted_at="2026-09-06T00:00:00Z",
        )
        result = InvestigationConflictAuthority(registry=stormnight_action_registry(), store=self.store).resolve_action_window(
            command=command, intent=window, graph=graph, spatial_snapshot=snapshot, role_ref="role:survivor@1", now="2026-09-06T00:00:00Z"
        )
        if not result.committed:
            return self._rejected(result.error_code or "stormnight_action_rejected")
        return self._response(accepted=True, status="committed", event_ids=tuple(result.receipt.committed_event_ids) if result.receipt else ())

    def _accuse(self, intent: StormnightPlayerIntent) -> StormnightRealtimeResponse:
        if intent.target_ref not in self.content.actor_refs:
            return self._rejected("stormnight_accusation_target_unadmitted")
        projection = self.case.project()
        adapter = ScriptedMysteryEvidenceAdapter(content=self.content)
        context = adapter.build_turn_context(projection, PLAYER_REF)
        evidence = tuple(sorted(context.public_fact_refs[:2]))
        result = self.case.submit_accusation(
            accuser_ref=PLAYER_REF, target_ref=intent.target_ref or "", evidence_refs=evidence,
            command_id=f"stormnight:player:{intent.request_id}:accuse", idempotency_key=f"stormnight:player:{intent.request_id}:accuse",
            expected_revision=self.store.get_stream_head(self.case.stream_id), causation_id=intent.request_id, correlation_id=SESSION_REF,
        )
        if not result.committed:
            return self._rejected(result.error_code or "stormnight_accusation_rejected")
        outcome = "case_solved" if intent.target_ref == self.content.culprit_actor_ref else "false_accusation"
        resolved = self.case.resolve_outcome(
            command_id=f"stormnight:player:{intent.request_id}:outcome", idempotency_key=f"stormnight:player:{intent.request_id}:outcome", outcome_kind=outcome,
            expected_revision=self.store.get_stream_head(self.case.stream_id), causation_id=intent.request_id, correlation_id=SESSION_REF,
        )
        if not resolved.committed:
            return self._rejected(resolved.error_code or "stormnight_outcome_rejected")
        return self._response(accepted=True, status="committed", event_ids=tuple(item for item in (result.event_id, resolved.event_id) if item))

    def _seed_spatial_source(self) -> None:
        if self.store.get_stream_head(_SOURCE_STREAM) > 0:
            return
        self.store.append_batch(build_atomic_event_batch(
            command_id="stormnight:realtime:spatial-source", principal_ref="authority:stormnight:spatial", stream_id=_SOURCE_STREAM,
            expected_revision=0, read_stream_revisions={_SOURCE_STREAM: 0},
            event_specs=(("world.stormnight.spatial_snapshot_committed", {"actor_ref": PLAYER_REF, "visibility_policy": "project"}),),
            idempotency_key="stormnight:realtime:spatial-source", causation_id=SESSION_REF, correlation_id=SESSION_REF,
        ))

    def _response_from_result(self, result) -> StormnightRealtimeResponse:
        if not result.committed:
            return self._rejected(result.error_code or "stormnight_case_rejected")
        return self._response(accepted=True, status="committed", event_ids=(result.event_id,) if result.event_id else ())

    def _response(self, *, accepted: bool, status: Literal["committed", "duplicate_replayed", "rejected"], event_ids: tuple[str, ...] = ()) -> StormnightRealtimeResponse:
        projection = self.case.project()
        adapter = ScriptedMysteryEvidenceAdapter(content=self.content)
        context = adapter.build_turn_context(projection, PLAYER_REF) if projection.opened else None
        player_private = tuple(context.private_fact_refs) if context else ()
        player_visible = tuple(sorted(set((context.public_fact_refs if context else ()) + player_private)))
        npc_proposal = self._npc_proposal(projection)
        payload = projection.model_dump(mode="json")
        payload.update({"player_visible_fact_refs": player_visible, "player_private_fact_refs": player_private, "session_ref": SESSION_REF})
        return StormnightRealtimeResponse(accepted=accepted, session_ref=SESSION_REF, player_ref=PLAYER_REF, idempotency_status=status, receipt_event_ids=event_ids, projection=payload, npc_proposal=npc_proposal)

    def _npc_proposal(self, projection) -> dict[str, object] | None:
        if not projection.opened:
            return None
        guardian_ref = "character:stormnight-guardian@1"
        context = ScriptedMysteryEvidenceAdapter(content=self.content).build_turn_context(projection, guardian_ref)
        decision = ScriptedMysteryAgentTurnService().propose_turn_from_character_runtime(
            CharacterAgentRuntime(), CharacterPerceivedEvent(actor_id=guardian_ref, percept_channel="auditory", producer_ts=1, room_id="stormnight", scene_id="stormnight", zone_id="case", perceived_summary="A player action has been committed.", source_candidate_event_id="source:stormnight:realtime@1"),
            context=context, case_ref=self.content.case_ref, turn_id=f"turn:stormnight:{projection.last_global_sequence}", policy="guardian",
        )
        return decision.proposal.model_dump(mode="json") if decision.accepted and decision.proposal else None

    def _rejected(self, error_code: str) -> StormnightRealtimeResponse:
        return StormnightRealtimeResponse(accepted=False, session_ref=SESSION_REF, player_ref=PLAYER_REF, idempotency_status="rejected", error_code=error_code, projection={})


__all__ = ["PLAYER_REF", "SESSION_REF", "StormnightPlayerIntent", "StormnightRealtimeResponse", "StormnightRealtimeSessionService"]
