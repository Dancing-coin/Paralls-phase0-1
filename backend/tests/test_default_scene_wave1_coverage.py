from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_wave_one_keeps_only_named_reviewed_default_scene_fixtures() -> None:
    main_scene = _read("scenes/phase0/MainDemo.tscn")
    controller = _read("scripts/phase0/MainDemoController.gd")
    affordance_bridge = _read("scripts/interaction/DefaultSceneLetterAffordanceBridge.gd")

    fixtures = {
        "obj_plaque": "affordance:obj_plaque:inspect",
        "obj_lamp_switch": "affordance:obj_lamp_switch:press",
        "obj_archive_door": "affordance:obj_archive_door:open_close",
        "obj_worktable": "affordance:obj_worktable:use_surface",
        "obj_observation_bench": "affordance:obj_observation_bench:seat",
        "obj_archive_token": "affordance:obj_archive_token:grab",
        "obj_archive_storage_chest": "affordance:obj_archive_storage_chest:retrieve",
    }
    for object_id, affordance_id in fixtures.items():
        assert f'object_id = "{object_id}"' in main_scene
        assert f'affordance_id = "{affordance_id}"' in main_scene
        assert f"collider:{object_id}:body" in main_scene
        assert f"anchor:{object_id}:stance" in main_scene
        assert f"anchor:{object_id}:observation" in main_scene
    # The compatibility instance intentionally inherits its reviewed identity
    # and constructs the record refs from that stable identifier.
    assert 'object_id := "obj_letter"' in affordance_bridge
    assert 'affordance_id := "affordance:obj_letter:inspect"' in affordance_bridge
    assert '"collider:%s:body" % object_id' in affordance_bridge
    assert '"anchor:%s:stance" % object_id' in affordance_bridge
    assert '"anchor:%s:observation" % object_id' in affordance_bridge
    assert "phase0_interact_registry_rejected" in controller


def test_wave_one_presentation_waits_for_authority_only_results() -> None:
    affordance_bridge = _read("scripts/interaction/DefaultSceneLetterAffordanceBridge.gd")
    pickup_bridge = _read("scripts/interaction/DefaultScenePickupPresentationBridge.gd")

    assert '"object_state_result"' in affordance_bridge
    assert "world_truth" not in affordance_bridge
    assert "authority_only" in pickup_bridge
    assert "presentation_state = \"carried\"" in pickup_bridge
    assert "if not bool(payload.get(\"accepted\", false))" in pickup_bridge
