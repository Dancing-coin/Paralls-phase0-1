from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_presentation_has_only_committed_state_mapping_and_rollback() -> None:
    script = (ROOT / "scripts" / "verification" / "ProceduralLowPolyCharacter.gd").read_text(encoding="utf-8")
    for method in ("apply_committed_state", "apply_speculative_state", "clear_speculative_state"):
        assert f"func {method}" in script
    for state in ("idle", "observe", "hide", "pursue", "controlled", "returned"):
        assert f'"{state}"' in script
    assert "event_vector" not in script
    assert "private_fact" not in script


def test_stormnight_probe_maps_committed_projection_to_actors_without_backend_writes() -> None:
    probe = (ROOT / "scripts" / "verification" / "StormnightCopperSanatoriumProbe.gd").read_text(encoding="utf-8")
    assert "_apply_committed_actor_state" in probe
    assert "apply_committed_state" in probe
    assert "append_batch" not in probe
    assert "BackendBridge" not in probe
