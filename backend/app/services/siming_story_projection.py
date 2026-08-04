from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.models.siming_heavenly_memory import SimingCompiledContext
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    NarrativeReadModel,
    StateTreeNode,
    StateTreeSnapshot,
    StorylineStateSnapshot,
)


class SimingGraphProjectionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_tree: StateTreeSnapshot
    storyline: StorylineStateSnapshot
    read_model: NarrativeReadModel
    debug_summary: dict[str, JsonValue] = Field(default_factory=dict)


class SimingStoryProjection:
    def project(self, context: SimingCompiledContext) -> SimingGraphProjectionBundle:
        scope = context.request.scope
        ref = context.context_hash
        state_tree = StateTreeSnapshot(
            snapshot_id=f"state-tree:{ref}", schema_version=1, producer_system="siming.graph_projection",
            room_id=scope.room_id or "room:unknown", scene_id=scope.scene_id or "scene:unknown", zone_id="graph",
            world_ts=context.request.valid_at, sim_tick_ts=context.request.valid_at,
            causation_id=ref, correlation_id=ref,
            environment=StateTreeNode(node_id=f"environment:{ref}", owner_system="system_l1", authority="mirror", status="fresh", summary={"derived_from_snapshot_ref": ref}),
            character=StateTreeNode(node_id=f"character:{ref}", owner_system="character_agent", authority="mirror", status="fresh", summary={"derived_from_snapshot_ref": ref}),
            storyline=StateTreeNode(node_id=f"storyline:{ref}", owner_system="siming", authority="editable", status="fresh", summary={"derived_from_snapshot_ref": ref}),
            group_simulation=GroupSimulationBranchSnapshot(status="fresh"),
        )
        storyline = StorylineStateSnapshot(snapshot_id=f"storyline:{ref}", schema_version=1, producer_system="siming.graph_projection", room_id=scope.room_id or "room:unknown", world_ts=context.request.valid_at, sim_tick_ts=context.request.valid_at, causation_id=ref, correlation_id=ref, active_phase="graph_compiled")
        read_model = NarrativeReadModel(read_model_id=f"read:{ref}", schema_version=1, producer_system="siming.graph_projection", room_id=scope.room_id or "room:unknown", scene_scope=f"{scope.scene_id or 'scene:unknown'}/graph", world_ts=context.request.valid_at, sim_tick_ts=context.request.valid_at, focus_entities=context.selected_node_refs, current_state={"context_hash": ref}, derived_from_snapshot_ref=ref)
        return SimingGraphProjectionBundle(state_tree=state_tree, storyline=storyline, read_model=read_model, debug_summary={"context_hash": ref, "truncated": context.truncated})
