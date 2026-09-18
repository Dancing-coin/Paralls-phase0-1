from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from common import verification_dir


SUPPORTED_SCHEMA_VERSION = 1
KNOWN_CANDIDATE_STATUSES = {"proposed", "evaluated", "rejected", "promoted"}
KNOWN_CANDIDATE_LIFECYCLE_STAGES = {"proposed", "qa-review", "promotion-ready", "promoted", "rejected"}
KNOWN_RISK_TIERS = {"read-only", "sandbox-edit", "full-access"}
KNOWN_EFFECTIVENESS = {"not_evaluated", "accepted", "rejected"}
HARNESS_MUTATION_PREFIXES = (
    ".harness/",
    "scripts/verification/",
)
HARNESS_MUTATION_EXACT_PATHS = {
    ".github/workflows/harness.yml",
    "docs/harness.md",
    "docs/ai-engineering-workflow.md",
    "docs/harness-playbook.md",
    ".agents/skills/harness-verification/SKILL.md",
}


def _safe_relative_path(root: Path, reference: str) -> Path:
    normalized = reference.replace("\\", "/")
    if not normalized or normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
        raise ValueError(f"unsafe path reference: {reference}")
    path = (root / normalized).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"unsafe path reference: {reference}")
    return path


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) is not None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_path(project_root: Path, path: Path) -> str:
    return str(path.relative_to(project_root)).replace("\\", "/")


def _read_json(path: Path) -> tuple[dict[str, object], list[str]]:
    normalized = str(path).replace("\\", "/")
    if not path.exists():
        return {}, [f"{normalized}: missing"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, [f"{normalized}: invalid json"]
    except UnicodeDecodeError:
        return {}, [f"{normalized}: invalid text"]
    except OSError:
        return {}, [f"{normalized}: read error"]
    if not isinstance(payload, dict):
        return {}, [f"{normalized}: expected json object"]
    return payload, []


def _project_relative_read_json(project_root: Path, path: Path) -> tuple[dict[str, object], list[str]]:
    payload, errors = _read_json(path)
    if not errors:
        return payload, []
    relative = _relative_path(project_root, path) if path.is_relative_to(project_root) else str(path)
    return {}, [error.replace(str(path).replace("\\", "/"), relative) for error in errors]


def _is_non_empty_string_list(value: object) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(isinstance(entry, str) and entry != "" for entry in value)


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(entry, str) and entry != "" for entry in value)


def load_evolution_config(project_root: Path) -> tuple[dict[str, object], list[str]]:
    path = project_root / ".harness" / "evolution" / "config.json"
    payload, read_errors = _project_relative_read_json(project_root, path)
    if read_errors:
        return {}, read_errors

    errors: list[str] = []
    relative = ".harness/evolution/config.json"
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        errors.append(f"{relative}: unsupported schema_version {payload.get('schema_version')}")
    if not isinstance(payload.get("max_runs_to_analyze"), int) or int(payload.get("max_runs_to_analyze", 0)) <= 0:
        errors.append(f"{relative}: max_runs_to_analyze must be a positive integer")
    if not _is_non_empty_string_list(payload.get("profiles_in_scope")):
        errors.append(f"{relative}: profiles_in_scope must be a non-empty list of strings")
    if not _is_non_empty_string_list(payload.get("allowed_mutation_types")):
        errors.append(f"{relative}: allowed_mutation_types must be a non-empty list of strings")
    if not _is_non_empty_string_list(payload.get("promotion_requires_profiles")):
        errors.append(f"{relative}: promotion_requires_profiles must be a non-empty list of strings")
    return ({}, errors) if errors else (payload, [])


