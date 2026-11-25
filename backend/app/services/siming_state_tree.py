from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.contracts.owner_fact_query import FactTypeValue, OwnerFactQuery
from app.models.fact_type import FACT_TYPE_REGISTRY, FactType, FactTypeRef
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    ObservedSimingEvent,
    StateTreeNode,
    StateTreeSnapshot,
)


@dataclass(frozen=True)
class SimingPayloadSchema:
    environment_key: str = "target_environment_id"
    actor_key: str = "target_actor_id"
    fact_key: str = "established_fact_id"
    object_key: str = "target_object_id"


# S1: aggregate event contracts; unknown gameplay payloads require a declaration.
# Phase 2: load these bindings from Owner FactType schemas when available.
_PAYLOAD_SCHEMAS = {fact: SimingPayloadSchema() for fact in (
    FactType.WORLD_FACT, FactType.VISUAL_FACT, FactType.ESM_RESULT,
    FactType.CHARACTER_BEHAVIOR, FactType.CONVERSATION_RESOLUTION,
    FactType.CONSTRAINT_STATE, FactType.POPULATION_CADENCE,
)}


class InMemorySimingStateTree:
    def __init__(self, *, owner_query: OwnerFactQuery | None = None,
                 payload_schemas: Mapping[FactType | FactTypeRef, SimingPayloadSchema] | None = None) -> None:
        self._owner_query = owner_query
        self._latest_snapshot: StateTreeSnapshot | None = None
        self._payload_schemas = dict(_PAYLOAD_SCHEMAS if payload_schemas is None else payload_schemas)

    def get_state(self, actor_id: str, fact_types: Iterable[FactTypeValue]) -> dict[FactTypeValue, Mapping[str, object]]:
        if self._owner_query is None:
            raise ValueError("owner_fact_query_required")
        projections = self._owner_query.query_facts(
            fact_types, actor_refs=[actor_id], audience="siming_internal"
        )
        return {projection.fact_type: projection.payload for projection in projections}

    def update_from_observed(
        self,
        observed_events: list[ObservedSimingEvent],
        *,
        sim_tick_ts: int,
    ) -> StateTreeSnapshot:
        snapshot = self.plan_from_observed(observed_events, sim_tick_ts=sim_tick_ts)
        self.install_snapshot(snapshot)
        return snapshot

    def install_snapshot(self, snapshot: StateTreeSnapshot) -> None:
        self._latest_snapshot = snapshot

    def plan_from_observed(
        self,
        observed_events: list[ObservedSimingEvent],
        *,
        sim_tick_ts: int,
    ) -> StateTreeSnapshot:
        if not observed_events:
            raise ValueError("at least one observed event is required")

        current_event = observed_events[-1]
        environment_id = self._latest_non_empty_payload_value(
            observed_events, "environment_key"
        )
        actor_id = self._latest_non_empty_payload_value(observed_events, "actor_key")
        object_id = self._latest_non_empty_payload_value(observed_events, "object_key")
        established_fact_id = self._latest_non_empty_payload_value(
            observed_events, "fact_key"
        )

        from app.services.siming_visual_protocol import SimingVisualFactProtocol
        visual = SimingVisualFactProtocol.project(current_event.authority_event, self._latest_snapshot)
        snapshot = StateTreeSnapshot(
            source_event_id=current_event.source_event_id,
            snapshot_id=f"state_tree:{current_event.room_id}:{sim_tick_ts}",
            schema_version=1,
            producer_system="siming.state_tree",
            room_id=current_event.room_id,
            scene_id=current_event.scene_id,
            zone_id=current_event.zone_id,
            world_ts=current_event.producer_ts,
            sim_tick_ts=sim_tick_ts,
            causation_id=current_event.causation_id,
            correlation_id=current_event.correlation_id,
            environment=StateTreeNode(
                node_id=f"environment:{environment_id or 'unknown'}",
                owner_system="L1/ESM",
                authority="mirror",
                status="fresh" if environment_id else "partial",
                summary={
                    "target_environment_id": environment_id,
                    "target_object_id": object_id,
                    **visual,
                    "established_fact_id": (visual["established_fact_id"]
                        if current_event.payload.get("fact_type") == "visual_evidence_projection"
                        else established_fact_id),
                },
            ),
            character=StateTreeNode(
                node_id=f"character:{actor_id or 'unknown'}",
                owner_system="character_agent",
                authority="mirror",
                status="fresh" if actor_id else "partial",
                summary={"target_actor_id": actor_id},
            ),
            storyline=StateTreeNode(
                node_id="storyline:main",
                owner_system="siming",
                authority="editable",
                status="fresh",
                summary={"active_phase": "rising"},
            ),
            group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
        )
        return snapshot

    @property
    def latest_snapshot(self) -> StateTreeSnapshot | None:
        return self._latest_snapshot

    def _optional_payload_value(self, event: ObservedSimingEvent, key: str) -> str | None:
        value = event.payload.get(key)
        if value is None:
            return None
        text = str(value)
        return text or None

    def _latest_non_empty_payload_value(
        self,
        observed_events: list[ObservedSimingEvent],
        key: str,
    ) -> str | None:
        latest_value: str | None = None
        for event in observed_events:
            schema = self._payload_schemas.get(FACT_TYPE_REGISTRY.from_event_type(event.event_type))
            if schema is None:
                continue
            value = self._optional_payload_value(event, getattr(schema, key))
            if value is not None:
                latest_value = value
        return latest_value
