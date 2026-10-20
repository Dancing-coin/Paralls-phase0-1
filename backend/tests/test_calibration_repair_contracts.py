from __future__ import annotations

import pytest

from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.evaluation.calibration_contracts import (
    canonical_records_digest,
    canonical_digest_excluding,
    score_calibration_records,
    build_run_envelope,
)


def test_provider_rejects_missing_or_truncated_full_budget_before_transport():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda value: [1] * len(value), tokenizer_sha256="sha256:" + "a" * 64)
    request = {"task_kind": "l3_planning", "context": {
        "laya_state": "state",
        "candidate_intents": ["observe"],
        "max_len": 4,
        "head_max_len": 256,
    }}
    with pytest.raises(ValueError, match="input budget"):
        provider.build_wire_request(request)


def test_provider_emits_frozen_wire_budget_and_preserves_state_and_order():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda value: [1], tokenizer_sha256="sha256:" + "a" * 64)
    request = {"task_kind": "l3_planning", "context": {
        "laya_state": "完整 state 保持原样",
        "candidate_intents": ["first", "second"],
        "max_len": 2091,
        "head_max_len": 256,
    }}
    wire = provider.build_wire_request(request)
    assert wire["state"] == "完整 state 保持原样"
    assert list(wire["questions"]["choice"]["criteria"]) == ["first", "second"]
    assert wire["max_len"] == 2091
    assert wire["head_max_len"] == 256


def test_archive_and_envelope_digests_have_explicit_scopes():
    records = [{"question_id": "q1", "response": {"choice": "C1"}}]
    digest = canonical_records_digest(records)
    assert digest == "sha256:dde2d60a39d4b504e7642ce9fb104f8a2ab1b25673ede4492e6c11eef3bf1a06"
    document = {"records": records, "score": {"hits": 1}, "score_digest": "old"}
    assert canonical_digest_excluding(document, {"score_digest"}) == canonical_digest_excluding(
        {**document, "score_digest": "new"}, {"score_digest"}
    )
    assert canonical_records_digest([{**records[0], "response": {"choice": "C2"}}]) != digest
    metadata = {"input_digest": "sha256:inputs", "provider_revision": "rev", "tokenizer_sha256": "sha256:tokenizer",
                "device": "cpu", "max_len": 2091, "head_max_len": 256, "before_health": {}, "after_health": {},
                "preflight": {}, "execution_identity": {"pid": 1}}
    envelope = build_run_envelope(records, metadata, {"status": "sealed"})
    assert envelope["records_digest"] == digest
    assert envelope["envelope_digest"].startswith("sha256:")
    assert canonical_digest_excluding(envelope, {"envelope_digest"}) == envelope["envelope_digest"]
    changed_metadata = {**metadata, "max_len": 2092}
    assert build_run_envelope(records, changed_metadata, {"status": "sealed"})["envelope_digest"] != envelope["envelope_digest"]


def test_envelope_requires_execution_attestations():
    with pytest.raises(ValueError, match="metadata missing"):
        build_run_envelope([], {"max_len": 2091}, {"status": "sealed"})


def test_scorer_excludes_invalid_and_preserves_formal_denominators():
    records = [
        {"question_id": "q1", "track": "autonomous_decision", "response": {"choice": "C1"}, "usage": {"truncated": True}},
        {"question_id": "q2", "track": "autonomous_decision", "response": {"choice": "C2"}, "usage": {"truncated": False, "state_tokens_dropped": 0},
         "request": {"questions": {"choice": {"criteria": {"C1": "one", "C2": "two"}}}}},
    ]
    truth = {"q1": {"acceptable_action_set": ["C1"]}, "q2": {"acceptable_action_set": ["C2"]}}
    result = score_calibration_records(records, truth, formal_denominators={"autonomous_decision": 8}, minimum_valid={"autonomous_decision": 2})
    assert result["tracks"]["autonomous_decision"]["valid_samples"] == 1
    assert result["tracks"]["autonomous_decision"]["hits"] == 1
    assert result["tracks"]["autonomous_decision"]["formal_denominator"] == 8
    assert result["status"] == "blocked_minimum_valid_samples"


def test_budget_accepts_exact_boundary_and_rejects_one_below():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda value: [1] * len(value), tokenizer_sha256="sha256:" + "a" * 64)
    base = {"task_kind": "l3_planning", "context": {"laya_state": "abcd", "candidate_intents": ["observe"], "head_max_len": 4}}
    provider.sequence_tokenizer = lambda value: [1] * (1 if value == "abcd" else 2)
    base["context"]["head_max_len"] = 20
    base["context"]["max_len"] = 20
    base["context"]["input_budget_required"] = True
    provider.build_wire_request(base)
    required = provider.last_input_budget["required_tokens"]
    base["context"]["head_max_len"] = required - 1
    base["context"]["max_len"] = required
    assert provider.build_wire_request(base)["max_len"] == required
    base["context"]["max_len"] = required - 1
    with pytest.raises(ValueError, match="input budget"):
        provider.build_wire_request(base)