def load_replay_set(project_root: Path, replay_set_id: str) -> tuple[dict[str, object], list[str]]:
    if not _valid_identifier(replay_set_id):
        return {}, [f"unsafe replay set id: {replay_set_id}"]
    try:
        path = _safe_relative_path(project_root, f".harness/evolution/replay-sets/{replay_set_id}.json")
    except ValueError as exc:
        return {}, [str(exc)]
    payload, read_errors = _project_relative_read_json(project_root, path)
    if read_errors:
        return {}, read_errors

    errors: list[str] = []
    relative = f".harness/evolution/replay-sets/{replay_set_id}.json"
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        errors.append(f"{relative}: unsupported schema_version {payload.get('schema_version')}")
    if payload.get("id") != replay_set_id:
        errors.append(f"{relative}: id must match {replay_set_id}")
    profile_cases = payload.get("profile_cases")
    if not isinstance(profile_cases, list) or not profile_cases:
        errors.append(f"{relative}: profile_cases must be a non-empty list")
    else:
        for index, case in enumerate(profile_cases):
            if not isinstance(case, dict):
                errors.append(f"{relative}: profile_cases[{index}] must be an object")
                continue
            if not isinstance(case.get("profile"), str) or case.get("profile") == "":
                errors.append(f"{relative}: profile_cases[{index}].profile must be a non-empty string")
            if not _is_non_empty_string_list(case.get("expected_artifacts")):
                errors.append(f"{relative}: profile_cases[{index}].expected_artifacts must be a non-empty list of strings")
    if not _is_non_empty_string_list(payload.get("regression_guards")):
        errors.append(f"{relative}: regression_guards must be a non-empty list of strings")
    return ({}, errors) if errors else (payload, [])


def _is_harness_mutation_path(path: str) -> bool:
    if "\\" in path or ":" in path or ".." in path.split("/"):
        return False
    return path in HARNESS_MUTATION_EXACT_PATHS or any(path.startswith(prefix) for prefix in HARNESS_MUTATION_PREFIXES)


