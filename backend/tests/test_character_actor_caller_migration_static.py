from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_embodied_providers_resolve_actor_capabilities_without_replica_lookup() -> None:
    provider = _read("scripts/character/EmbodiedStateProvider.gd")
    skeletal = _read("scripts/character/EmbodiedSkeletalStateProvider.gd")

    for source in (provider, skeletal):
        assert "CharacterReplica" not in source
        assert "_find_character_replica" not in source
        assert "apply_control_intent" in source
        assert "get_focus_anchor_position" in source
        assert "get_embodied_forward_vector" in source


def test_archive_door_host_uses_actor_capability_path_and_fails_closed() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")

    assert 'var character_actor_path := NodePath("../CharacterActor")' in host
    assert "func _character_actor()" in host
    assert "CharacterReplica" not in host
    assert "capability_unavailable" in host
    assert "apply_control_intent" in host
    assert "get_focus_anchor_position" in host
    assert "get_embodied_forward_vector" in host


def test_embodied_runtime_probes_report_actor_ingress_without_replica_nodes() -> None:
    skeletal_probe = _read("scripts/verification/EmbodiedSkeletalRuntimeProbe.gd")
    door_probe = _read("scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd")
    caller_probe = _read("scripts/verification/CharacterActorCallerMigrationProbe.gd")

    assert "CharacterReplica" not in skeletal_probe
    assert "CharacterReplica" not in door_probe
    assert "CharacterReplica" not in caller_probe
    assert "apply_control_intent" in skeletal_probe
    assert "apply_control_intent" in door_probe
    assert "ingress_source" in caller_probe
    assert "provider_lookup_count" in caller_probe
    assert "compatibility_call_count" in caller_probe