def test_budget_missing_verification_fails_closed():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1")
    request = {"task_kind": "l3_planning", "context": {"laya_state": "state", "candidate_intents": ["observe"], "max_len": 2091, "input_budget_required": True}}
    with pytest.raises(ValueError, match="cannot be verified"):
        provider.build_wire_request(request)


def test_budget_counts_official_choice_layout_and_independent_spans():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda value: list(value), tokenizer_sha256="sha256:" + "a" * 64)
    context = {"laya_state": "state", "candidate_intents": ["A", "B"], "input_budget_required": True,
               "max_len": 200, "head_max_len": 110}
    provider.build_wire_request({"task_kind": "l3_planning", "context": context})
    audit = provider.last_input_budget
    instruction = "choice question: Choose exactly one complete action and target from the frozen candidates."
    options = [" A: A", " B: B"]
    expected_head = 3 + len(instruction) + sum(1 + len(option) for option in options)
    assert audit["head_tokens"] == expected_head
    assert audit["required_tokens"] == expected_head + len("state") + 1


def test_budget_official_layout_rejects_individual_truncation_and_boundary():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda value: [1] * len(value), tokenizer_sha256="sha256:" + "a" * 64)
    request = {"task_kind": "l3_planning", "context": {"laya_state": "state", "candidate_intents": ["A"],
               "input_budget_required": True, "max_len": 200, "head_max_len": 100}}
    provider.build_wire_request(request)
    required = provider.last_input_budget["required_tokens"]
    request["context"]["max_len"] = required
    assert provider.build_wire_request(request)["max_len"] == required
    request["context"]["max_len"] = required + 1
    assert provider.build_wire_request(request)["max_len"] == required + 1
    request["context"]["max_len"] = required - 1
    with pytest.raises(ValueError, match="input budget exceeded"):
        provider.build_wire_request(request)
    request["context"]["max_len"] = 200
    request["context"]["head_max_len"] = provider.last_input_budget["head_tokens"] - 1
    with pytest.raises(ValueError, match="head exceeds"):
        provider.build_wire_request(request)


def test_budget_rejects_instruction_option_and_state_truncation():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1",
        option_tokenizer=lambda value: list(value), tokenizer_sha256="sha256:" + "a" * 64)
    base = {"task_kind": "l3_planning", "context": {"laya_state": "s", "candidate_intents": ["A"],
        "input_budget_required": True, "max_len": 300, "head_max_len": 256}}
    provider.build_wire_request(base)
    head = provider.last_input_budget["head_tokens"]
    base["context"]["head_max_len"] = head - 1
    with pytest.raises(ValueError, match="head exceeds"):
        provider.build_wire_request(base)
    base["context"]["head_max_len"] = 256
    base["context"]["candidate_intents"] = ["A" * 48]
    with pytest.raises(ValueError, match="option token limit"):
        provider.build_wire_request(base)
    base["context"]["candidate_intents"] = ["A"]
    base["context"]["laya_state"] = "s" * 300
    with pytest.raises(ValueError, match="input budget exceeded"):
        provider.build_wire_request(base)


def test_scorer_accepts_frozen_structured_truth_labels():
    records = [{"question_id": "q1", "track": "autonomous_decision", "response": {"choice": "C1"}, "usage": {"truncated": False, "state_tokens_dropped": 0},
                "request": {"questions": {"choice": {"criteria": {"C1": "one", "C2": "two"}}}}}]
    truth = {"q1": {"acceptable_action_set": [{"label": "C1", "candidate_id": "candidate_01"}]}}
    result = score_calibration_records(records, truth, formal_denominators={"autonomous_decision": 8}, minimum_valid={"autonomous_decision": 1})
    assert result["tracks"]["autonomous_decision"]["hits"] == 1


def test_scorer_rejects_unverifiable_usage():
    records = [{"question_id": "q1", "track": "autonomous_decision", "response": {"choice": "C1"},
                "usage": {"state_tokens": 3}}]
    result = score_calibration_records(records, {"q1": {"acceptable_action_set": ["C1"]}},
        formal_denominators={"autonomous_decision": 8}, minimum_valid={"autonomous_decision": 8})
    assert result["tracks"]["autonomous_decision"]["valid_samples"] == 0
    assert result["status"] == "blocked_minimum_valid_samples"


def test_runner_requires_verified_cpu_instance_and_synthetic_preflight():
    from scripts.verification.run_calibration_diagnostic import preflight_admits_formal_run

    health = {"status": "ok", "loaded": ["multilingual"],
              "revisions": {"multilingual": LayaSystemOneProvider.CHECKPOINT_REVISION},
              "device": "cpu", "checkpoint_devices": {"multilingual": "cpu"}}
    synthetic = {"accepted": True, "usage": {"truncated": False, "state_tokens_dropped": 0}}
    assert preflight_admits_formal_run(health, synthetic)
    assert not preflight_admits_formal_run({**health, "device": "cuda"}, synthetic)
    assert not preflight_admits_formal_run(health, {"accepted": True, "usage": {"truncated": None}})
    assert not preflight_admits_formal_run(health, {"accepted": True, "usage": {"truncated": False, "state_tokens_dropped": 1}})


