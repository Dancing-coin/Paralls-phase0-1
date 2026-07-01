from __future__ import annotations

from pathlib import Path

import pytest

from app.world_runtime.intelligence_upgrade import (
    ActorSceneKnowledgeEntry,
    BackpressurePolicy,
    CanonicalPerceptBundle,
    ESMDualChannelManifest,
    EmbodiedSkeletalStateBundle,
    FusionSpec,
    HighLevelEmbodiedState,
    InteractionIntentFrame,
    LowLevelBoneSnapshot,
    MidLevelSkeletalParameters,
    MultimodalCapabilityPlatform,
    MultimodalStackSpec,
    NonRuntimeStackManifest,
    PerceptionQueryFrame,
    SpatialOccupancyField,
    SampleInputRef,
    Scene3DSpaceModel,
    SceneSpaceElement,
    SimingGlobalSituationSpec,
    SlowPathAdvisorPolicy,
    SpatialReference,
    TimeWindow,
    VLAContract,
    assert_isolated_runtime_contexts,
    default_non_runtime_tooling_manifest,
    default_sampling_provider_manifests,
    orchestrate_interaction,
    plan_actor_scene_knowledge_update,
    FactProjectionLayerManifest,
)


ROOT = Path(__file__).resolve().parents[2]


def test_perception_query_frame_and_percept_protocol_enforce_context_isolation() -> None:
    frame = PerceptionQueryFrame(
        query_id="pqf:char_a:1",
        consumer_kind="character",
        subject_id="char_a",
        time_window=TimeWindow(started_at=10, ended_at=20),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="visual_patch:char_a:1")],
        structured_fact_refs=["visual_fact:1"],
        multimodal_context_id="character_mm:char_a",
        cache_namespace="character_mm:char_a:cache",
    )
    bundle = CanonicalPerceptBundle(
        bundle_id="bundle:char_a:1",
        consumer_kind="character",
        subject_id="char_a",
        query_id=frame.query_id,
        percept_context_id=frame.multimodal_context_id,
        structured_fact_refs=frame.structured_fact_refs,
    )

    assert bundle.raw_input_retention_policy == "refs_only"
    with pytest.raises(ValueError, match="character_mm"):
        PerceptionQueryFrame(
            query_id="pqf:bad",
            consumer_kind="character",
            subject_id="char_a",
            time_window=TimeWindow(started_at=1, ended_at=1),
            spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
            multimodal_context_id="siming_mm:room_demo",
            cache_namespace="siming_mm:room_demo:cache",
        )


def test_godot_sampling_frontend_declares_four_sampling_only_providers() -> None:
    manifests = default_sampling_provider_manifests()
    provider_kinds = {manifest.provider_kind for manifest in manifests}

    assert provider_kinds == {"visual_patch", "spatial_patch", "auditory_context", "embodied_state"}
    for manifest in manifests:
        text = (ROOT / manifest.godot_script).read_text(encoding="utf-8")
        assert "sampling_only" in text
        assert "feeds_query_frame" in text
        assert "heavy_inference_allowed := false" in text or "heavy_voxelization_allowed := false" in text
        assert "heavy_voxelization" in manifest.forbidden_responsibilities


def test_l1_world_fact_and_space_foundation_models_static_and_dynamic_space_without_runtime_rescan() -> None:
    space_model = Scene3DSpaceModel(
        model_id="scene_space:demo",
        room_id="room_demo",
        scene_id="scene_demo",
        elements=[
            SceneSpaceElement(
                element_id="zone_focus",
                element_type="zone",
                source_refs=["node:/Root/ZoneFocus"],
                semantic_tags=["playable_area"],
            )
        ],
    )
    occupancy = SpatialOccupancyField(field_id="occupancy:demo", static_model_ref=space_model.model_id)
    projection = FactProjectionLayerManifest()

    assert space_model.manual_role == "review_only"
    assert "node_names" in space_model.extraction_sources
    assert "full_scene_rescan" in occupancy.forbidden_runtime_work
    assert "line_of_sight_blocked" in projection.extension_fact_types["los_reachability"]
    assert "world_result" in projection.projected_fact_families


def test_character_multimodal_stack_and_actor_scene_knowledge_extend_mind_core_without_rewriting_it() -> None:
    stack = MultimodalStackSpec(
        owner_kind="character",
        owner_id="char_a",
        context_id="character_mm:char_a",
        patch_scope="actor_local",
        input_window="actor_local_short",
        allowed_inputs=["PerceptionQueryFrame", "CanonicalPerceptBundle", "ActorSceneKnowledge"],
        forbidden_inputs=["siming_mm:*", "other_actor_private_patch_cache"],
        backpressure_policy=BackpressurePolicy(timeout_ms=80),
    )
    fusion = FusionSpec(
        owner_kind="character",
        inputs=["L1_structured_facts", "character_multimodal_results", "body_feedback", "recent_failures"],
        output_bundle_kind="canonical_percept_bundle",
        forbidden_authority=["character_mind_core_rewrite", "world_truth_write"],
    )
    incoming = ActorSceneKnowledgeEntry(
        entry_id="ask:char_a:cover_1",
        actor_id="char_a",
        knowledge_type="occlusion",
        subject_ref="cover_1",
        summary="cover blocks sight from throne approach",
        source_refs=["pqf:char_a:1"],
        confidence=0.7,
    )
    update = plan_actor_scene_knowledge_update(existing_entry=None, incoming_entry=incoming)

    assert stack.context_id == "character_mm:char_a"
    assert "siming_mm:*" in stack.forbidden_inputs
    assert fusion.output_bundle_kind == "canonical_percept_bundle"
    assert "character_mind_core_rewrite" in fusion.forbidden_authority
    assert update.operation == "add_new"


