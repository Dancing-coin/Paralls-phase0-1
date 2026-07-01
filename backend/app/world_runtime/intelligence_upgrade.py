from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ConsumerKind = Literal["character", "siming", "non_runtime_tool", "non_runtime_production"]
ProviderKind = Literal["visual_patch", "spatial_patch", "auditory_context", "embodied_state"]
ModalityKind = Literal["visual_spatial", "auditory", "embodied", "environmental"]
InteractionChannel = Literal["semantic", "physical"]


class TimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    started_at: int
    ended_at: int
    cadence: Literal["frame", "short_window", "slow_path"] = "short_window"

    @model_validator(mode="after")
    def validate_window_order(self) -> "TimeWindow":
        if self.ended_at < self.started_at:
            raise ValueError("time window ended_at must be >= started_at")
        return self


class SpatialReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: str
    scene_id: str
    zone_id: str
    actor_frame_ref: str = ""
    camera_frame_ref: str = ""
    listener_frame_ref: str = ""
    coordinate_space: Literal["godot_world", "actor_local", "siming_global"] = "godot_world"


class AttentionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_actor_ids: list[str] = Field(default_factory=list)
    target_object_ids: list[str] = Field(default_factory=list)
    target_environment_ids: list[str] = Field(default_factory=list)
    reason_tags: list[str] = Field(default_factory=list)


class SampleInputRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_kind: ProviderKind
    ref_id: str
    summary: str = ""
    retention: Literal["ref_only", "debug_artifact"] = "ref_only"


class PerceptionQueryFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str
    consumer_kind: ConsumerKind
    subject_id: str
    time_window: TimeWindow
    spatial_reference: SpatialReference
    attention_context: AttentionContext = Field(default_factory=AttentionContext)
    visual_inputs: list[SampleInputRef] = Field(default_factory=list)
    spatial_inputs: list[SampleInputRef] = Field(default_factory=list)
    auditory_inputs: list[SampleInputRef] = Field(default_factory=list)
    embodied_inputs: list[SampleInputRef] = Field(default_factory=list)
    environment_inputs: list[SampleInputRef] = Field(default_factory=list)
    structured_fact_refs: list[str] = Field(default_factory=list)
    multimodal_context_id: str
    cache_namespace: str
    inference_history_ref: str = ""

    @model_validator(mode="after")
    def validate_runtime_context_boundary(self) -> "PerceptionQueryFrame":
        if self.consumer_kind == "character" and not self.multimodal_context_id.startswith("character_mm:"):
            raise ValueError("character perception frames must use a character_mm context")
        if self.consumer_kind == "siming" and not self.multimodal_context_id.startswith("siming_mm:"):
            raise ValueError("siming perception frames must use a siming_mm context")
        if self.consumer_kind.startswith("non_runtime") and not self.multimodal_context_id.startswith("tool_mm:"):
            raise ValueError("non-runtime perception frames must use a tool_mm context")
        if "shared" in self.multimodal_context_id or "shared" in self.cache_namespace:
            raise ValueError("runtime multimodal context/cache namespaces must not be shared")
        return self


class ModalityInterpretationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    query_id: str
    modality: ModalityKind
    findings: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_inputs: list[str] = Field(default_factory=list)
    conflict_refs: list[str] = Field(default_factory=list)


class CrossModalUnderstandingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    query_id: str
    world_hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    confidence_adjustments: dict[str, float] = Field(default_factory=dict)
    modality_conflicts: list[str] = Field(default_factory=list)
    missing_modalities: list[ModalityKind] = Field(default_factory=list)
    attention_updates: list[str] = Field(default_factory=list)


class CanonicalPerceptBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    consumer_kind: ConsumerKind
    subject_id: str
    query_id: str
    percept_context_id: str
    local_spatial_state: dict[str, Any] = Field(default_factory=dict)
    target_state: dict[str, Any] = Field(default_factory=dict)
    environment_state: dict[str, Any] = Field(default_factory=dict)
    embodied_state: dict[str, Any] = Field(default_factory=dict)
    attention_state: dict[str, Any] = Field(default_factory=dict)
    world_hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    structured_fact_refs: list[str] = Field(default_factory=list)
    uncertainty: dict[str, Any] = Field(default_factory=dict)
    raw_input_retention_policy: Literal["refs_only"] = "refs_only"

    @model_validator(mode="after")
    def validate_percept_context_boundary(self) -> "CanonicalPerceptBundle":
        if self.consumer_kind == "character" and not self.percept_context_id.startswith("character_mm:"):
            raise ValueError("character percept bundles must stay in character_mm context")
        if self.consumer_kind == "siming" and not self.percept_context_id.startswith("siming_mm:"):
            raise ValueError("siming percept bundles must stay in siming_mm context")
        return self


class SamplingProviderManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_kind: ProviderKind
    godot_script: str
    output_fields: list[str]
    forbidden_responsibilities: list[str] = Field(
        default_factory=lambda: ["heavy_voxelization", "heavy_scene_scan", "large_model_inference"]
    )
    throttling_policy: str = "on_demand_local_window"
    feeds_query_frame: bool = True


def default_sampling_provider_manifests() -> list[SamplingProviderManifest]:
    return [
        SamplingProviderManifest(
            provider_kind="visual_patch",
            godot_script="scripts/character/VisualPatchProvider.gd",
            output_fields=["view_patch_ref", "target_patch_ref", "camera_pose"],
        ),
        SamplingProviderManifest(
            provider_kind="spatial_patch",
            godot_script="scripts/character/SpatialPatchProvider.gd",
            output_fields=["occupancy_patch_ref", "bev_patch_ref", "obstacle_refs", "occlusion_refs"],
        ),
        SamplingProviderManifest(
            provider_kind="auditory_context",
            godot_script="scripts/character/AuditoryContextProvider.gd",
            output_fields=["time_window", "source_refs", "reachability", "ambient_noise"],
        ),
        SamplingProviderManifest(
            provider_kind="embodied_state",
            godot_script="scripts/character/EmbodiedStateProvider.gd",
            output_fields=["pose", "locomotion_state", "grounded", "los_failure", "reachability_failure"],
        ),
    ]


SpaceElementType = Literal[
    "zone",
    "portal",
    "static_obstacle",
    "occluder",
    "environment_anchor",
    "interaction_object",
    "navigation_lane",
]


class SceneSpaceElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element_id: str
    element_type: SpaceElementType
    source_refs: list[str]
    semantic_tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Scene3DSpaceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    room_id: str
    scene_id: str
    extraction_sources: list[str] = Field(
        default_factory=lambda: [
            "node_names",
            "child_node_structure",
            "resource_paths",
            "collision_shapes",
            "navigation_regions",
            "environment_nodes",
        ]
    )
    manual_role: Literal["review_only"] = "review_only"
    elements: list[SceneSpaceElement] = Field(default_factory=list)


class OccupancyCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str
    zone_id: str
    occupancy: Literal["free", "occupied", "blocked", "unknown"]
    passability: Literal["passable", "blocked", "requires_detour", "unknown"]
    dynamic_source_refs: list[str] = Field(default_factory=list)
    updated_at: int


class RuntimeSpatialOccupancyField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    static_model_ref: str
    generation_strategy: Literal["static_offline_dynamic_incremental"] = "static_offline_dynamic_incremental"
    dynamic_cells: list[OccupancyCell] = Field(default_factory=list)
    forbidden_runtime_work: list[str] = Field(default_factory=lambda: ["full_scene_rescan", "heavy_voxelization"])


class FactProjectionLayerManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_foundations: list[str] = Field(
        default_factory=lambda: ["Scene3DSpaceModel", "RuntimeSpatialOccupancyField", "EnvironmentFieldModel"]
    )
    projected_fact_families: list[str] = Field(
        default_factory=lambda: [
            "raw_fact_event",
            "visual_fact",
            "auditory_fact",
            "spatial_access_fact",
            "world_result",
            "state_machine_transition",
        ]
    )
    extension_fact_types: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "environment": ["light_level_restore", "visibility_drop", "visibility_restore", "smoke_occlusion"],
            "los_reachability": [
                "line_of_sight_blocked",
                "line_of_sight_restored",
                "target_unreachable",
                "path_detour_required",
            ],
            "affordance": ["grabbable", "immovable", "interaction_affordance_changed"],
            "negative": ["expected_target_missing", "expected_reachable_but_failed", "auditory_signal_unclear"],
        }
    )


class BackpressurePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: int
    affects_current_tick: bool = False
    fallback_behavior: Literal["use_structured_facts", "defer_to_next_tick", "debug_only"] = "defer_to_next_tick"


class MultimodalCapabilityPlatform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shared_interfaces: list[str] = Field(
        default_factory=lambda: ["model_registry", "input_encoding", "output_schema", "scheduling", "tracing"]
    )
    forbidden_shared_runtime_state: list[str] = Field(
        default_factory=lambda: ["patch_context", "private_cache", "inference_history", "hidden_state"]
    )


class MultimodalStackSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_kind: ConsumerKind
    owner_id: str
    context_id: str
    patch_scope: str
    input_window: Literal["actor_local_short", "siming_global_wide", "non_runtime_batch"]
    allowed_inputs: list[str]
    forbidden_inputs: list[str] = Field(default_factory=list)
    backpressure_policy: BackpressurePolicy

    @model_validator(mode="after")
    def validate_stack_context(self) -> "MultimodalStackSpec":
        expected_prefix = {
            "character": "character_mm:",
            "siming": "siming_mm:",
            "non_runtime_tool": "tool_mm:",
            "non_runtime_production": "tool_mm:",
        }[self.owner_kind]
        if not self.context_id.startswith(expected_prefix):
            raise ValueError(f"{self.owner_kind} stack context must start with {expected_prefix}")
        if "shared" in self.context_id:
            raise ValueError("multimodal stack contexts must not be shared")
        return self


class ActorSceneKnowledgeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    actor_id: str
    knowledge_type: Literal["space", "obstacle", "occlusion", "path", "environment", "affordance"]
    subject_ref: str
    summary: str
    source_refs: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: Literal["fresh", "stale", "contested"] = "fresh"
    conflict_refs: list[str] = Field(default_factory=list)

    @property
    def conflict_state(self) -> Literal["clear", "conflicted"]:
        return "conflicted" if self.conflict_refs else "clear"


class ActorSceneKnowledgeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["hit_existing", "revise_existing", "add_new", "record_conflict"]
    entry: ActorSceneKnowledgeEntry
    active_perception_requests: list[str] = Field(default_factory=list)


def plan_actor_scene_knowledge_update(
    *,
    existing_entry: ActorSceneKnowledgeEntry | None,
    incoming_entry: ActorSceneKnowledgeEntry,
    confidence_delta_threshold: float = 0.2,
) -> ActorSceneKnowledgeUpdate:
    if existing_entry is None:
        return ActorSceneKnowledgeUpdate(operation="add_new", entry=incoming_entry)
    if existing_entry.subject_ref != incoming_entry.subject_ref:
        return ActorSceneKnowledgeUpdate(operation="record_conflict", entry=incoming_entry)
    if abs(existing_entry.confidence - incoming_entry.confidence) >= confidence_delta_threshold:
        return ActorSceneKnowledgeUpdate(operation="revise_existing", entry=incoming_entry)
    return ActorSceneKnowledgeUpdate(operation="hit_existing", entry=existing_entry)


class FusionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_kind: Literal["character", "siming"]
    inputs: list[str]
    output_bundle_kind: Literal["canonical_percept_bundle", "siming_percept_bundle"]
    forbidden_authority: list[str]


class SimingGlobalSituationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str
    patch_scope: Literal["multi_actor_global_situation"] = "multi_actor_global_situation"
    enhances: list[str] = Field(
        default_factory=lambda: ["FairnessStateSnapshot", "intervention_candidates", "minimal_catalyst_path", "workbench_explanation"]
    )
    forbidden_actions: list[str] = Field(
        default_factory=lambda: ["low_level_character_motion", "physical_world_truth_write", "final_character_behavior_choice"]
    )

    @model_validator(mode="after")
    def validate_siming_context(self) -> "SimingGlobalSituationSpec":
        if not self.context_id.startswith("siming_mm:"):
            raise ValueError("Siming global situation context must use siming_mm namespace")
        return self


class VLAContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["spatial_visual_understanding_subchain"] = "spatial_visual_understanding_subchain"
    accepted_inputs: list[str] = Field(default_factory=lambda: ["visual_patch_ref", "spatial_patch_ref", "bev_patch_ref"])
    outputs: list[str] = Field(default_factory=lambda: ["structured_spatial_understanding", "optional_text_summary"])
    forbidden_roles: list[str] = Field(default_factory=lambda: ["global_brain", "authority_owner", "character_mind_core_replacement"])


class SlowPathAdvisorPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_conditions: list[str] = Field(
        default_factory=lambda: ["high_ambiguity", "cross_modal_conflict", "low_confidence_global_situation"]
    )
    backpressure_policy: BackpressurePolicy = Field(
        default_factory=lambda: BackpressurePolicy(timeout_ms=250, affects_current_tick=False)
    )


class InteractionIntentFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_id: str
    actor_id: str
    target_refs: dict[str, list[str]] = Field(default_factory=dict)
    semantic_intent: str
    physical_affordance: str = ""
    gameplay_mode: str = "default"
    performance_budget: Literal["low", "normal", "high"] = "normal"


class InteractionOrchestrationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    intent_id: str
    selected_channels: list[InteractionChannel]
    channel_roles: dict[InteractionChannel, str]
    result_merge_strategy: Literal["semantic_only", "physical_only", "semantic_goal_physical_effect_merge"]
    forbidden_ownership: list[str] = Field(default_factory=lambda: ["character_mind_core", "siming_main_brain", "world_truth_authority"])


