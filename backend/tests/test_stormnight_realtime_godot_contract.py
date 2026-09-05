from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_realtime_scene_is_independent_player_shell_and_primitive_actor_vertical() -> None:
    scene = (ROOT / "scenes" / "phase0" / "StormnightRealtimePlayable.tscn").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "phase0" / "StormnightRealtimePlayable.gd").read_text(encoding="utf-8")
    assert "StormnightRealtimePlayable.gd" in scene
    assert "PlayerShell.tscn" in script
    assert "ProceduralLowPolyCharacter.tscn" in script
    assert script.count('"actor_ref"') >= 4
    assert "stormnight_player_intent" in script
    assert "stormnight_case_projection" in script
    assert '"ws://127.0.0.1:8000/ws"' in script
    assert "StormnightPlayerAvatar" in script
    assert "ThroneHall" not in script
    assert "KnightRoleSkin" not in script
    assert "crusader_knight" not in script


def test_realtime_client_is_finite_intent_and_committed_response_only() -> None:
    script = (ROOT / "scripts" / "phase0" / "StormnightRealtimePlayable.gd").read_text(encoding="utf-8")
    for action in ("start", "inspect", "advance", "question", "hide", "pursue", "accuse"):
        assert f'"{action}"' in script
    assert "_on_case_projection" in script
    assert "_restore_committed_actor_state" in script
    assert "append_batch" not in script
    assert "GameplayEventStore" not in script


def test_bridge_and_bus_route_only_server_issued_case_projection() -> None:
    bridge = (ROOT / "scripts" / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")
    bus = (ROOT / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(encoding="utf-8")
    assert '"stormnight_case_projection"' in bridge
    assert "stormnight_case_projection_received" in bridge
    assert "signal stormnight_case_projection_received(payload)" in bus
