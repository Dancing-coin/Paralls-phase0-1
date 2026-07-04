from __future__ import annotations

from pathlib import Path

from app.world_runtime.intelligence_upgrade import (
    EmbodiedSkeletalStateBundle,
    HighLevelEmbodiedState,
    LowLevelBoneSnapshot,
    MidLevelSkeletalParameters,
    PerceptionQueryFrame,
    SampleInputRef,
    SpatialReference,
    TimeWindow,
)


ROOT = Path(__file__).resolve().parents[2]


def test_high_and_mid_level_skeletal_state_enters_main_payload_without_low_level_snapshot() -> None:
    bundle = EmbodiedSkeletalStateBundle(
        provider_id="skeletal_provider:char_b",
        actor_id="char_b",
        high_level_state=HighLevelEmbodiedState(
            posture="standing",
            gait="idle",
            balance="stable",
            strain="nominal",
            active_behavior="runtime_probe",
            hand_readiness="available",
        ),
        mid_level_parameters=MidLevelSkeletalParameters(
            anchor_refs={"actor_root": "runtime://node/PlayerCharacter", "skeleton": "runtime://node/Skeleton3D"},
            facing_vectors={"actor_forward": [0.0, 0.0, -1.0]},
            reach_envelope="arm_length_local",
            balance_hints=["center_of_mass_within_support"],
            strain_hints=["no_high_strain"],
            hand_readiness={"left": "available", "right": "available"},
            contact_candidate_refs=["runtime://contact_candidate/char_b/floor"],
            pose_features=["standing", "hands_available"],
        ),
        low_level_snapshot=LowLevelBoneSnapshot(snapshot_ref="runtime://artifact/skeletal-replay-char_b.json", bone_count=81),
    )

    payload = bundle.main_perception_chain_payload()

    assert "low_level_snapshot" not in payload
    assert payload["mid_level_parameters"]["anchor_refs"]["skeleton"] == "runtime://node/Skeleton3D"
    assert payload["mid_level_parameters"]["facing_vectors"]["actor_forward"] == [0.0, 0.0, -1.0]
    assert payload["mid_level_parameters"]["reach_envelope"] == "arm_length_local"
    assert payload["mid_level_parameters"]["balance_hints"] == ["center_of_mass_within_support"]
    assert payload["mid_level_parameters"]["strain_hints"] == ["no_high_strain"]
    assert payload["mid_level_parameters"]["hand_readiness"]["right"] == "available"
    assert payload["mid_level_parameters"]["contact_candidate_refs"] == ["runtime://contact_candidate/char_b/floor"]
    assert payload["mid_level_parameters"]["pose_features"] == ["standing", "hands_available"]


def test_skeletal_refs_can_enter_pqf_with_debug_replay_retention() -> None:
    frame = PerceptionQueryFrame(
        query_id="pqf:char_b:skeletal",
        consumer_kind="character",
        subject_id="char_b",
        time_window=TimeWindow(started_at=0, ended_at=1),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        skeletal_inputs=[
            SampleInputRef(
                provider_kind="skeletal_state",
                ref_id="runtime://embodied_skeletal/char_b/high_mid/1",
                retention="ref_only",
                runtime_source_refs=[
                    "runtime://embodied_skeletal/char_b/high_mid/1",
                    "runtime://artifact/.harness/verification/skeletal-replay-char_b.json",
                ],
                stable_source_ref="runtime://embodied_skeletal/char_b",
                sample_status="ok",
                freshness="fresh",
                throttle_state="allowed",
                failure_status="none",
            )
        ],
        multimodal_context_id="character_mm:char_b",
        cache_namespace="character_mm:char_b:skeletal_cache",
    )
    debug_snapshot = LowLevelBoneSnapshot(snapshot_ref="runtime://artifact/.harness/verification/skeletal-replay-char_b.json", bone_count=81)

    assert frame.skeletal_inputs[0].provider_kind == "skeletal_state"
    assert debug_snapshot.retention == "debug_replay_only"
    assert debug_snapshot.snapshot_ref in frame.skeletal_inputs[0].runtime_source_refs


def test_godot_provider_script_has_runtime_binding_and_debug_replay_hooks() -> None:
    text = (ROOT / "scripts/character/EmbodiedSkeletalStateProvider.gd").read_text(encoding="utf-8")
    probe_text = (ROOT / "scripts/verification/EmbodiedSkeletalRuntimeProbe.gd").read_text(encoding="utf-8")

    assert "bind_runtime" in text
    assert "_find_character_replica" in text
    assert "_find_first_skeleton" in text
    assert "write_debug_snapshot_artifact" in text
    assert "debug_replay_only" in text
    assert "full_bone_snapshot_to_backend_allowed := false" in text
    assert "CharacterReplica" in text
    assert "Skeleton3D" in text
    assert "full_bone_main_chain_excluded" in probe_text
