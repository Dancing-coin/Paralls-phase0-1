from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_street_combat_profile_and_verifier_require_fresh_runtime_fields() -> None:
    profile = json.loads((ROOT / ".harness/profiles/street-combat.json").read_text(encoding="utf-8"))
    source = (ROOT / "scripts/verification/verify_street_combat.py").read_text(encoding="utf-8")
    assert profile["name"] == "street-combat"
    assert profile["script"] == "scripts/verification/verify_street_combat.py"
    for field in ("environment_loaded", "skeleton_bindings", "player_authority_hit", "agent_authority_hit", "duplicate_replayed", "stale_rejected", "recovery_committed", "hud_observed"):
        assert field in source


def test_street_combat_verifier_writes_artifact_into_current_harness_scope() -> None:
    source = (ROOT / "scripts/verification/verify_street_combat.py").read_text(encoding="utf-8")
    assert "EVIDENCE = ROOT / \".harness\" / \"verification\"" not in source
    assert "verification_dir(ROOT) / \"street-combat-runtime.json\"" in source
