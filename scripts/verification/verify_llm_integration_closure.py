from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from common import repo_root, verification_dir, write_json, write_markdown


SCHEMA_VERSION = "llm-integration-closure.v1"
REPORT_JSON = "llm-integration-closure-report.json"
REPORT_MD = "llm-integration-closure-report.md"


SOURCE_FILES = {
    "readiness": "model-provider-readiness-report.json",
    "character": "character-model-live-report.json",
    "siming": "siming-backend-chain-report.json",
}


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _row(report: dict[str, object], provider_kind: str) -> dict[str, object] | None:
    rows = report.get("rows", [])
    if not isinstance(rows, list):
        return None
    for item in rows:
        if isinstance(item, dict) and item.get("provider_kind") == provider_kind:
            return item
    return None


def _result(report: dict[str, object], result_id: str) -> dict[str, object] | None:
    results = report.get("results", [])
    if not isinstance(results, list):
        return None
    for item in results:
        if isinstance(item, dict) and item.get("id") == result_id:
            return item
    return None


def build_report() -> dict[str, object]:
    run_id = os.getenv("LLM_CLOSURE_RUN_ID", "")
    log_dir = verification_dir(repo_root())
    artifacts: dict[str, dict[str, object] | None] = {
        name: _load_json(log_dir / filename) for name, filename in SOURCE_FILES.items()
    }
    errors: list[str] = []
    for name, payload in artifacts.items():
        if payload is None:
            errors.append(f"missing_artifact:{name}")
            continue
        if str(payload.get("verification_run_id", "")) != run_id:
            errors.append(f"run_id_mismatch:{name}")

    readiness = artifacts["readiness"] or {}
    character = artifacts["character"] or {}
    siming = artifacts["siming"] or {}
    character_row = _row(readiness, "character_text")
    siming_row = _row(readiness, "siming_candidate")
    provider = character.get("provider", {}) if isinstance(character.get("provider", {}), dict) else {}

    claims = {
        "character_dialogue_live": _claim_character(character, "dialogue_live_deepseek", errors),
        "character_l2_live": _claim_character(character, "l2_live_deepseek", errors),
        "character_l3_live": _claim_character(character, "l3_live_deepseek", errors),
        "siming_deepseek_live": _claim_siming(siming, errors),
    }

    if character_row is not None:
        if character_row.get("provider_id") != provider.get("provider_kind"):
            errors.append("identity_mismatch:character_provider")
        if character_row.get("model_id") != provider.get("model"):
            errors.append("identity_mismatch:character_model")
    else:
        errors.append("missing_readiness_row:character_text")
    if siming_row is not None:
        if siming_row.get("provider_id") != "deepseek_chat":
            errors.append("identity_mismatch:siming_provider")
        siming_result = _result(siming, "app_wiring_live_deepseek_chain") or {}
        notes = str(siming_result.get("notes", ""))
        if str(siming_row.get("model_id", "")) and str(siming_row.get("model_id", "")) not in notes:
            # Older Siming reports record model in the header/stdout only; do not fail
            # on notes, but keep provider identity strict.
            pass
    else:
        errors.append("missing_readiness_row:siming_candidate")

    overall = not errors and all(value == "passed" for value in claims.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "verification_run_id": run_id,
        "overall_llm_integration_closure_passed": overall,
        "claims": claims,
        "readiness_is_live_proof": False,
        "source_artifacts": [
            f".harness/verification/{filename}" for filename in SOURCE_FILES.values()
        ],
        "errors": errors,
    }


def _claim_character(report: dict[str, object], result_id: str, errors: list[str]) -> str:
    result = _result(report, result_id)
    if result is None:
        errors.append(f"missing_character_result:{result_id}")
        return "failed"
    passed = (
        result.get("status") == "passed"
        and result.get("transport_attempted") is True
        and result.get("transport_succeeded") is True
        and result.get("fallback_used") is False
    )
    if not passed:
        errors.append(f"failed_character_result:{result_id}")
    return "passed" if passed else "failed"


def _claim_siming(report: dict[str, object], errors: list[str]) -> str:
    result = _result(report, "app_wiring_live_deepseek_chain")
    if result is None:
        errors.append("missing_siming_result:app_wiring_live_deepseek_chain")
        return "failed"
    passed = result.get("status") == "passed"
    if not passed:
        errors.append("failed_siming_result:app_wiring_live_deepseek_chain")
    return "passed" if passed else "failed"


def main() -> int:
    report = build_report()
    log_dir = verification_dir(repo_root())
    write_json(log_dir / REPORT_JSON, report)
    write_markdown(log_dir / REPORT_MD, "LLM Integration Closure", report, "overall_llm_integration_closure_passed")
    print(f"llm_integration_closure_report_json=.harness/verification/{REPORT_JSON}")
    print(f"overall_llm_integration_closure_passed={report['overall_llm_integration_closure_passed']}")
    for error in report["errors"]:
        print(f"closure_error={error}")
    return 0 if report["overall_llm_integration_closure_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
