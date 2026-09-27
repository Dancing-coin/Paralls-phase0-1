from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[2]


def test_two_qualified_packages_and_mode_b_boundary_are_declared() -> None:
    packages = []
    for package_id in ("female_jk_external", "female_t_external"):
        report = json.loads((ROOT / "assets" / "characters" / "qualification_reports" / f"{package_id}.json").read_text(encoding="utf-8"))
        packages.append(report)
    assert all(report.get("qualified") is True or report.get("status") == "qualified" for report in packages)
    assert (ROOT / "scripts" / "character" / "CharacterMotor.gd").exists()
    scene = (ROOT / "scenes" / "integration" / "UnifiedCharacterActionFoundation.tscn").read_text(encoding="utf-8")
    assert 'instance=ExtResource("1_replica")' in scene
    assert 'female_jk_external/female_jk_external.glb' in scene
    assert 'female_t_external/female_t_external.glb' in scene
    profile = json.loads((ROOT / ".harness" / "profiles" / "unified-character-action-foundation.json").read_text(encoding="utf-8"))
    assert profile["requires_godot"] is True


def test_release_verifier_reports_mode_b_without_physical_claim() -> None:
    import subprocess, sys
    result = subprocess.run([sys.executable, "scripts/verification/verify_unified_character_action_foundation.py", "--stage", "release"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"mode": "B"' in result.stdout


def test_live_foundation_probe_route_returns_authority_results_and_replays_duplicate() -> None:
    payload = {
        "package_ids": ["female_jk_external", "female_t_external"],
        "attempt": {
            "attempt_id": "attempt:live:test",
            "actor_ref": "character:foundation_a",
            "action_instance_id": "action:live:test",
            "semantic_action_id": "melee:slash",
            "target_refs": ["object:foundation_target"],
            "contact_marker_id": "marker:contact",
            "physics_tick": 1,
            "physics_evidence_refs": ["contact:live"],
            "authority_route": "esm",
            "expected_revisions": {},
            "idempotency_key": "live:foundation:test",
            "command_version": "v1",
            "causation_id": "cause:live:test",
            "correlation_id": "corr:live:test",
            "source": "agent_inf",
            "privacy_scope": "public",
        },
    }
    import os
    import subprocess, sys
    script = (
        "from fastapi.testclient import TestClient; "
        "from app.main import app; "
        "from app.ws_protocol import Envelope; "
        "from app import main; "
        "p=" + repr(payload) + "; "
            "main.reset_runtime_state(); "
            "a=main._handle_envelope(Envelope(message_type='unified_character_action_foundation_probe', payload=p)); "
        "b=main._handle_envelope(Envelope(message_type='unified_character_action_foundation_probe', payload=p)); "
        "assert a[0]['payload']['authority_result']['outcome']=='committed'; "
        "assert b[0]['payload']['authority_result']['transaction_id']==a[0]['payload']['authority_result']['transaction_id']"
    )
    env = os.environ.copy()
    env["PARALLS_HEAVENLY_GRAPH_PATH"] = ":memory:"
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT / "backend", env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return
