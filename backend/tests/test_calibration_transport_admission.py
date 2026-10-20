from __future__ import annotations

import json
import sys

import pytest

from scripts.verification import run_calibration_diagnostic as runner


def response(choice="C1"):
    return {"answers": {"choice": {"choice": choice}},
            "usage": {"truncated": False, "state_tokens_dropped": 0}}


@pytest.fixture
def transport(tmp_path, monkeypatch):
    inputs = tmp_path / "inputs.json"
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "output"
    prepared = {"inputs_digest": "synthetic", "prepared_records": [
        {"question_id": qid, "track": "synthetic", "split": "dev",
         "prepared_request": {"task_kind": "l3_planning", "context": {
             "laya_state": "synthetic", "candidate_intents": ["C1", "C2"]}}}
        for qid in ["q1", "q2"]]}
    metadata = {"formal_question_ids": ["q1", "q2"]}
    inputs.write_text(json.dumps(prepared), encoding="utf-8")
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    health = {"status": "ok", "loaded": ["multilingual"],
              "revisions": {"multilingual": runner.LayaSystemOneProvider.CHECKPOINT_REVISION},
              "device": "cpu", "checkpoint_devices": {"multilingual": "cpu"}}
    real_provider = runner.LayaSystemOneProvider

    class SyntheticProvider(real_provider):
        def __init__(self, **kw):
            super().__init__(endpoint=kw["endpoint"], option_tokenizer=lambda _: [1], tokenizer_sha256="synthetic")

    monkeypatch.setattr(runner, "LayaSystemOneProvider", SyntheticProvider)
    monkeypatch.setattr(runner, "_health", lambda *args: health)
    monkeypatch.setattr(sys, "argv", ["runner", "--inputs", str(inputs), "--manifest", str(manifest),
        "--output", str(output), "--tokenizer", "unused", "--tokenizer-sha256", "synthetic"])
    calls = []

    def run(answers):
        pending = iter([response(), *answers])

        def post(*args):
            calls.append(args[1])
            answer = next(pending)
            return answer, json.dumps(answer).encode(), None

        monkeypatch.setattr(runner, "_post", post)
        code = runner.main()
        return code, json.loads((output / "run-envelope.json").read_text(encoding="utf-8"))

    return run, calls, inputs, manifest, output, prepared, metadata


@pytest.mark.parametrize("bad", [response("C9"), response(""), response(42),
    {"answers": []}, {"answers": {"choice": []}}, {"answers": "malformed"},
    {"answers": {"choice": "malformed"}},
    {"answers": {"choice": {"choice": "C1"}}, "usage": {"truncated": False, "state_tokens_dropped": False}}])
def test_invalid_response_seals_first_failure_and_never_calls_next_question(transport, bad):
    run, calls, *_ = transport
    code, archive = run([bad, response()])
    assert code == 2
    assert len(calls) == 2  # synthetic preflight + first formal question
    assert archive["run_status"]["executed_count"] == 1
    assert archive["records"][0]["invalid_category"]
    assert archive["records"][0]["response_body"] == bad


def test_valid_choices_seal_without_truth_or_retries(transport):
    run, calls, *_ = transport
    code, archive = run([response("C2"), response("C1")])
    assert code == 0
    assert len(calls) == 3
    assert archive["run_status"]["status"] == "sealed"
    assert archive["metadata"]["truth_loaded"] is False


def test_existing_archive_is_preserved_before_any_network_call(transport):
    run, calls, _, _, output, *_ = transport
    output.mkdir()
    sealed = output / "run-envelope.json"
    sealed.write_text("original sealed bytes", encoding="utf-8")
    with pytest.raises((SystemExit, ValueError, FileExistsError)):
        run([response(), response()])
    assert sealed.read_text(encoding="utf-8") == "original sealed bytes"
    assert not calls


@pytest.mark.parametrize("choice,wire_request", [("C9", {"questions": {"choice": {"criteria": {"C1": "one"}}}}),
                                           ("C1", None)])
def test_scorer_cannot_count_unbound_or_out_of_set_choice(choice, wire_request):
    from app.character_agent.evaluation.calibration_contracts import score_calibration_records

    records = [{"question_id": "q1", "track": "synthetic", "request": wire_request,
                "response": {"choice": choice}, "usage": {"truncated": False, "state_tokens_dropped": 0}}]
    result = score_calibration_records(records, {"q1": {"acceptable_action_set": [choice]}},
        formal_denominators={"synthetic": 1}, minimum_valid={"synthetic": 1})
    assert result["status"] == "blocked_minimum_valid_samples"
    assert result["tracks"]["synthetic"]["valid_samples"] == 0


@pytest.mark.parametrize("kind", ["manifest_duplicate", "prepared_duplicate", "empty_manifest"])
def test_ambiguous_or_empty_question_coverage_rejected_before_transport(transport, kind):
    run, calls, inputs, manifest, _, prepared, metadata = transport
    if kind == "manifest_duplicate":
        metadata["formal_question_ids"].append("q1")
    elif kind == "prepared_duplicate":
        prepared["prepared_records"][1]["question_id"] = "q1"
    else:
        metadata["formal_question_ids"] = []
    inputs.write_text(json.dumps(prepared), encoding="utf-8")
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises((SystemExit, ValueError)):
        run([response(), response()])
    assert not calls
