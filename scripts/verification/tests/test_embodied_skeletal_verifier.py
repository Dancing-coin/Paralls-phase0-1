import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_embodied_skeletal_debug_replay_pipeline import _runtime_binding_ok


def test_runtime_binding_requires_actor_skeleton_and_bones():
    binding = {"runtime_binding_verified": True, "actor_node_path": "/root/CharacterActor",
               "skeleton_path": "/root/CharacterActor/Skeleton3D", "bone_count": 1}
    payload = {"main_perception_payload": {"runtime_binding": binding}}
    assert _runtime_binding_ok(payload)
    binding["actor_node_path"] = ""
    assert not _runtime_binding_ok(payload)
