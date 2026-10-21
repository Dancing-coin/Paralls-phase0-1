from __future__ import annotations

import importlib.util
from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prepare_calibration_preclosure", ROOT / "scripts/verification/prepare_calibration_preclosure.py")
preparation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparation)


def test_offline_wire_preserves_unknowns_targets_and_source_memory(monkeypatch):
    monkeypatch.setattr(preparation.LayaSystemOneProvider, "_post", lambda *_: pytest.fail("offline preparation attempted model call"))
    source = json.loads((preparation.INPUTS / "inputs.json").read_text(encoding="utf-8"))
    provider = preparation.LayaSystemOneProvider(endpoint="http://offline.invalid", option_tokenizer=lambda _: [1],
                                               tokenizer_sha256="test:pin", require_option_token_validation=True)
    results = [preparation.prepare_record(r, provider) for r in source["records"]]
    assert len(results) == 24
    sizes = {}
    for original, result in zip(source["records"], results):
        sizes.setdefault(result["scenario_id"], set()).add(len(result["U"]))
        wire = json.dumps(result["wire"])
        assert not any(word in wire for word in ["char_a", "char_b", "char_c", "char_d", "source_refs", "rationale", "acceptable_actions", "canonical_name"])
        assert "owner_permission" in wire and "execution_receipt" in wire
        assert list(result["wire"]["questions"]["choice"]["criteria"]) == [c["wire_label"] for c in result["P"]]
        if original["actor_id"] == "char_d":
            state = json.loads(result["wire"]["state"])
            assert not any(c["factor_type"] == "personality_bias" for c in state["enduring_truth"])
            assert state["event_inbox"][0]["unknown_dimensions"]
        else:
            assert all(m["text"] in wire for m in original["memories"])
            assert all(g["text"] in wire for g in original["goals"])
            assert all(c["text"] in wire for c in original["constraints"])
            prohibited = next(c for c in original["constraints"] if "virtue_value_layer.red_lines" in c.get("reference", ""))
            assert "Must not " + prohibited["text"] in wire
        if original["relationships"]:
            assert original["relationships"][0]["remembered_evidence"] in wire
        assert result["actual_projection_paths"]["constraints"] == "cognition_workspace.event_inbox[0].constraints"
    assert all(value == {3, 4} for value in sizes.values())


def test_approval_rejects_missing_coverage_pollution_and_false_claims(tmp_path):
    path = str(tmp_path / "review-input.json")
    Path(path).write_text(json.dumps({"inputs_digest": "pin", "records": [{"question_id": q, "track": "diagnostic", "U": [{"candidate_id": "candidate_01"}, {"candidate_id": "candidate_02"}, {"candidate_id": "candidate_03"}],
                         "P_candidate_ids": ["candidate_01", "candidate_02"], "wire": {"questions": {"choice": {"criteria": {"C1": "first", "C2": "second"}}}}} for q in ["q1", "q2"]]}), encoding="utf-8")
    report = {"reviewer_independent_approval": True, "lead_audit_approval": True, "formal_truth_usable": True,
              "inputs_digest": "pin", "coverage_question_ids": ["q1", "q2"],
              "read_log": {"unpolluted": True, "paths": [path]}, "accidental_exposure": [],
              "input_sha256": preparation.file_digest(Path(path)),
              "judgments": [{"question_id": q, "track": "diagnostic", "acceptable_action_set": ["C1"],
                             "multiple_answers_allowed": False, "formal_denominator_computable": True,
                             "source_supported_difference": False, "difference_requirement": "not_required",
                             "unknowns": ["runtime_legality", "owner_permission", "actual_speech", "execution_receipt"]} for q in ["q1", "q2"]]}
    assert preparation.verify_approvals(report, ["q1", "q2"], "pin", [path])
    structured = {**report, "judgments": [{**j, "acceptable_action_set": [{"label": "C1", "candidate_id": "candidate_01"}]} for j in report["judgments"]]}
    assert preparation.verify_approvals(structured, ["q1", "q2"], "pin", [path])
    for change in [{"reviewer_independent_approval": False}, {"lead_audit_approval": False},
                   {"formal_truth_usable": False}, {"inputs_digest": "stale"},
                   {"coverage_question_ids": ["q1"]}, {"read_log": {"unpolluted": False, "paths": [path]}},
                   {"judgments": []}, {"input_sha256": "stale"},
                   {"judgments": [{**j, "acceptable_action_set": ["unregistered"]} for j in report["judgments"]]},
                   {"judgments": [{**j, "acceptable_action_set": ["candidate_03"]} for j in report["judgments"]]},
                   {"judgments": [{**j, "acceptable_action_set": [{"label": "C1", "candidate_id": "candidate_02"}]} for j in report["judgments"]]},
                   {"judgments": [{**j, "unknowns": []} for j in report["judgments"]]},
                   {"read_log": {"unpolluted": True, "paths": [str(tmp_path / "historical-response.json")]}}]:
        with pytest.raises(ValueError):
            preparation.verify_approvals({**report, **change}, ["q1", "q2"], "pin", [path])
    changed = json.loads(Path(path).read_text(encoding="utf-8"))
    changed["inputs_digest"] = "different"
    Path(path).write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="input digest"):
        preparation.verify_approvals({**report, "input_sha256": preparation.file_digest(Path(path))}, ["q1", "q2"], "pin", [path])
    Path(path).write_text('{}', encoding="utf-8")
    with pytest.raises(ValueError, match="byte pin"):
        preparation.verify_approvals(report, ["q1", "q2"], "pin", [path])


def test_source_revision_staleness_and_missing_source_are_rejected(tmp_path):
    profile = tmp_path / "profile.yaml"
    profile.write_text("values: care\n", encoding="utf-8")
    records = [{"differences": [{"source_kind": "profile_authored", "reference": "profile.yaml#values",
                                  "revision": preparation.file_digest(profile)}]}]
    preparation.validate_source_pins(records, tmp_path)
    profile.write_text("values: changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        preparation.validate_source_pins(records, tmp_path)
    profile.unlink()
    with pytest.raises(ValueError, match="missing"):
        preparation.validate_source_pins(records, tmp_path)
