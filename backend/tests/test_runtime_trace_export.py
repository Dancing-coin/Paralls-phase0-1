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

    def run(change=None, **kwargs):
        rows = copy.deepcopy(records)
        if change:
            change(rows)
        raw = "\n".join(json.dumps(x, ensure_ascii=False) for x in rows).encode()
        path.write_bytes(raw)
        return export_runtime_trace(path, provider=provider, **kwargs), raw
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


@pytest.fixture
def owner_snapshot(tmp_path):
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.models.player_input import InteractIntent
    from app.services.esm_service import ESMService

    def create(*, action="use", actor="char_a"):
        target = "obj_plaque" if action == "inspect" else "obj_worktable"
        path = tmp_path / "owner.json"
        store = DurableGameplayEventStore(tmp_path / f"{action}-{actor}.db")
        try:
            owner = ESMService(store=store)
            event = InteractIntent(player_id="character_agent", actor_id=actor,
                room_id="room", scene_id="scene", zone_id="zone", producer_ts=10,
                target_object_id=target, interaction_type=action,
                turn_id="turn:1", execution_contract_ref="execution:turn:1")
            request = owner.build_action_request(event, source_system="character_agent_l4").model_copy(update={
                "request_id": "execution:turn:1:0",
                "source": {"layer": "L4", "system": "character_agent_l4", "actor_id": actor},
                "causation_id": "cause:1", "correlation_id": "correlation:1"})
            result, receipt = owner.settle_object_interaction(event, action_request=request,
                actor_position=owner.OBJECT_POSITIONS[target])
            assert receipt.committed
            store.save_snapshot(path)
        finally:
            store.close()

        def bind(rows):
            rows[3]["contract"].update(producer_ts=10, causation_id="cause:1",
                correlation_id="correlation:1", expected_revision_vector={},
                expected_memory_revision_vector={}, expected_snapshot_revision=0)
            rows[4]["message"]["payload"].update(result.model_dump(mode="json"))
        return path, bind, receipt
    return create


def test_original_durable_owner_snapshot_matches_without_exposing_private_payload(source, owner_snapshot):
    path, bind, receipt = owner_snapshot()
    before = path.read_bytes()
    result, _ = source(bind, owner_snapshot=path)
    assert result["accepted_count"] == 1
    record = result["records"][0]
    assert record["owner_store_validation"] == "snapshot_matched"
    assert record["owner_evidence"]["source_sha256"] == "sha256:" + hashlib.sha256(before).hexdigest()
    assert record["owner_evidence"]["event_id"] == receipt.committed_event_ids[0]
    assert record["owner_evidence"]["transaction_id"] == receipt.transaction_id
    assert record["quality"] == "unscored" and record["recovery"] == "unverified"
    assert result["formal_eligible"] is False
    assert set(record["owner_evidence"]) == {"source_sha256", "event_id", "event_digest",
        "transaction_id", "receipt_digest", "global_sequence"}
    assert path.read_bytes() == before


@pytest.mark.parametrize("changed", ["actor", "action", "correlation", "boundary", "missing"])
def test_owner_snapshot_mismatch_rejects_archive_association(source, owner_snapshot, changed):
    path, bind, _ = owner_snapshot(actor="char_b" if changed == "actor" else "char_a",
                                  action="inspect" if changed == "action" else "use")
    def mutate(rows):
        bind(rows)
        # Preserve a consistent archive, while the original owner retains its request.
        rows[4]["message"]["payload"]["actor_id"] = "char_a"
        if changed == "action":
            rows[4]["message"]["payload"]["target_object_id"] = "obj_worktable"
        if changed == "correlation":
            rows[3]["contract"]["correlation_id"] = "other"
        if changed == "boundary":
            rows[4]["message"]["payload"]["settlement_id"] = "transaction:other"
        if changed == "missing":
            rows[3]["contract"]["idempotency_key"] = "execution:other"
            rows[4]["message"]["payload"]["idempotency_key"] = "execution:other"
    result, _ = source(mutate, owner_snapshot=path)
    assert result["accepted_count"] == 0
    assert result["rejections"][0]["reason"] == {
        "actor": "owner_request_mismatch", "action": "owner_request_mismatch",
        "correlation": "owner_request_mismatch", "boundary": "owner_boundary_mismatch",
        "missing": "owner_receipt_missing",
    }[changed]


def test_corrupt_supplied_owner_snapshot_cannot_degrade_to_unverified(source, owner_snapshot):
    path, bind, _ = owner_snapshot()
    path.write_text('{}', encoding="utf-8")
    with pytest.raises(ValueError, match="owner_snapshot_invalid"):
        source(bind, owner_snapshot=path)


def test_export_matches_original_l4_executor_requests_for_worktable_cycle(tmp_path, monkeypatch):
    """Controlled choices, real L3/L4/owner: avoid hand-authoring owner requests."""
    from test_character_object_execution import vertical
    from test_character_worktable_vertical import selected_contract
    from app.character_agent.planning.l3_planner import CharacterAgentL3Service

    monkeypatch.setenv("CHARACTER_LAYA_ENDPOINT", "http://unused.invalid/v1/systemone")
    prepared_requests = []
    prepare = CharacterAgentL3Service.prepare_intent_plan

    def capture(self, *args, **kwargs):
        prepared = prepare(self, *args, **kwargs)
        prepared_requests.append(json.loads(prepared.request_json))
        return prepared

    monkeypatch.setattr(CharacterAgentL3Service, "prepare_intent_plan", capture)
    provider = LayaSystemOneProvider(endpoint="http://unused.invalid/v1/systemone",
        option_tokenizer=lambda _: [1], tokenizer_sha256="sha256:synthetic")
    rows, receipts = [], []
    with vertical(tmp_path, target="obj_worktable", intent="use_object", action="action:use") as (
        execution, runtime, owner, source, world, sessions, clock, _
    ):
        for sequence, intent in enumerate(("use_object", "finish_use"), 1):
            contract = selected_contract(runtime, owner, sessions, intent, sequence)
            execution.offer(contract)
            result, receipt = execution.execute(contract)[2:]
            receipts.append(receipt.transaction_id)
            prepared = prepared_requests[-1]
            rows.extend([
                {"kind": "laya_enter", "frozen_request": prepared},
                {"kind": "laya_http_result", "call": {"request": provider.build_wire_request(prepared),
                    "response": {"answers": {"choice": {"choice": f"{intent}:obj_worktable"}},
                        "usage": {"truncated": False, "state_tokens_dropped": 0, "truncated_questions": []}}}},
                {"kind": "execution_input", "contract": contract.model_dump(mode="json")},
                {"kind": "wire_output", "message": {"message_type": "world_result",
                    "payload": result.model_dump(mode="json")}},
            ])
        snapshot = tmp_path / "original-owner.json"
        world.save_snapshot(snapshot)
    trace = tmp_path / "original-runtime.jsonl"
    trace.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    before = snapshot.read_bytes()
    exported = export_runtime_trace(trace, provider=provider, owner_snapshot=snapshot)
    assert exported["accepted_count"] == 2, exported["rejections"]
    assert exported["rejections"] == []
    assert [row["owner_evidence"]["transaction_id"] for row in exported["records"]] == receipts
    assert all(row["owner_store_validation"] == "snapshot_matched" for row in exported["records"])
    assert exported["formal_eligible"] is False
    assert snapshot.read_bytes() == before