def _candidate_errors(relative: str, payload: dict[str, object], allowed_mutation_types: list[str]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        errors.append(f"{relative}: unsupported schema_version {payload.get('schema_version')}")
    for field in ("id", "status", "mutation_type", "risk_tier", "hypothesis", "replay_set"):
        if not isinstance(payload.get(field), str) or payload.get(field) == "":
            errors.append(f"{relative}: {field} must be a non-empty string")
    if payload.get("status") not in KNOWN_CANDIDATE_STATUSES:
        errors.append(f"{relative}: invalid status {payload.get('status')}")
    if not _valid_identifier(payload.get("id")):
        errors.append(f"{relative}: unsafe candidate id")
    if not _valid_identifier(payload.get("replay_set")):
        errors.append(f"{relative}: unsafe replay set id")
    if payload.get("effectiveness", "not_evaluated") not in KNOWN_EFFECTIVENESS:
        errors.append(f"{relative}: invalid effectiveness")
    for field in ("baseline_revision", "candidate_revision", "evaluation_set_digest"):
        if field in payload and not isinstance(payload[field], str):
            errors.append(f"{relative}: {field} must be a string")
    lifecycle_stage = payload.get("lifecycle_stage")
    if lifecycle_stage is not None:
        if not isinstance(lifecycle_stage, str) or lifecycle_stage == "":
            errors.append(f"{relative}: lifecycle_stage must be a non-empty string")
        elif lifecycle_stage not in KNOWN_CANDIDATE_LIFECYCLE_STAGES:
            errors.append(f"{relative}: invalid lifecycle_stage {lifecycle_stage}")
    if payload.get("risk_tier") not in KNOWN_RISK_TIERS:
        errors.append(f"{relative}: invalid risk_tier {payload.get('risk_tier')}")
    if payload.get("mutation_type") not in allowed_mutation_types:
        errors.append(f"{relative}: unsupported mutation_type {payload.get('mutation_type')}")
    if not _is_non_empty_string_list(payload.get("source_failures")):
        errors.append(f"{relative}: source_failures must be a non-empty list of strings")
    if not _is_non_empty_string_list(payload.get("promotion_checks")):
        errors.append(f"{relative}: promotion_checks must be a non-empty list of strings")
    if not isinstance(payload.get("requires_human_approval"), bool):
        errors.append(f"{relative}: requires_human_approval must be boolean")
    if payload.get("risk_tier") == "full-access" and payload.get("requires_human_approval") is not True:
        errors.append(f"{relative}: full-access candidates require human approval")
    if payload.get("qa_review_required") is not None and not isinstance(payload.get("qa_review_required"), bool):
        errors.append(f"{relative}: qa_review_required must be boolean")
    qa_review_artifacts = payload.get("qa_review_artifacts")
    if qa_review_artifacts is not None and not _is_string_list(qa_review_artifacts):
        errors.append(f"{relative}: qa_review_artifacts must be a list of strings")
    promotion_stage = "promoted" if payload.get("status") == "promoted" else lifecycle_stage
    if promotion_stage in {"promotion-ready", "promoted"} and not _is_non_empty_string_list(qa_review_artifacts):
        errors.append(f"{relative}: {promotion_stage} candidates require qa_review_artifacts")

    proposed_changes = payload.get("proposed_changes")
    if not isinstance(proposed_changes, list) or not proposed_changes:
        errors.append(f"{relative}: proposed_changes must be a non-empty list")
    else:
        for index, change in enumerate(proposed_changes):
            if not isinstance(change, dict):
                errors.append(f"{relative}: proposed_changes[{index}] must be an object")
                continue
            change_path = change.get("path")
            if not isinstance(change_path, str) or change_path == "":
                errors.append(f"{relative}: proposed_changes[{index}].path must be a non-empty string")
            elif not _is_harness_mutation_path(change_path):
                errors.append(f"{relative}: {change_path} is outside first-version harness mutation scope")
            if not isinstance(change.get("summary"), str) or change.get("summary") == "":
                errors.append(f"{relative}: proposed_changes[{index}].summary must be a non-empty string")
    return errors


def _evaluation_errors(project_root: Path, relative: str, candidate: dict[str, object]) -> list[str]:
    promotion = candidate.get("status") == "promoted" or candidate.get("lifecycle_stage") in {"promotion-ready", "promoted"}
    effectiveness = candidate.get("effectiveness", "not_evaluated")
    artifacts = candidate.get("qa_review_artifacts", [])
    if not promotion and effectiveness == "not_evaluated" and not artifacts:
        return []
    errors: list[str] = []
    if promotion and effectiveness != "accepted":
        errors.append(f"{relative}: promotion requires accepted effectiveness")
    if not artifacts:
        return [*errors, f"{relative}: evaluated effectiveness requires evaluation evidence"]
    for field in ("baseline_revision", "candidate_revision", "evaluation_set_digest"):
        if not isinstance(candidate.get(field), str) or not candidate[field].strip():
            errors.append(f"{relative}: evaluation requires {field}")
    if candidate.get("baseline_revision") == candidate.get("candidate_revision"):
        errors.append(f"{relative}: baseline and candidate revisions must differ")
    config, config_errors = load_evolution_config(project_root)
    errors.extend(config_errors)
    missing_checks = set(config.get("promotion_requires_profiles", [])) - set(candidate["promotion_checks"])
    if missing_checks:
        errors.append(f"{relative}: missing configured promotion checks: {', '.join(sorted(missing_checks))}")
    replay_set, replay_errors = load_replay_set(project_root, str(candidate["replay_set"]))
    errors.extend(replay_errors)
    if replay_set:
        replay_path = _safe_relative_path(project_root, f".harness/evolution/replay-sets/{candidate['replay_set']}.json")
        if candidate.get("evaluation_set_digest") != _sha256(replay_path):
            errors.append(f"{relative}: evaluation_set_digest does not match replay set content")
    digests = candidate.get("qa_review_artifact_digests", {})
    if not isinstance(digests, dict):
        digests = {}
    for reference in artifacts:
        try:
            path = _safe_relative_path(project_root, reference)
        except ValueError as exc:
            errors.append(f"{relative}: {exc}")
            continue
        review, read_errors = _project_relative_read_json(project_root, path)
        if read_errors:
            errors.extend(read_errors)
            continue
        if digests.get(reference) != _sha256(path):
            errors.append(f"{relative}: evaluation content digest mismatch: {reference}")
            continue
        identity = {"schema_version": 1, "candidate_id": candidate["id"]}
        identity.update({field: candidate.get(field) for field in ("baseline_revision", "candidate_revision", "evaluation_set_digest")})
        for field, expected in identity.items():
            if review.get(field) != expected:
                errors.append(f"{relative}: evaluation {field} mismatch: {reference}")
        if review.get("effectiveness") != effectiveness or review.get("overall_evaluation_passed") is not (effectiveness == "accepted"):
            errors.append(f"{relative}: evaluation conclusion does not match candidate: {reference}")
        if review.get("criteria_unchanged") is not True:
            errors.append(f"{relative}: evaluation criteria must remain unchanged: {reference}")
        reason_field = "rejection_reason" if effectiveness == "rejected" else "acceptance_reason"
        if not isinstance(review.get(reason_field), str) or not review[reason_field].strip():
            errors.append(f"{relative}: evaluation requires {reason_field}: {reference}")
        results = review.get("results")
        if not isinstance(results, list) or not results:
            errors.append(f"{relative}: evaluation requires execution results: {reference}")
            continue
        seen: set[tuple[str, str]] = set()
        run_revisions: dict[str, str] = {}
        for result in results:
            if not isinstance(result, dict):
                errors.append(f"{relative}: invalid execution result: {reference}")
                continue
            revision = result.get("revision")
            profile = result.get("profile")
            exit_code = result.get("exit_code")
            valid = (
                isinstance(result.get("run_id"), str) and bool(result["run_id"].strip())
                and isinstance(profile, str) and bool(profile)
                and revision in (candidate.get("baseline_revision"), candidate.get("candidate_revision"))
                and type(exit_code) is int
                and result.get("status") == ("passed" if exit_code == 0 else "failed")
            )
            if not valid or (effectiveness == "accepted" and revision == candidate.get("candidate_revision") and exit_code != 0):
                errors.append(f"{relative}: execution result failed or has invalid identity: {reference}")
                continue
            run_id = result["run_id"]
            if run_id in run_revisions and run_revisions[run_id] != revision:
                errors.append(f"{relative}: execution run_id reused across revisions: {reference}")
                continue
            run_revisions[run_id] = revision
            seen.add((revision, profile))
        required_profiles = set(candidate["promotion_checks"])
        required_profiles.update(case["profile"] for case in replay_set.get("profile_cases", []))
        for revision in (candidate.get("baseline_revision"), candidate.get("candidate_revision")):
            for profile in sorted(required_profiles):
                if (revision, profile) not in seen:
                    errors.append(f"{relative}: missing {profile} execution for revision {revision}: {reference}")
    return errors


def load_candidate_manifests(
    project_root: Path,
    *,
    allowed_mutation_types: list[str],
) -> tuple[list[dict[str, object]], list[str]]:
    candidates_dir = project_root / ".harness" / "evolution" / "candidates"
    candidates: list[dict[str, object]] = []
    errors: list[str] = []
    if not candidates_dir.exists():
        return candidates, errors
    for path in sorted(candidates_dir.glob("*.json")):
        relative = _relative_path(project_root, path)
        try:
            _safe_relative_path(project_root, relative)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        payload, read_errors = _project_relative_read_json(project_root, path)
        if read_errors:
            errors.extend(read_errors)
            continue
        candidate_errors = _candidate_errors(relative, payload, allowed_mutation_types)
        if not candidate_errors:
            candidate_errors.extend(_evaluation_errors(project_root, relative, payload))
        if candidate_errors:
            errors.extend(candidate_errors)
            continue
        candidates.append({"baseline_revision": "", "candidate_revision": "", "evaluation_set_digest": "", "effectiveness": "not_evaluated", **payload})
    return candidates, errors


def _recent_run_manifests(input_root: Path | None, max_runs: int) -> list[tuple[Path, dict[str, object]]]:
    if input_root is None:
        return []
    if not input_root.is_dir():
        raise ValueError(f"input root is not a directory: {input_root}")
    manifests: list[tuple[Path, dict[str, object]]] = []
    paths = [*input_root.rglob("run-manifest.json"), *input_root.rglob("harness-run-manifest.json")]
    for path in sorted(paths, reverse=True)[:max_runs]:
        path = _safe_relative_path(input_root, _relative_path(input_root, path))
        payload, errors = _project_relative_read_json(input_root, path)
        if errors:
            raise ValueError("; ".join(errors))
        if payload.get("schema_version") != 1 or not isinstance(payload.get("run_id"), str) or not payload["run_id"]:
            raise ValueError(f"invalid run manifest identity: {path}")
        entries = payload.get("profile_exit_codes")
        if not isinstance(entries, list) or any(
            not isinstance(entry, dict) or not isinstance(entry.get("profile"), str) or not entry["profile"]
            or type(entry.get("exit_code")) is not int for entry in entries
        ):
            raise ValueError(f"invalid profile_exit_codes: {path}")
        if not _is_string_list(payload.get("failure_digest_artifacts", [])):
            raise ValueError(f"invalid failure_digest_artifacts: {path}")
        if any(item[1]["run_id"] == payload["run_id"] for item in manifests):
            raise ValueError(f"duplicate run_id: {payload['run_id']}")
        manifests.append((path, payload))
    return list(reversed(manifests))


def _load_digest(input_root: Path, digest_ref: str) -> dict[str, object] | None:
    path = _safe_relative_path(input_root, digest_ref)
    payload, errors = _project_relative_read_json(input_root, path)
    return None if errors else payload


def _suggested_mutation_type(profile: str) -> str:
    if profile == "docs":
        return "docs_gate"
    if profile in {"phase0", "phase1-slice", "character-agent-execution"}:
        return "failure_digest"
    return "validator"


def analyze_harness_evolution(project_root: Path, config: dict[str, object], *, input_root: Path | None = None) -> dict[str, object]:
    max_runs = int(config.get("max_runs_to_analyze", 20))
    profiles_in_scope = set(str(profile) for profile in config.get("profiles_in_scope", []))
    manifests = _recent_run_manifests(input_root, max_runs)
    if not manifests:
        return {
            "schema_version": 1,
            "overall_harness_evolution_analyzed": True,
            "history_status": "insufficient_history",
            "effectiveness": "not_evaluated",
            "run_ids_analyzed": [],
            "failure_patterns": [],
            "check_patterns": [],
            "telemetry_gaps": [],
            "candidate_recommendations": [],
            "results": [],
        }

    profile_failures: dict[str, list[str]] = defaultdict(list)
    check_failures: dict[tuple[str, str], list[str]] = defaultdict(list)
    telemetry_gaps: list[dict[str, object]] = []
    run_ids: list[str] = []

    for manifest_path, manifest in manifests:
        run_id = str(manifest.get("run_id", ""))
        if run_id:
            run_ids.append(run_id)
        for entry in manifest.get("profile_exit_codes", []):
            if not isinstance(entry, dict):
                continue
            profile = str(entry.get("profile", ""))
            if profiles_in_scope and profile not in profiles_in_scope:
                continue
            if int(entry.get("exit_code", 0)) != 0:
                profile_failures[profile].append(run_id)
        for digest_ref in manifest.get("failure_digest_artifacts", []):
            if not isinstance(digest_ref, str):
                continue
            digest = _load_digest(manifest_path.parent, digest_ref)
            if digest is None:
                telemetry_gaps.append({"id": "missing_digest_ref", "run_id": run_id, "path": digest_ref})
                continue
            if digest.get("run_id") != run_id:
                raise ValueError(f"digest run_id mismatch: {digest_ref}")
            profile = str(digest.get("profile", ""))
            if profiles_in_scope and profile not in profiles_in_scope:
                continue
            for check in digest.get("failed_checks", []):
                if isinstance(check, dict) and isinstance(check.get("id"), str):
                    check_failures[(profile, str(check["id"]))].append(run_id)

    failure_patterns = [
        {
            "id": f"repeated_profile_failure.{profile}",
            "profile": profile,
            "failure_count": len(failures),
            "run_ids": failures,
            "suggested_mutation_type": _suggested_mutation_type(profile),
            "confidence": "medium" if len(failures) >= 2 else "low",
        }
        for profile, failures in sorted(profile_failures.items())
        if failures
    ]
    check_patterns = [
        {
            "id": f"repeated_check_failure.{profile}.{check_id}",
            "profile": profile,
            "check_id": check_id,
            "failure_count": len(failures),
            "run_ids": failures,
        }
        for (profile, check_id), failures in sorted(check_failures.items())
        if len(failures) >= 2
    ]

    return {
        "schema_version": 1,
        "overall_harness_evolution_analyzed": True,
        "history_status": "analyzed",
        "effectiveness": "not_evaluated",
        "run_ids_analyzed": run_ids,
        "failure_patterns": failure_patterns,
        "check_patterns": check_patterns,
        "telemetry_gaps": telemetry_gaps,
        "candidate_recommendations": failure_patterns[:1],
        "results": [],
    }


def build_candidate_from_analysis(
    *,
    candidate_id: str,
    analysis: dict[str, object],
    config: dict[str, object],
    replay_set_id: str,
) -> dict[str, object]:
    patterns = analysis.get("failure_patterns", [])
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("No failure patterns available for candidate generation.")
    pattern = patterns[0]
    if not isinstance(pattern, dict):
        raise ValueError("Invalid failure pattern.")
    profile = str(pattern["profile"])
    mutation_type = str(pattern.get("suggested_mutation_type", "validator"))
    proposed_path = "scripts/verification/check_docs.py" if mutation_type == "docs_gate" else "scripts/verification/evidence.py"
    proposed_summary = (
        "Tighten docs_gate diagnostics for repeated docs profile failures."
        if mutation_type == "docs_gate"
        else f"Tighten {mutation_type} diagnostics for repeated {profile} profile failures."
    )
    return {
        "schema_version": 1,
        "id": candidate_id,
        "status": "proposed",
        "lifecycle_stage": "proposed",
        "mutation_type": mutation_type,
        "risk_tier": "sandbox-edit",
        "source_failures": [*list(pattern.get("run_ids", [])), profile],
        "hypothesis": f"Repeated {profile} profile failures suggest a harness-owned {mutation_type} improvement may be needed.",
        "proposed_changes": [
            {
                "path": proposed_path,
                "summary": proposed_summary,
            }
        ],
        "replay_set": replay_set_id,
        "promotion_checks": list(config.get("promotion_requires_profiles", [])),
        "requires_human_approval": False,
        "qa_review_required": True,
        "qa_review_artifacts": [],
        "qa_review_artifact_digests": {},
        "baseline_revision": "",
        "candidate_revision": "",
        "evaluation_set_digest": "",
        "effectiveness": "not_evaluated",
    }


def write_candidate_manifest(project_root: Path, candidate: dict[str, object]) -> Path:
    candidate_id = str(candidate["id"])
    if not _valid_identifier(candidate_id):
        raise ValueError(f"unsafe candidate id: {candidate_id}")
    path = _safe_relative_path(project_root, f".harness/evolution/candidates/{candidate_id}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"{candidate_id}.json already exists")
    path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def evaluate_harness_evolution(project_root: Path) -> dict[str, object]:
    config, config_errors = load_evolution_config(project_root)
    replay_set, replay_errors = load_replay_set(project_root, "default")
    candidates, candidate_errors = load_candidate_manifests(
        project_root,
        allowed_mutation_types=list(config.get("allowed_mutation_types", [])) if config else [],
    )
    report_path = verification_dir(project_root) / "harness-evolution-report.json"
    report, report_errors = _project_relative_read_json(project_root, report_path)

    results = [
        _result(
            "evolution_config_valid",
            "Harness evolution config exists and validates",
            bool(config) and not config_errors,
            [".harness/evolution/config.json"],
            "\n".join(config_errors),
        ),
        _result(
            "evolution_replay_set_valid",
            "Default harness evolution replay set exists and validates",
            bool(replay_set) and not replay_errors,
            [".harness/evolution/replay-sets/default.json"],
            "\n".join(replay_errors),
        ),
        _result(
            "evolution_candidates_governed",
            "Candidate manifests are schema-valid, scoped, and approval-gated",
            not candidate_errors,
            [".harness/evolution/candidates/"],
            "\n".join(candidate_errors),
        ),
        _result(
            "evolution_candidate_lifecycle_governed",
            "Candidate lifecycle stages require QA/replay evidence before promotion",
            not candidate_errors,
            [".harness/evolution/candidates/"],
            "\n".join(candidate_errors),
        ),
        _result(
            "evolution_report_exists",
            "Harness evolution report exists after analyzer execution",
            bool(report) and report.get("schema_version") == 1 and report.get("overall_harness_evolution_analyzed") is True,
            [str(report_path)],
            "\n".join(report_errors),
        ),
    ]
    return {
        "results": results,
        "candidate_count": len(candidates),
        "effectiveness": "not_evaluated",
        "overall_harness_evolution_passed": all(str(entry["status"]) == "proved" for entry in results),
    }
