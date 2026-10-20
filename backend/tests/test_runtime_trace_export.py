from __future__ import annotations

import copy
import hashlib
import json

import pytest

from app.character_agent.evaluation.runtime_trace_export import export_runtime_trace
from app.character_agent.evaluation.runtime_trace_export import _digest
from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.planning.l3_planner import CandidateCompiler


@pytest.fixture
def source(tmp_path):
    provider = LayaSystemOneProvider(endpoint="http://unused", option_tokenizer=lambda _: [1],
                                     tokenizer_sha256="sha256:synthetic")
    compiled = CandidateCompiler().compile(candidates=[{
        "candidate_id": "use_object:obj_worktable", "semantic_action_id": "action:use",
        "semantic_intent_id": "use_object", "target_refs": {"object": "obj_worktable"},
        "action_family": "procedure", "owner_route": "esm.interaction",
        "revision_pins": {"target_admission_digest": "sha256:target"},
    }, {"candidate_id": "observe", "semantic_action_id": "action:observe",
        "semantic_intent_id": "observe", "target_refs": {}, "action_family": "observation"}])
    context = {"actor_id": "char_a", "turn_id": "turn:1", "provider_revision": provider.PROVIDER_REVISION,
               "candidate_intents": [x["wire_label"] for x in compiled.presented],
               "frozen_candidates": compiled.presented,
               "candidate_mapping": {x["wire_label"]: x for x in compiled.presented},
               "candidate_universe": compiled.universe, "candidate_pruned": compiled.pruned,
               "candidate_diagnostics": compiled.diagnostics, "candidate_digest": compiled.digest,
               "input_budget_required": True, "max_len": 2091, "head_max_len": 256,
               "private_truth_profile": {"hidden": "never-export-this"}}
    prepared = {"task_kind": "l3_planning", "context": context}
    contract = {"turn_id": "turn:1", "actor_ref": "character:char_a", "target_ref": "obj_worktable",
                "target_refs": ["obj_worktable"], "semantic_intent_id": "use_object",
                "semantic_action_id": "action:use", "idempotency_key": "execution:turn:1",
                "expected_observation": {"candidate_id": "use_object:obj_worktable",
                    "candidate_digest": compiled.digest, "owner_route": "esm.interaction",
                    "target_admission_digest": "sha256:target",
                    "execution_scope": {"room_id": "room", "scene_id": "scene", "zone_id": "zone"}}}
    result = {"message_type": "world_result", "payload": {
        "settlement_status": "committed", "settlement_id": "transaction:1", "turn_id": "turn:1",
        "idempotency_key": "execution:turn:1", "actor_id": "char_a", "target_object_id": "obj_worktable",
        "room_id": "room", "scene_id": "scene", "zone_id": "zone"}}
    records = [{"kind": "configuration", "api_key": "credential-do-not-export"},
               {"kind": "laya_enter", "frozen_request": prepared},
               {"kind": "laya_http_result", "call": {"request": provider.build_wire_request(prepared),
                "response": {"answers": {"choice": {"choice": "use_object:obj_worktable"}},
                             "usage": {"truncated": False, "state_tokens_dropped": 0, "truncated_questions": []}}}},
               {"kind": "execution_input", "contract": contract},
               {"kind": "wire_output", "message": result}]
    path = tmp_path / "trace.jsonl"

    def run(change=None):
        rows = copy.deepcopy(records)
        if change:
            change(rows)
        raw = "\n".join(json.dumps(x, ensure_ascii=False) for x in rows).encode()
        path.write_bytes(raw)
        return export_runtime_trace(path, provider=provider), raw
    return run


