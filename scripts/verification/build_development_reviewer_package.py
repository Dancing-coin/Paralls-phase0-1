"""Build a sanitized, pre-scoring reviewer input package for development v4.

The package intentionally contains no policy roles, acceptable paths, grades,
provider responses, rationale, or sealed split material.  The reviewer must
return a separate truth manifest before any score is accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.character_agent.planning.l3_planner import CandidateCompiler

FORBIDDEN = {
    "acceptable_paths", "acceptable_pairs", "acceptable_action_set", "gold",
    "grading", "offline_grading", "raw_response", "mapped_result", "provider_response",
    "rationale", "original_reviewer_rationale", "development-policy", "calibration",
    "final", "independent_holdout", "expected_choice", "role_expectation",
}


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _assert_clean(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN:
                raise ValueError(f"reviewer_package_forbidden_field:{path}.{key}")
            _assert_clean(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_clean(child, f"{path}[{index}]")
    elif isinstance(value, str):
        for token in ("acceptable_paths", "acceptable_pairs", "reviewer rationale", "development-policy", "provider_response"):
            if token in value.lower():
                raise ValueError(f"reviewer_package_forbidden_value:{path}")


def _candidate_records(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for ref in scenario.get("candidate_refs", []):
        intent, target = str(ref).split(":", 1)
        family = intent
        records.append({
            "candidate_id": ref,
            "wire_label": ref,
            "action_family": family,
            "semantic_intent_id": intent,
            "target_refs": {"target": target},
            "required_conditions": {"visibility": "satisfied"},
            "target_visibility": "visible",
            "target_provenance": ["development:scenario-visible-target"],
            "affordance_result": {"status": "available", "reason": "registered fixture candidate"},
            "owner_route": "unassigned",
            "revision_pins": {"runtime_legality": "unverified"},
        })
    return records


def _role_condition(data: dict[str, Any], role: str) -> dict[str, Any]:
    path = ROOT / data["source_ref"].split("#", 1)[0]
    original = yaml.safe_load(path.read_text(encoding="utf-8"))
    if role == "char_d":
        # The only admitted qualitative condition here has an explicit source;
        # other authored claims do not fill unavailable numeric schema fields.
        excerpts = {"claims": [claim for entry in original["sources"] for claim in entry.get("claims", []) if claim == "reliable_fixed_procedure"]}
    else:
        layer = original["capability_constraint_layer"]
        excerpts = {key: layer[key] for key in ("skills", "psychological_constraints", "social_constraints")}
    unavailable = list(dict.fromkeys(data.get("unavailable_fields", []) + ["cognitive_facets", "hard_limits", "compute_defaults", "authority_owner_binding"]))
    return {"source_ref": data["source_ref"], "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "supported_facts": data.get("supported_facts", []), "source_excerpts": excerpts,
            "unavailable_fields": unavailable}


def build(*, role_sensitive_path: Path, development_package: dict[str, Any]) -> dict[str, Any]:
    source = yaml.safe_load(role_sensitive_path.read_text(encoding="utf-8"))
    scenarios = [dict(row, cohort="role_sensitive") for row in source.get("scenarios", [])]
    if not scenarios or any(item.get("split") != "development" for item in scenarios):
        raise ValueError("role_sensitive_development_only_required")
    reviewer_scenarios = []
    role_conditions = source.get("role_conditions", {})
    seen_original = {}
    for record in development_package.get("records", []):
        if record.get("split") != "development":
            raise ValueError("development_only_source_required")
        evidence = record["visible_evidence"]
        scenario = {
            "scenario_id": record["scenario_id"], "trajectory_group": record["trajectory_group"],
            "split": "development", "question_kind": "explicit_instruction_diagnostic",
            "cohort": "description_frozen_regression", "event": evidence["event"],
            "question": evidence["question"], "visible_targets": evidence["targets"],
            "candidate_refs": record["complete_u"], "role_condition_refs": list(role_conditions),
        }
        prior = seen_original.setdefault(scenario["scenario_id"], scenario)
        if prior != scenario:
            raise ValueError("development_role_facts_disagree")
    scenarios = list(seen_original.values()) + scenarios
    for scenario in scenarios:
        candidate_records = _candidate_records(scenario)
        compiled = CandidateCompiler().compile(
            candidates=candidate_records,
            envelope={"allowed_action_families": ["observe", "ask_probe", "defer"], "max_candidate_intents": 3},
            visible_targets=set(scenario.get("visible_targets", [])),
        )
        reviewer_scenarios.append({
            "scenario_id": scenario["scenario_id"],
            "trajectory_group": scenario["trajectory_group"],
            "question_kind": scenario["question_kind"],
            "cohort": scenario["cohort"],
            "facts": {"event": scenario["event"], "question": scenario["question"], "visible_targets": scenario["visible_targets"]},
            "role_conditions": {
                role: _role_condition(data, role)
                for role, data in role_conditions.items()
                if role in scenario.get("role_condition_refs", [])
            },
            "common_constraints": source["constraints"]["common_privacy_authority_constraint"],
            "candidate_records": candidate_records,
            "candidates": [
                {
                    "label": item["wire_label"],
                    "candidate_id": item["candidate_id"],
                    "action_family": item["action_family"],
                    "target_refs": item["target_refs"],
                    "description": item["description"],
                    "target_visibility": item["target_visibility"],
                    "runtime_legality": "unverified",
                    "owner_permission": "unverified",
                    "actual_speech": "unverified",
                    "execution_receipt": "unverified",
                }
                for item in compiled.presented
            ],
            "mapping_digest": compiled.digest,
        })
    package = {
        "schema": "development-reviewer-input-v4",
        "candidate_description_contract": {
            "frozen": True,
            "version": CandidateCompiler.DESCRIPTION_CONTRACT_REVISION,
            "compiler_sha256": hashlib.sha256((ROOT / "backend/app/character_agent/planning/l3_planner.py").read_bytes()).hexdigest(),
        },
        "review_only": True,
        "split": "development",
        "source_revision": _digest(source),
        "development_package_digest": _digest(development_package),
        "independent_review_approved": False,
        "approval_rule": "freeze acceptable action sets and reasons in a separate reviewer truth manifest before model calls",
        "truth_schema": {
            "input_sha256": "SHA256 of the exact input file bytes", "read_log": "absolute paths actually read",
            "accidental_exposure": "list of any exposure; empty only if none",
            "judgments": "one per scenario_id and actor_id; question_kind; allowed action-family/target pairs; pair_sources; unacceptable_reasons; unknowns; required_role_difference and its source; all execution boundary fields unverified",
        },
        "rubric": {
            "freeze_before_model_call": True,
            "record_acceptable_action_set_sources": True,
            "record_unacceptable_reasons": True,
            "record_unknown_scope": True,
            "keep_runtime_legality_owner_permission_actual_speech_execution_receipt_unverified": True,
            "score_tracks_separately": ["autonomous_decision", "explicit_instruction_diagnostic"],
        },
        "scenarios": reviewer_scenarios,
    }
    _assert_clean(package)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role-sensitive", type=Path, required=True)
    parser.add_argument("--development-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = build(
        role_sensitive_path=args.role_sensitive,
        development_package=json.loads(args.development_package.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "reviewer_package_created", "scenarios": len(package["scenarios"]), "independent_review_approved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
