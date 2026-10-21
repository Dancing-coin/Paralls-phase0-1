"""Prepare independent calibration inputs offline; never author truth or call a model."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.planning.l3_planner import CandidateCompiler

INPUTS = ROOT / "backend/tests/fixtures/character_evaluation/calibration_preclosure_20261013"
TOKENIZER = Path("D:/laya-probe-cache/laya-multilingual/tokenizer/tokenizer.json")
MANIFEST_FIELDS = {"question_id", "source_revision", "split", "privacy_visibility", "expected_denominator_type"}
CALIBRATION_MAX_LEN = 2091
CALIBRATION_HEAD_MAX_LEN = 256


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: object) -> object:
    """Keep semantic content while removing actor identity and provenance annotations."""
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items() if k not in {
            "identity_core", "source_refs", "reference", "revision", "revision_pins", "actor_id",
            "target_actor_id", "canonical_name", "occupation_role", "aliases", "differences",
            "source_kind", "memory_id", "provenance", "difference_id", "source_revision",
        } and not k.endswith("_digest")}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return value


def validate_source_pins(records: list[dict], repo: Path = ROOT) -> None:
    for record in records:
        for difference in record["differences"]:
            if difference["source_kind"] not in {"profile_authored", "dossier_seed"}:
                continue
            relative = difference["reference"].split("#", 1)[0]
            path = (repo / relative).resolve()
            if repo.resolve() not in path.parents or not path.is_file():
                raise ValueError("source pin path missing or outside repository")
            if difference["revision"] != file_digest(path):
                raise ValueError("declared source revision is stale")


def prepare_record(record: dict, provider: LayaSystemOneProvider) -> dict:
    actor = record["actor_id"]
    if actor not in {"char_a", "char_b", "char_c", "char_d"}:
        raise ValueError("unregistered fixture actor")
    profile = {}
    if actor != "char_d":
        profile = yaml.safe_load((ROOT / f"assets/characters/profiles/{actor}.yaml").read_text(encoding="utf-8"))
    # Identity is irrelevant to the question and is excluded before projection.
    profile = sanitize(profile)
    target_names = list(dict.fromkeys(e["target_ref"] for e in record["visible_evidence"]))
    target_names.extend(v for c in record["candidate_records"] for v in c["target_refs"].values() if v not in target_names)
    target_aliases = {name: f"T{i + 1}" for i, name in enumerate(dict.fromkeys(target_names))}
    source_memories = [{"summary": m["text"]} for m in record["memories"]]
    event = {"facts": [f["text"] for f in record["facts"]],
             "constraints": [("Must not " + c["text"]) if any(key in c.get("reference", "") for key in
                              ["virtue_value_layer.red_lines", "virtue_value_layer.forbidden_behaviors"])
                             else c["text"] for c in record["constraints"]],
             "visible_evidence": [{**sanitize(e), "target_ref": target_aliases[e["target_ref"]]} for e in record["visible_evidence"]],
             "target_catalog": {alias: name for name, alias in target_aliases.items()},
             "unknown": record["unknown"], "unknown_dimensions": record["unknown_dimensions"]}
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id=actor, producer_ts=1, effective_profile=profile,
        memory_bundle={"event_memories": source_memories}, event_inbox=[event],
        current_goal_state={"primary_goal": record["goals"][0]["text"],
                            "goals": [g["text"] for g in record["goals"]]},
        dossier_projection={"relationship_seeds": {"relationships": sanitize(record["relationships"])}}
        if record["relationships"] else None,
    )
    projected = {}
    for layer in ["enduring_truth", "memory_evidence", "runtime_state"]:
        cards = getattr(frame, layer).cards
        projected[layer] = [{"factor_type": c.factor_type, "summary": c.summary,
                             "payload": sanitize(c.payload)} for c in cards
                            if c.factor_type != "effective_profile" and (c.summary or c.payload)]
    projected["event_inbox"] = sanitize(frame.cognition_workspace.event_inbox)
    state = json.dumps(projected, ensure_ascii=False, sort_keys=True)
    for forbidden in ["char_a", "char_b", "char_c", "char_d", "Lin Yue", "Qiao Ren", "Shen Mo", "source_refs", "acceptable_actions", "rationale"]:
        if forbidden in state:
            raise ValueError(f"identity or annotation leaked into wire state: {forbidden}")
    candidates = deepcopy(record["candidate_records"])
    # Compact neutral labels preserve the complete candidate universe and mapping.
    for index, candidate in enumerate(candidates):
        candidate["wire_label"] = f"C{index + 1}"
        candidate["target_refs"] = {key: target_aliases[value] for key, value in candidate["target_refs"].items()}
    compilation = CandidateCompiler().compile(
        candidates=candidates,
        visible_targets=[target_aliases[e["target_ref"]] for e in record["visible_evidence"]],
    )
    context = {"laya_state": state, "candidate_intents": compilation.wire_labels,
               "frozen_candidates": compilation.presented, "candidate_mapping": compilation.by_wire_label,
               "candidate_digest": compilation.digest, "provider_revision": provider.PROVIDER_REVISION,
               "option_token_validation_required": True, "option_tokenizer_sha256": provider.tokenizer_sha256}
    context.update({"max_len": CALIBRATION_MAX_LEN, "head_max_len": CALIBRATION_HEAD_MAX_LEN,
                    "input_budget_required": True})
    request = {"task_kind": "l3_planning", "context": context}
    wire = provider.build_wire_request(request)
    trace = {
        "facts": "cognition_workspace.event_inbox[0].facts",
        "visible_evidence": "cognition_workspace.event_inbox[0].visible_evidence",
        "constraints": "cognition_workspace.event_inbox[0].constraints",
        "goals": next((f"runtime_state.cards[{i}].payload.current_goal_state.goals" for i, c in enumerate(frame.runtime_state.cards) if c.factor_type == "goal_context"), None),
        "memories": next((f"memory_evidence.cards[{i}].payload.active_anchors" for i, c in enumerate(frame.memory_evidence.cards) if c.factor_type == "cognitive_anchor"), None),
        "relationships": next((f"memory_evidence.cards[{i}].payload.relationships" for i, c in enumerate(frame.memory_evidence.cards) if c.factor_type == "relationship_seed_context"), None),
    }
    return {"question_id": record["question_id"], "scenario_id": record["scenario_id"],
            "trajectory_group": record["trajectory_group"], "track": record["track"],
            "split": record["split"], "frame": frame.model_dump(mode="json"),
            "prepared_request": request, "wire": wire, "wire_digest": digest(wire),
            "U": compilation.universe, "P": compilation.presented,
            "compiler_diagnostics": compilation.diagnostics,
            "target_aliases": target_aliases,
            "actual_projection_paths": trace,
            "option_token_audit": deepcopy(provider.last_option_token_audit),
            "input_budget": deepcopy(provider.last_input_budget),
            "formal_denominator_expected": record["formal_denominator_expected"]}


def verify_approvals(report: dict, question_ids: list[str], inputs_digest: str,
                     allowed_read_paths: list[str]) -> bool:
    """Fail closed: disagreement, missing coverage or polluted reads cannot unlock calls."""
    for field in ["reviewer_independent_approval", "lead_audit_approval", "formal_truth_usable"]:
        if report.get(field) is not True:
            raise ValueError(f"approval missing: {field}")
    if report.get("inputs_digest") != inputs_digest:
        raise ValueError("approval input pin is stale")
    if report.get("accidental_exposure") != []:
        raise ValueError("accidental exposure was not cleared")
    covered = report.get("coverage_question_ids")
    if not isinstance(covered, list) or len(covered) != len(set(covered)) or set(covered) != set(question_ids):
        raise ValueError("approval coverage is incomplete")
    log = report.get("read_log")
    if not isinstance(log, dict) or log.get("unpolluted") is not True or not isinstance(log.get("paths"), list) or not log["paths"]:
        raise ValueError("unpolluted read log is required")
    allowed = {str(Path(p).resolve()) for p in allowed_read_paths}
    if any(str(Path(p).resolve()) not in allowed for p in log["paths"]):
        raise ValueError("read log contains an unapproved source")
    if len(allowed) != 1:
        raise ValueError("reviewer must read exactly the frozen review input")
    review_path = Path(next(iter(allowed)))
    pin = file_digest(review_path)
    if report.get("input_sha256") not in {pin, pin.removeprefix("sha256:")}:
        raise ValueError("review file byte pin is stale")
    frozen = json.loads(review_path.read_text(encoding="utf-8"))
    if frozen.get("inputs_digest") != inputs_digest:
        raise ValueError("review file input digest does not match approval")
    presentation = {}
    for record in frozen["records"]:
        labels = list(record.get("wire", {}).get("questions", {}).get("choice", {}).get("criteria", {}))
        candidate_ids = record.get("P_candidate_ids", [])
        if len(labels) != len(candidate_ids) or len(labels) != len(set(labels)) or len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("frozen presentation mapping is incomplete")
        presentation[record["question_id"]] = dict(zip(labels, candidate_ids))
    candidates = {r["question_id"]: {c["candidate_id"] for c in r["U"]} |
                  set(r.get("wire", {}).get("questions", {}).get("choice", {}).get("criteria", {}))
                  for r in frozen["records"]}
    tracks = {r["question_id"]: r["track"] for r in frozen["records"]}
    compiled = {r["question_id"]: {c["candidate_id"]: c for c in r["U"]} for r in frozen["records"]}
    judgments = report.get("judgments")
    if not isinstance(judgments, list) or len(judgments) != len(question_ids):
        raise ValueError("per-question judgments are required")
    if len({j.get("question_id") for j in judgments if isinstance(j, dict)}) != len(question_ids):
        raise ValueError("judgment coverage is incomplete or duplicated")
    boundaries = {"runtime_legality", "owner_permission", "actual_speech", "execution_receipt"}
    for judgment in judgments:
        qid = judgment.get("question_id")
        if qid not in candidates or judgment.get("track") != tracks[qid]:
            raise ValueError("judgment identity or track mismatch")
        for field in ["multiple_answers_allowed", "formal_denominator_computable", "source_supported_difference"]:
            if type(judgment.get(field)) is not bool:
                raise ValueError("judgment flags must be booleans")
        if not isinstance(judgment.get("difference_requirement"), str):
            raise ValueError("difference requirement is required")
        unknowns = judgment.get("unknowns")
        if not isinstance(unknowns, list) or not boundaries.issubset(set(unknowns)):
            raise ValueError("unverified boundaries must remain unknown")
        choices = judgment.get("acceptable_action_set")
        if not isinstance(choices, list):
            raise ValueError("judgment contains malformed candidate labels")
        labels = []
        for choice in choices:
            if isinstance(choice, str):
                label = choice
            elif isinstance(choice, dict):
                label = choice.get("label")
                cid = choice.get("candidate_id")
                if cid not in compiled[qid] or presentation[qid].get(label) != cid:
                    raise ValueError("structured judgment candidate pin mismatch")
                source_candidate = compiled[qid][cid]
                for field in ["action_family", "target_refs", "semantic_intent_id"]:
                    if field in choice and choice[field] != source_candidate.get(field):
                        raise ValueError("structured judgment semantics mismatch")
            else:
                raise ValueError("judgment contains malformed candidate labels")
            if isinstance(choice, str) and label not in presentation[qid] and label not in presentation[qid].values():
                raise ValueError("judgment choice is not in frozen presentation")
            labels.append(label)
        if any(not isinstance(v, str) or v not in candidates[qid] for v in labels) or len(labels) != len(set(labels)):
            raise ValueError("judgment contains malformed candidate labels")
        if judgment["formal_denominator_computable"] and not labels:
            raise ValueError("evaluable judgment needs an acceptable set")
        if len(labels) > 1 and not judgment["multiple_answers_allowed"]:
            raise ValueError("multiple labels contradict judgment flag")
    return True


def generate(output: Path, tokenizer: Path = TOKENIZER) -> dict:
    if not tokenizer.is_file():
        raise ValueError("pinned local tokenizer artifact is unavailable")
    source = json.loads((INPUTS / "inputs.json").read_text(encoding="utf-8"))
    manifest = json.loads((INPUTS / "metadata-manifest.json").read_text(encoding="utf-8"))
    if any(set(m) != MANIFEST_FIELDS for m in manifest):
        raise ValueError("metadata manifest must contain exactly five fields")
    records = source["records"]
    validate_source_pins(records)
    ids = [r["question_id"] for r in records]
    if len(ids) != len(set(ids)) or {m["question_id"] for m in manifest} != set(ids):
        raise ValueError("manifest/input coverage mismatch")
    provider = LayaSystemOneProvider(endpoint="http://offline.invalid", tokenizer_path=str(tokenizer),
                                    tokenizer_sha256=file_digest(tokenizer), require_option_token_validation=True)
    prepared = [prepare_record(r, provider) for r in records]
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("generated evidence must be outside the repository")
    output.mkdir(parents=True, exist_ok=True)
    review = {"schema_version": "calibration_preclosure_review_input.v1", "inputs_digest": digest(source),
              "records": [{"question_id": r["question_id"], "scenario_id": r["scenario_id"],
                           "trajectory_group": r["trajectory_group"], "track": r["track"],
                           "facts": sanitize(r["facts"]),
                           "source_excerpts": {k: sanitize(r[k]) for k in ["memories", "goals", "relationships", "constraints"]},
                           "constraint_semantics": [{"text": c["text"], "prohibited": any(key in c.get("reference", "") for key in
                                                       ["virtue_value_layer.red_lines", "virtue_value_layer.forbidden_behaviors"])} for c in r["constraints"]],
                           "source_validity": {"differences": r["differences"], "unknown_dimensions": r["unknown_dimensions"],
                                               "runtime_truth": False, "role_source_available": r["actor_id"] != "char_d"},
                           "wire": p["wire"], "U": [{k: c.get(k) for k in ["candidate_id", "action_family", "semantic_intent_id", "target_refs", "required_conditions", "description"]} for c in p["U"]],
                           "P_candidate_ids": [c["candidate_id"] for c in p["P"]],
                           "expected_denominator_type": manifest[i]["expected_denominator_type"]}
                          for i, (r, p) in enumerate(zip(records, prepared))]}
    pins = {"provider_revision": provider.PROVIDER_REVISION, "source_commit": provider.SOURCE_COMMIT,
            "checkpoint_revision": provider.CHECKPOINT_REVISION, "tokenizer_path": str(tokenizer.resolve()),
            "tokenizer_sha256": provider.tokenizer_sha256,
            "description_contract_revision": CandidateCompiler.DESCRIPTION_CONTRACT_REVISION,
            "code_sha256": {str(p.relative_to(ROOT)): file_digest(p) for p in [
                Path(__file__), ROOT / "backend/app/character_agent/mind/frame_builder.py",
                ROOT / "backend/app/character_agent/planning/l3_planner.py", ROOT / "backend/app/character_agent/gateway/laya_provider.py"]}}
    summary = {"schema_version": "calibration_preclosure_preparation.v1", "offline_only": True,
               "provider_calls": 0, "inputs_digest": digest(source), "pins": pins,
               "record_count": len(records), "status": "awaiting_independent_review_and_lead_audit",
               "reviewer_independent_approval": False, "lead_audit_approval": False, "formal_truth_usable": False,
               "formal_action_target_denominator": 0, "prepared_records": prepared}
    for name, value in [("review-input.json", review), ("prepared-inputs.json", summary), ("metadata-manifest.json", manifest)]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output": str(output), "records": len(records), "inputs_digest": digest(source),
            "provider_calls": 0, "pins": pins}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, default=TOKENIZER)
    args = parser.parse_args()
    print(json.dumps(generate(args.output, args.tokenizer), ensure_ascii=False))


if __name__ == "__main__":
    main()
