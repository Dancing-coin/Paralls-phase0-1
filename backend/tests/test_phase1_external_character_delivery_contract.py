from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ROOT / "assets" / "active"
REPORTS = ROOT / "assets" / "characters" / "qualification_reports"


def _manifest(package_id: str) -> dict:
    path = ACTIVE / package_id / "manifest.json"
    assert path.is_file(), f"missing package manifest: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_two_external_packages_declare_provenance_and_runtime_contract() -> None:
    manifests = [_manifest("crusader_knight"), _manifest("external_character_b")]
    assert {m["package_id"] for m in manifests} == {"crusader_knight", "external_character_b"}
    for manifest in manifests:
        assert manifest["source"]["model_path"]
        assert len(manifest["source"]["digest_sha256"]) == 64
        assert manifest["provenance"]["source_uri"]
        assert manifest["provenance"]["qualification_report_ref"]
        assert manifest["canonical_mapping"]["profile_id"] == "humanoid.v1"
        assert manifest["rest_pose"]["import_policy"] == "applied_transforms"
        assert manifest["slots"]
        assert manifest["locomotion_map"]
        assert manifest["root_motion_profile"]["policy"] in {"hold", "bounded_continue", "reversible_continue"}
        assert manifest["physical_profile"]["collision_shape"]
        assert manifest["fallback"]["mode"]
        assert manifest["report_path"].startswith(".harness/verification/")


def test_delivery_timing_sheets_use_semantic_ids_and_empty_atomic_sequences() -> None:
    for package_id in ("crusader_knight", "external_character_b"):
        timing_path = ACTIVE / package_id / "docs" / "action-timing.json"
        timing = json.loads(timing_path.read_text(encoding="utf-8"))
        actions = timing["actions"]
        assert {a["action_id"] for a in actions} >= {"Idle", "Walk", "Run", "Jump", "Turn"}
        for action in actions:
            assert action["action_id"] != action["clip"]
            assert action["atomic_sequence"] == []
            assert action["timing"]["duration_seconds"] > 0


def test_qualification_matrix_keeps_rejected_candidates_rejected() -> None:
    matrix = json.loads((REPORTS / "qualification-matrix.json").read_text(encoding="utf-8"))
    by_id = {entry["candidate_id"]: entry for entry in matrix["candidates"]}
    assert by_id["crusader_knight"]["status"] in {"qualified", "qualified_with_fallback"}
    assert by_id["external_character_b"]["status"] == "rejected"
    assert by_id["npc_candidate"]["status"] == "rejected"
    assert by_id["female_trio_opt_in"]["status"] == "rejected"
    assert by_id["female_trio_opt_in"]["opt_in"] is True
    assert by_id["female_trio_opt_in"]["reasons"]
    assert all(entry["delivery_level"] in {"minimum_movement", "full_body_action", "concurrent_action", "presentation_extension"} for entry in by_id.values())


def test_reports_are_machine_readable_and_expose_fallback_and_concurrency_claims() -> None:
    for package_id, expected_status in (("crusader_knight", {"qualified", "qualified_with_fallback"}), ("external_character_b", {"rejected"})):
        report = json.loads((REPORTS / f"{package_id}.json").read_text(encoding="utf-8"))
        assert report["contract"] == "character_qualification_report.v1"
        assert report["package_id"] == package_id
        assert report["status"] in expected_status
        assert report["delivery_level"] in {"minimum_movement", "full_body_action", "concurrent_action", "presentation_extension"}
        assert report["fallback"]
        assert report["locomotion_compatibility"]
        assert report["provenance"]["package_digest"]
        assert report["actions"]
        assert any(a.get("semantic_action_id") for a in report["actions"])
