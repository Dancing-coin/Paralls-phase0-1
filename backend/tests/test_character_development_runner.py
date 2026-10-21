import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def load(name):
    path = REPO / f"scripts/verification/{name}.py"
    assert path.is_file(), "development runner is missing"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package():
    return load("prepare_character_evaluation").prepare(
        REPO, REPO / "backend/tests/fixtures/character_evaluation/four_role_preparation")


def test_runner_rejects_changed_wire_and_truth_before_any_provider_call(tmp_path):
    runner = load("run_character_development")
    for kind in ("wire", "truth", "source", "split", "ready", "mapping"):
        data = package()
        if kind == "wire":
            data["records"][-1]["wire_request"]["state"] = "tampered"
        elif kind == "truth":
            data["grading"][-1]["acceptable_pairs"] = [["defer", "obj:invented"]]
        elif kind == "source":
            key = next(iter(data["records"][-1]["source_revisions"]))
            data["records"][-1]["source_revisions"][key] = "0" * 64
        elif kind == "split":
            data["records"][-1]["split"] = "final"
        elif kind == "ready":
            data["preflight"]["development_ready"] = False
        else:
            ctx = data["records"][-1]["provider_request"]["context"]
            ctx["candidate_mapping"][data["records"][-1]["controlled_p"][0]]["target_refs"] = {"target": "obj:invented"}
        with pytest.raises(ValueError):
            runner.run(data, repo=REPO, output_dir=tmp_path / kind, endpoint="http://127.0.0.1:1")
        assert not (tmp_path / kind / "results.jsonl").exists()


def test_runner_uses_real_adapter_mapping_and_flushes_diagnostic_only_results(tmp_path, monkeypatch):
    runner = load("run_character_development")
    data = package()
    seen = []

    def post(self, payload):
        seen.append(copy.deepcopy(payload))
        label = next(iter(payload["questions"]["choice"]["criteria"]))
        return {"answers": {"choice": {"choice": label}}}

    monkeypatch.setattr(runner.LayaSystemOneProvider, "_post", post)
    summary = runner.run(data, repo=REPO, output_dir=tmp_path / "evidence", endpoint="http://local-test")
    rows = [json.loads(line) for line in (tmp_path / "evidence/results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert seen == [row["wire_request"] for row in data["records"]]
    assert summary["provider_calls"] == summary["valid_inputs"] == 16
    assert summary["diagnostic_safety_denominator"] == 16
    assert summary["diagnostic_safety_passed"] == 4
    assert summary["action_target_quality_denominator"] == 0
    assert summary["role_sensitive_evaluation_denominator"] == 0
    assert summary["diagnostic_safety_truth_status"] == "provisional_authored_development_set_not_independent_gold"
    assert all(row["raw_response"] and row["mapped_candidate"]["target_refs"] for row in rows)
    assert all(row["latency_ms"] is not None and row["wire_request_digest"] for row in rows)
    assert all("offline_grading" not in request for request in seen)


def test_runner_preserves_rejected_real_response_and_does_not_grade_it(tmp_path, monkeypatch):
    runner = load("run_character_development")
    monkeypatch.setattr(runner.LayaSystemOneProvider, "_post", lambda self, payload:
                        {"answers": {"choice": {"choice": "outside-frozen-set"}}})
    summary = runner.run(package(), repo=REPO, output_dir=tmp_path / "evidence", endpoint="http://local-test")
    rows = [json.loads(line) for line in (tmp_path / "evidence/results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert summary["mapping_rejections"] == 16
    assert summary["diagnostic_safety_denominator"] == 0
    assert all(row["raw_response"] and row["rejection_reason"] for row in rows)


def test_runner_stops_changed_input_version_and_retains_already_issued_call(tmp_path, monkeypatch):
    runner = load("run_character_development")
    data = package()

    def post(self, payload):
        data["records"][1]["provider_request"]["context"]["snapshot"]["event"] = "changed after preflight"
        label = next(iter(payload["questions"]["choice"]["criteria"]))
        return {"answers": {"choice": {"choice": label}}}

    monkeypatch.setattr(runner.LayaSystemOneProvider, "_post", post)
    summary = runner.run(data, repo=REPO, output_dir=tmp_path / "evidence", endpoint="http://local-test")
    assert summary["stop_reason"] == "runtime_discovered_input_defect"
    assert summary["provider_calls"] == 1
    assert len((tmp_path / "evidence/results.jsonl").read_text(encoding="utf-8").splitlines()) == 1
