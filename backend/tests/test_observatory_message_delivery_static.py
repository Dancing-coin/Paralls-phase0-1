from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_backend_emits_full_observatory_message_family() -> None:
    main_source = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")

    assert '"message_type": "character_agent_debug_snapshot"' in main_source
    assert '"message_type": "character_agent_debug_event"' in main_source
    assert '"message_type": "siming_debug_snapshot"' in main_source
    assert '"message_type": "siming_debug_event"' in main_source
    assert '"message_type": "world_outcome_trace"' in main_source
    assert '"message_type": "script_beat_event"' in main_source


def test_backend_bridge_and_local_presentation_bus_expose_observatory_signal_chain() -> None:
    bus_source = (ROOT / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(
        encoding="utf-8"
    )
    bridge_source = (ROOT / "scripts" / "autoload" / "BackendBridge.gd").read_text(
        encoding="utf-8"
    )

    assert "signal character_agent_debug_snapshot_received(payload)" in bus_source
    assert "signal character_agent_debug_event_received(payload)" in bus_source
    assert "signal siming_debug_snapshot_received(payload)" in bus_source
    assert "signal siming_debug_event_received(payload)" in bus_source
    assert "signal world_outcome_trace_received(payload)" in bus_source
    assert "signal script_beat_event_received(payload)" in bus_source
    assert '"character_agent_debug_snapshot":' in bridge_source
    assert '"character_agent_debug_event":' in bridge_source
    assert '"siming_debug_snapshot":' in bridge_source
    assert '"siming_debug_event":' in bridge_source
    assert '"world_outcome_trace":' in bridge_source
    assert '"script_beat_event":' in bridge_source