def orchestrate_interaction(intent: InteractionIntentFrame) -> InteractionOrchestrationDecision:
    if intent.physical_affordance in {"push", "pull", "carry", "grab", "continuous_contact"}:
        return InteractionOrchestrationDecision(
            decision_id=f"interaction_decision:{intent.intent_id}",
            intent_id=intent.intent_id,
            selected_channels=["semantic", "physical"],
            channel_roles={
                "semantic": "resolve_goal_constraints_and_cognitive_feedback",
                "physical": "apply_continuous_or_contact_world_effect",
            },
            result_merge_strategy="semantic_goal_physical_effect_merge",
        )
    return InteractionOrchestrationDecision(
        decision_id=f"interaction_decision:{intent.intent_id}",
        intent_id=intent.intent_id,
        selected_channels=["semantic"],
        channel_roles={"semantic": "resolve_rule_led_interaction_and_world_result"},
        result_merge_strategy="semantic_only",
    )


class ESMDualChannelManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channels: dict[InteractionChannel, list[str]] = Field(
        default_factory=lambda: {
            "semantic": ["dialogue", "investigation", "light_interaction", "story_trigger", "rule_led_environment_request"],
            "physical": ["push", "pull", "carry", "grab", "blocking", "continuous_contact", "body_weapon_contact"],
        }
    )
    shared_foundations: list[str] = Field(
        default_factory=lambda: ["world_state_foundation", "world_result_protocol", "cognitive_feedback_interface"]
    )
    unified_result_families: list[str] = Field(
        default_factory=lambda: [
            "world_result",
            "object_state_result",
            "environment_state_result",
            "body_state_result",
            "constraint_state_result",
        ]
    )
    channel_selector_owner: Literal["InteractionOrchestrationLayer"] = "InteractionOrchestrationLayer"


class HighLevelEmbodiedState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    posture: str
    gait: str = ""
    balance: str = ""
    strain: str = ""
    active_behavior: str = ""
    hand_readiness: str = ""


class MidLevelSkeletalParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_refs: dict[str, str] = Field(default_factory=dict)
    facing_vectors: dict[str, list[float]] = Field(default_factory=dict)
    reach_envelope: str = ""
    pose_features: list[str] = Field(default_factory=list)


class LowLevelBoneSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_ref: str
    bone_count: int
    retention: Literal["debug_replay_only"] = "debug_replay_only"


class EmbodiedSkeletalStateBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    actor_id: str
    high_level_state: HighLevelEmbodiedState
    mid_level_parameters: MidLevelSkeletalParameters
    low_level_snapshot: LowLevelBoneSnapshot | None = None

    def main_perception_chain_payload(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "actor_id": self.actor_id,
            "high_level_state": self.high_level_state.model_dump(),
            "mid_level_parameters": self.mid_level_parameters.model_dump(),
        }


class NonRuntimeStackManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stack_kind: Literal["tool", "production"]
    context_id: str
    modules: list[str]
    shared_platform_allowed: bool = True
    shares_runtime_context: bool = False

    @model_validator(mode="after")
    def validate_tool_context(self) -> "NonRuntimeStackManifest":
        if not self.context_id.startswith("tool_mm:"):
            raise ValueError("non-runtime tool stacks must use tool_mm context namespace")
        if self.shares_runtime_context:
            raise ValueError("non-runtime stacks must not share runtime character or Siming contexts")
        return self


def default_non_runtime_tooling_manifest() -> list[NonRuntimeStackManifest]:
    return [
        NonRuntimeStackManifest(
            stack_kind="tool",
            context_id="tool_mm:review_replay_analysis",
            modules=["ReviewWorkbench", "DatasetAndReplayBuilder"],
        ),
        NonRuntimeStackManifest(
            stack_kind="production",
            context_id="tool_mm:production_scene_knowledge",
            modules=[
                "SceneSemanticExtractor",
                "SpatialStructureBaker",
                "MultimodalSemanticClassifier",
                "SceneKnowledgeGenerator",
            ],
        ),
    ]


def assert_isolated_runtime_contexts(stacks: list[MultimodalStackSpec | NonRuntimeStackManifest]) -> bool:
    context_ids = [stack.context_id for stack in stacks]
    if len(context_ids) != len(set(context_ids)):
        raise ValueError("multimodal runtime contexts must be unique")
    for context_id in context_ids:
        if "shared" in context_id:
            raise ValueError("multimodal runtime contexts must not use shared namespaces")
    return True