def test_siming_multimodal_stack_enhances_fairness_without_polluting_character_context() -> None:
    character_stack = MultimodalStackSpec(
        owner_kind="character",
        owner_id="char_a",
        context_id="character_mm:char_a",
        patch_scope="actor_local",
        input_window="actor_local_short",
        allowed_inputs=["PerceptionQueryFrame"],
        backpressure_policy=BackpressurePolicy(timeout_ms=80),
    )
    siming_stack = MultimodalStackSpec(
        owner_kind="siming",
        owner_id="siming",
        context_id="siming_mm:room_demo",
        patch_scope="global_situation",
        input_window="siming_global_wide",
        allowed_inputs=["authority_event", "world_result", "visual_fact", "environment_state_result"],
        forbidden_inputs=["character_mm:*", "character_private_patch_cache"],
        backpressure_policy=BackpressurePolicy(timeout_ms=150, fallback_behavior="defer_to_next_tick"),
    )
    situation = SimingGlobalSituationSpec(context_id=siming_stack.context_id)

    assert assert_isolated_runtime_contexts([character_stack, siming_stack]) is True
    assert "FairnessStateSnapshot" in situation.enhances
    assert "low_level_character_motion" in situation.forbidden_actions


def test_interaction_orchestration_selects_channels_without_becoming_a_new_brain() -> None:
    semantic_decision = orchestrate_interaction(
        InteractionIntentFrame(intent_id="intent:inspect", actor_id="char_a", semantic_intent="inspect")
    )
    mixed_decision = orchestrate_interaction(
        InteractionIntentFrame(
            intent_id="intent:push",
            actor_id="char_a",
            semantic_intent="move_obstacle",
            physical_affordance="push",
        )
    )

    assert semantic_decision.selected_channels == ["semantic"]
    assert mixed_decision.selected_channels == ["semantic", "physical"]
    assert mixed_decision.result_merge_strategy == "semantic_goal_physical_effect_merge"
    assert "character_mind_core" in mixed_decision.forbidden_ownership


def test_esm_dual_channel_manifest_keeps_one_world_result_protocol() -> None:
    manifest = ESMDualChannelManifest()

    assert "investigation" in manifest.channels["semantic"]
    assert "continuous_contact" in manifest.channels["physical"]
    assert manifest.channel_selector_owner == "InteractionOrchestrationLayer"
    assert {
        "world_result",
        "object_state_result",
        "environment_state_result",
        "body_state_result",
        "constraint_state_result",
    }.issubset(set(manifest.unified_result_families))


def test_embodied_skeletal_state_provider_excludes_low_level_snapshot_from_main_chain() -> None:
    bundle = EmbodiedSkeletalStateBundle(
        provider_id="skeletal_provider:char_a",
        actor_id="char_a",
        high_level_state=HighLevelEmbodiedState(posture="standing", gait="idle", balance="stable"),
        mid_level_parameters=MidLevelSkeletalParameters(
            anchor_refs={"head": "bone:head", "right_hand": "bone:hand_r"},
            reach_envelope="short",
        ),
        low_level_snapshot=LowLevelBoneSnapshot(snapshot_ref="debug:skeleton:1", bone_count=64),
    )
    provider_text = (ROOT / "scripts" / "character" / "EmbodiedSkeletalStateProvider.gd").read_text(encoding="utf-8")

    assert bundle.low_level_snapshot is not None
    assert "low_level_snapshot" not in bundle.main_perception_chain_payload()
    assert "debug_replay_only" in provider_text
    assert "full_bone_snapshot_to_backend_allowed := false" in provider_text


def test_vla_multimodal_upgrade_places_vla_as_non_blocking_subchain() -> None:
    platform = MultimodalCapabilityPlatform()
    contract = VLAContract()
    slow_path = SlowPathAdvisorPolicy()

    assert "output_schema" in platform.shared_interfaces
    assert "inference_history" in platform.forbidden_shared_runtime_state
    assert contract.role == "spatial_visual_understanding_subchain"
    assert "global_brain" in contract.forbidden_roles
    assert slow_path.backpressure_policy.affects_current_tick is False


def test_non_runtime_multimodal_tooling_uses_tool_contexts_and_review_only_human_role() -> None:
    manifests = default_non_runtime_tooling_manifest()

    assert {manifest.stack_kind for manifest in manifests} == {"tool", "production"}
    assert all(manifest.context_id.startswith("tool_mm:") for manifest in manifests)
    assert all(manifest.shares_runtime_context is False for manifest in manifests)
    assert any("SceneSemanticExtractor" in manifest.modules for manifest in manifests)
    with pytest.raises(ValueError, match="must not share runtime"):
        NonRuntimeStackManifest(
            stack_kind="tool",
            context_id="tool_mm:bad",
            modules=["ReviewWorkbench"],
            shares_runtime_context=True,
        )