def test_diagnostic_score_requires_independent_version_bound_approval():
    import copy
    import json
    from pathlib import Path
    from scripts.verification.score_calibration_diagnostic import validate_score_admission

    root = Path("D:/Users/User/Documents/paralls-evidence/october-calibration-repair-20261014")
    prior = Path("D:/Users/User/Documents/paralls-evidence/october-calibration-preclosure-20261013/preparation-v2")
    if not (root / "diagnostic-run-v2/run-envelope.json").exists():
        pytest.skip("external sealed calibration evidence unavailable")
    envelope = json.loads((root / "diagnostic-run-v2/run-envelope.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "transport-input-manifest.json").read_text(encoding="utf-8"))
    approval = json.loads((root / "independent-truth-approval-v3.json").read_text(encoding="utf-8"))
    truth_bytes = (prior / "lead-audited-truth.json").read_bytes()
    review_bytes = (root / "preparation-v3/review-input.json").read_bytes()
    prepared_bytes = (root / "preparation-v3/prepared-inputs.json").read_bytes()
    source_bytes = (root / "preparation-v3/metadata-manifest.json").read_bytes()
    def admit(sealed, signed):
        return validate_score_admission(sealed, manifest, signed, truth_bytes, review_bytes,
                                        prepared_bytes, source_bytes)
    assert admit(envelope, approval) == 22
    assert validate_score_admission(envelope, manifest, approval, None, review_bytes,
                                    prepared_bytes, source_bytes) == 22
    for changed in (None, {**approval, "decision": "rejected"},
                    {**approval, "actual_inputs_digest": "sha256:wrong"},
                    {**approval, "truth_sha256": "sha256:wrong"}):
        with pytest.raises(ValueError, match="approval"):
                admit(envelope, changed)
    changed = copy.deepcopy(approval)
    changed["requests"][0]["request_digest"] = "sha256:wrong"
    with pytest.raises(ValueError, match="approval"):
        admit(envelope, changed)
    changed = copy.deepcopy(approval)
    changed["requests"][0]["candidate_mapping_digest"] = "sha256:wrong"
    with pytest.raises(ValueError, match="approval candidate mapping"):
        admit(envelope, changed)
    corrupted = copy.deepcopy(envelope)
    corrupted["records"][0]["response_digest"] = "sha256:wrong"
    corrupted["records_digest"] = canonical_records_digest(corrupted["records"])
    corrupted["envelope_digest"] = canonical_digest_excluding(corrupted, {"envelope_digest"})
    with pytest.raises(ValueError, match="response digest"):
        admit(corrupted, approval)
    invalid = copy.deepcopy(envelope)
    invalid["records"][-1]["response_body"] = None
    invalid["records"][-1]["response_digest"] = None
    invalid["records"][-1]["response"] = None
    invalid["records"][-1]["usage"]["truncated"] = True
    invalid["records"][-1]["usage"]["input_tokens"] = 1024
    invalid["run_status"]["status"] = "stopped_on_invalid_or_error"
    invalid["records_digest"] = canonical_records_digest(invalid["records"])
    invalid["envelope_digest"] = canonical_digest_excluding(invalid, {"envelope_digest"})
    assert admit(invalid, approval) == 22


def test_all_22_repaired_budgets_equal_fixed_official_usage():
    import json
    from pathlib import Path

    root = Path("D:/Users/User/Documents/paralls-evidence/october-calibration-repair-20261014")
    tokenizer = Path("D:/laya-probe-cache/laya-multilingual/tokenizer/tokenizer.json")
    if not (root / "diagnostic-run-v2/run-envelope.json").exists() or not tokenizer.exists():
        pytest.skip("external official tokenizer or sealed evidence unavailable")
    envelope = json.loads((root / "diagnostic-run-v2/run-envelope.json").read_text(encoding="utf-8"))
    provider = LayaSystemOneProvider(endpoint="http://offline.invalid", tokenizer_path=str(tokenizer),
        tokenizer_sha256="sha256:609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f")
    observed = []
    for record in envelope["records"]:
        wire = record["request"]
        provider._validate_input_budget({"max_len": wire["max_len"], "head_max_len": wire["head_max_len"],
            "input_budget_required": True}, wire["state"], wire["questions"]["choice"]["criteria"])
        assert provider.last_input_budget["required_tokens"] == record["usage"]["input_tokens"]
        assert provider.last_input_budget["state_tokens"] == record["usage"]["state_tokens"]
        observed.append(provider.last_input_budget["required_tokens"])
    assert len(observed) == 22
    assert max(observed) == 2091