def test_export_freezes_complete_input_without_claiming_owner_or_quality(source):
    result, raw = source()
    assert result["accepted_count"] == 1
    assert result["status"] == "development_only"
    assert result["formal_eligible"] is False
    assert result["source_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    record = result["records"][0]
    assert record["boundary_result"]["settlement_id"] == "transaction:1"
    assert record["owner_store_validation"] == "unverified"
    assert record["quality"] == "unscored"
    assert record["recovery"] == "unverified"
    assert record["source_lines"] == {"prepared": 2, "model": 3, "execution": 4, "boundary": 5}
    encoded = json.dumps(result)
    assert "never-export-this" not in encoded
    assert "credential-do-not-export" not in encoded
    assert len(record["candidate_compilation"]["presented"]) == 2
    assert "state" in record["wire_request"]


@pytest.mark.parametrize("mutate,reason", [
    (lambda r: r.pop(), "owner_boundary_missing"),
    (lambda r: r.pop(3), "execution_missing"),
    (lambda r: r[4]["message"]["payload"].update(settlement_status="accepted"), "owner_boundary_missing"),
    (lambda r: r[4]["message"]["payload"].update(actor_id="char_b"), "boundary_identity_mismatch"),
    (lambda r: r[4]["message"]["payload"].update(idempotency_key="other"), "boundary_identity_mismatch"),
    (lambda r: r[4]["message"]["payload"].update(zone_id="other"), "boundary_identity_mismatch"),
    (lambda r: r[3]["contract"].update(semantic_action_id="action:finish_use"), "execution_identity_mismatch"),
    (lambda r: r[3]["contract"].update(target_refs=["obj_other"]), "execution_identity_mismatch"),
    (lambda r: r[3]["contract"]["expected_observation"].update(candidate_digest="forged"), "execution_identity_mismatch"),
    (lambda r: r[2]["call"]["response"]["answers"]["choice"].update(choice="not-in-set"), "choice_invalid"),
    (lambda r: r[2]["call"]["response"]["usage"].update(state_tokens_dropped=False), "usage_invalid"),
    (lambda r: r[2]["call"]["response"]["usage"].update(truncated=True), "usage_invalid"),
    (lambda r: r[2]["call"]["request"].update(state="changed"), "wire_mismatch"),
    (lambda r: r[1]["frozen_request"]["context"]["candidate_universe"].pop(), "compilation_digest_mismatch"),
    (lambda r: r[1]["frozen_request"]["context"].update(provider_revision="stale"), "provider_invalid"),
    (lambda r: r.insert(2, copy.deepcopy(r[1])), "overlapping_model_calls"),
])
def test_incomplete_or_changed_associations_fail_closed(source, mutate, reason):
    result, _ = source(mutate)
    assert result["accepted_count"] == 0
    assert reason in {x["reason"] for x in result["rejections"]}


def test_repeated_archive_snapshots_deduplicate_identical_boundary(source):
    result, _ = source(lambda r: r.append(copy.deepcopy(r[-1])))
    assert result["accepted_count"] == 1


def test_changed_duplicate_boundary_is_ambiguous(source):
    def mutate(rows):
        other = copy.deepcopy(rows[-1])
        other["message"]["payload"]["settlement_id"] = "transaction:other"
        rows.append(other)
    result, _ = source(mutate)
    assert result["accepted_count"] == 0
    assert result["rejections"][0]["reason"] == "boundary_ambiguous"


def test_presented_candidate_cannot_be_absent_from_rehashed_universe(source):
    def mutate(rows):
        context = rows[1]["frozen_request"]["context"]
        context["candidate_universe"].pop(0)
        context["candidate_digest"] = _digest({"universe": context["candidate_universe"],
            "presented": context["frozen_candidates"], "pruned": context["candidate_pruned"],
            "diagnostics": context["candidate_diagnostics"]})
        rows[3]["contract"]["expected_observation"]["candidate_digest"] = context["candidate_digest"]
    result, _ = source(mutate)
    assert result["accepted_count"] == 0
    assert result["rejections"][0]["reason"] == "compilation_coverage_invalid"


def test_truncation_of_questions_is_not_a_valid_complete_input(source):
    result, _ = source(lambda rows: rows[2]["call"]["response"]["usage"].update(truncated_questions=["choice"]))
    assert result["accepted_count"] == 0
    assert result["rejections"][0]["reason"] == "usage_invalid"
