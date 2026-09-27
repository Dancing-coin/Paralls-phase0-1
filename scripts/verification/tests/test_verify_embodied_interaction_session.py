from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_live_session_probe_window_covers_async_backend_terminal_evidence() -> None:
    source = (ROOT / "verification" / "verify_embodied_interaction_session.py").read_text(encoding="utf-8")
    assert 'timeout_seconds=30' in source
    assert '"--quit-after"' not in source


def test_live_session_probe_uses_cursor_pulls_for_one_event_per_transport_round_trip() -> None:
    probe = (ROOT / "verification" / "EmbodiedInteractionSessionProbe.gd").read_text(encoding="utf-8")

    assert '"message_type": "embodied_interaction_session_projection_pull"' in probe
    assert '"after_global_sequence": cursor' in probe
    assert "live_consumer.last_global_sequence > cursor" in probe
