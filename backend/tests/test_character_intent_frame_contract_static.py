from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_tag_contract_freezes_allowed_namespaces_and_authority_gate() -> None:
    source = _read("scripts/character/CharacterTagContract.gd")
    for namespace in (
        "goal", "intent", "evidence", "capability", "affordance", "constraint",
        "state", "status", "action", "phase", "occupy", "event", "authority",
        "presentation", "expression",
    ):
        assert '"%s"' % namespace in source
    assert "authority_committed" in source


def test_ingress_contract_normalizes_proposals_without_world_writes() -> None:
    proposal = _read("scripts/character/IntentProposal.gd")
    port = _read("scripts/character/CharacterControllerPort.gd")
    layer = _read("scripts/character/LayerControlProposal.gd")
    for forbidden in ("damage", "hit_result", "inventory_mutation", "status_write", "transform", "velocity"):
        assert '"%s"' % forbidden in proposal
    assert "submit_intent_proposal" in port
    assert "from_intent" in layer


def test_frame_and_runtime_state_keep_authority_projection_separate() -> None:
    frame = _read("scripts/character/CharacterIntentFrame.gd")
    state = _read("scripts/character/CharacterRuntimeState.gd")
    assert "static func build(physics_tick" in frame
    assert "apply_authority_result" in state
    assert "latest_authority_result" in state
    assert "pending_attempts" in state
