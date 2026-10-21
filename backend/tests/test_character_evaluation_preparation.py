import importlib.util
import json
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/verification/prepare_character_evaluation.py"
FIXTURE = REPO / "backend/tests/fixtures/character_evaluation/four_role_preparation"


def preparer():
    assert SCRIPT.is_file(), "missing isolated evaluation preparation"
    spec = importlib.util.spec_from_file_location("character_evaluation_preparation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preparation_materializes_frozen_frames_and_independent_reference_universe():
    result = preparer().prepare(REPO, FIXTURE)
    assert result["status"] == "diagnostic_inputs_prepared"
    assert len(result["records"]) == 16
    assert result["provider_calls"] == 0
    assert result["A-Cognition"] == "blocked"
    assert result["A-Embodied"] == "blocked"
    for row in result["records"]:
        assert row["frame"]["actor_id"] == row["actor_id"]
        assert row["frame"]["frame_digest"]
        assert row["reference_u_match"] is True
        assert len(row["complete_u"]) == len(row["controlled_p"]) == 3
        assert row["runtime_quality_denominator_eligible"] is False
        assert row["target_state"]["evidence_kind"] == "authored_fixture"
        assert row["target_state"]["runtime_legality"] == "unverified"
        assert row["base_selection"]["controlled_error"] is False
        assert row["character_performance"]["seed"]
        assert row["character_performance"]["status"] == "not_run"
        assert row["split"] == "development"
        assert row["frame"]["runtime_state"]["cards"]
        assert row["frame"]["enduring_truth"]["cards"]
        assert row["private_projection"]["status"] == "not_used_public_fixture"
        assert [item["wire_label"] for item in row["provider_request"]["context"]["frozen_candidates"]] == row["controlled_p"]
        assert row["frame"]["cognition_workspace"]["event_inbox"]
    assert len(result["grading"]) == 16
    assert all(r["acceptable_pairs"] and r["authored_by"] and not r["independent_review_approved"] for r in result["grading"])


def test_model_input_never_contains_grading_answers():
    module = preparer()
    corpus = module.load_yaml(FIXTURE / "development.yaml")
    baseline = module.prepare(REPO, FIXTURE)
    for item in corpus["scenarios"]:
        item["review"]["acceptable_pairs"] = [["defer", item["objects"][0]]]
        item["review"]["rationale"] = "secret-grading-sentinel"
    changed = module.prepare(REPO, FIXTURE, corpus=corpus)
    assert [r["provider_request"] for r in changed["records"]] == [r["provider_request"] for r in baseline["records"]]
    assert "secret-grading-sentinel" not in json.dumps(changed["records"])


def test_final_and_independent_holdout_remain_unopened(tmp_path):
    module = preparer()
    corpus = module.load_yaml(FIXTURE / "development.yaml")
    corpus["sealed_splits"] = {"final": {"labels_path": "never-open"}, "independent_holdout": {"labels_path": "never-open"}}
    assert module.prepare(REPO, FIXTURE, corpus=corpus)["final_labels_read"] is False
    for split in ("final", "independent_holdout"):
        with pytest.raises(ValueError, match="sealed_split_not_available"):
            module.prepare(REPO, FIXTURE, splits=(split,))


def test_same_authority_trajectory_cannot_cross_splits():
    module = preparer()
    corpus = module.load_yaml(FIXTURE / "development.yaml")
    corpus["scenarios"][3]["trajectory_group"] = corpus["scenarios"][0]["trajectory_group"]
    corpus["scenarios"][3]["split"] = "calibration"
    with pytest.raises(ValueError, match="trajectory_leakage"):
        module.prepare(REPO, FIXTURE, corpus=corpus)


def test_missing_or_hidden_targets_cannot_receive_fixture_admission():
    module = preparer()
    corpus = module.load_yaml(FIXTURE / "development.yaml")
    corpus["scenarios"][0]["visible_targets"] = []
    with pytest.raises(ValueError, match="fixture_target_not_visible"):
        module.prepare(REPO, FIXTURE, corpus=corpus)


def test_source_change_is_rejected_without_auto_repinning(tmp_path):
    module = preparer()
    policy = module.load_yaml(FIXTURE / "development-policy.yaml")
    policy["source_pins"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source_changed"):
        module.prepare(REPO, FIXTURE, policy=policy)


def test_abo_projection_does_not_inherit_runtime_numeric_defaults():
    result = preparer().prepare(REPO, FIXTURE)
    abo = next(r for r in result["records"] if r["actor_id"] == "char_d")
    assert abo["role_projection"]["runtime_admission"] is False
    assert abo["role_projection"]["source_caps"] == {"preferred_effort": "fast", "maximum_effort": "balanced", "max_active_hypotheses": 1, "max_reasoning_hops": 1}
    assert "personality_numeric_values" in abo["role_projection"]["unresolved"]
    assert "personality_layer" not in abo["role_projection"]["effective_profile"]
    assert result["thresholds"]["status"] == "not_frozen"
    assert result["preflight"]["development_ready"] is True
    assert result["preflight"]["calibration_ready"] is False
    assert result["preflight"]["final_ready"] is False
    assert result["calibration"]["rebuild_required"] is True
    assert result["independent_holdout"]["independence_verified"] is False


def test_reference_universe_detects_compiler_omission(monkeypatch):
    module = preparer()
    original = module.CandidateCompiler.compile

    def omit(self, **kwargs):
        result = original(self, **kwargs)
        result.universe.pop()
        return result

    monkeypatch.setattr(module.CandidateCompiler, "compile", omit)
    with pytest.raises(ValueError, match="reference_u_mismatch"):
        module.prepare(REPO, FIXTURE)


def test_fixture_profiles_have_source_evidence_without_abo_defaults():
    result = preparer().prepare(REPO, FIXTURE)
    for actor in ("char_a", "char_b", "char_c"):
        row = next(r for r in result["records"] if r["actor_id"] == actor)
        assert row["role_projection"]["effective_profile"]["identity_core"]["character_id"] == actor
        assert row["role_projection"]["runtime_admission"] is False
    assert len({r["target_state"]["visible_targets"][0] for r in result["records"]}) == 4


def test_authored_profile_reaches_shared_wire_without_private_backbone():
    result = preparer().prepare(REPO, FIXTURE)
    row = result["records"][0]
    assert row["provider_request"]["context"]["effective_profile"]["personality_layer"]
    assert row["wire_request"]["state"] != row["visible_evidence"]["event"]
    assert "life_memory_backbone" not in row["wire_request"]["state"]
    assert row["wire_request_digest"]


def test_preparation_is_repeatable_and_full_wire_matches_runtime_serializer():
    from app.character_agent.gateway.laya_provider import LayaSystemOneProvider

    module = preparer()
    baseline = module.prepare(REPO, FIXTURE)
    assert baseline == module.prepare(REPO, FIXTURE)
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:8765")
    assert all(item["passed"] for item in baseline["input_checks"])
    for row in baseline["records"]:
        assert provider.build_wire_request(row["provider_request"]) == row["wire_request"]
        assert module._digest(row["wire_request"]) == row["wire_request_digest"]
        assert list(row["wire_request"]["questions"]["choice"]["criteria"]) == row["controlled_p"]
        assert row["source_revisions"] and row["transformation_revisions"]
        assert not row["provider_request"]["context"]["capability_envelope"]
        assert not row["provider_request"]["context"]["cognition_policy"]


def test_empty_development_selection_cannot_claim_ready():
    result = preparer().prepare(REPO, FIXTURE, splits=())
    assert result["records"] == []
    assert result["preflight"]["development_ready"] is False
