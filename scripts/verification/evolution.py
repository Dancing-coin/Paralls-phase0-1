from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


SUPPORTED_SCHEMA_VERSION = 1
KNOWN_CANDIDATE_STATUSES = {"proposed", "evaluated", "rejected", "promoted"}
KNOWN_RISK_TIERS = {"read-only", "sandbox-edit", "full-access"}
HARNESS_MUTATION_PREFIXES = (
    ".harness/",
    "scripts/verification/",
    ".github/workflows/harness.yml",
)
HARNESS_MUTATION_EXACT_PATHS = {
    "docs/harness.md",
    "docs/ai-engineering-workflow.md",
}


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
    path = project_root / ".harness" / "evolution" / "replay-sets" / f"{replay_set_id}.json"
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
        payload, read_errors = _project_relative_read_json(project_root, path)
        if read_errors:
            errors.extend(read_errors)
            continue
        candidate_errors = _candidate_errors(relative, payload, allowed_mutation_types)
        if candidate_errors:
            errors.extend(candidate_errors)
            continue
        candidates.append(payload)
    return candidates, errors


def _recent_run_manifests(project_root: Path, max_runs: int) -> list[dict[str, object]]:
    runs_dir = project_root / ".harness" / "verification" / "runs"
    if not runs_dir.exists():
        return []
    manifests: list[dict[str, object]] = []
    for path in sorted(runs_dir.glob("*/run-manifest.json"), reverse=True)[:max_runs]:
        payload, _errors = _project_relative_read_json(project_root, path)
        if payload:
            manifests.append(payload)
    return list(reversed(manifests))


def _load_digest(project_root: Path, digest_ref: str) -> dict[str, object] | None:
    path = project_root / digest_ref
    payload, errors = _project_relative_read_json(project_root, path)
    return None if errors else payload


def _suggested_mutation_type(profile: str) -> str:
    if profile == "docs":
        return "docs_gate"
    if profile in {"phase0", "phase1-slice", "character-agent-execution"}:
        return "failure_digest"
    return "validator"


def analyze_harness_evolution(project_root: Path, config: dict[str, object]) -> dict[str, object]:
    max_runs = int(config.get("max_runs_to_analyze", 20))
    profiles_in_scope = set(str(profile) for profile in config.get("profiles_in_scope", []))
    manifests = _recent_run_manifests(project_root, max_runs)
    if not manifests:
        return {
            "schema_version": 1,
            "overall_harness_evolution_analyzed": True,
            "history_status": "insufficient_history",
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

    for manifest in manifests:
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
            digest = _load_digest(project_root, digest_ref)
            if digest is None:
                telemetry_gaps.append({"id": "missing_digest_ref", "run_id": run_id, "path": digest_ref})
                continue
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
    }


def write_candidate_manifest(project_root: Path, candidate: dict[str, object]) -> Path:
    candidate_id = str(candidate["id"])
    path = project_root / ".harness" / "evolution" / "candidates" / f"{candidate_id}.json"
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
    report_path = project_root / ".harness" / "verification" / "harness-evolution-report.json"
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
            "evolution_report_exists",
            "Harness evolution report exists after analyzer execution",
            bool(report) and report.get("schema_version") == 1 and report.get("overall_harness_evolution_analyzed") is True,
            [".harness/verification/harness-evolution-report.json"],
            "\n".join(report_errors),
        ),
    ]
    return {
        "results": results,
        "candidate_count": len(candidates),
        "overall_harness_evolution_passed": all(str(entry["status"]) == "proved" for entry in results),
    }
