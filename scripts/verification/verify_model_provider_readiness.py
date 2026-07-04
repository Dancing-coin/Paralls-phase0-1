from __future__ import annotations

import json
import sys
from pathlib import Path

from common import repo_root


PROJECT_ROOT = repo_root()
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.world_runtime.model_provider_readiness import (  # noqa: E402
    ModelProviderKind,
    ModelProviderReadinessReport,
    ModelProviderReadinessStatus,
    build_model_provider_readiness_report,
    write_model_provider_readiness_report,
)


REQUIRED_ROW_KEYS = {
    "provider_kind",
    "mode",
    "provider_id",
    "model_id",
    "endpoint_host_redacted",
    "readiness_status",
    "schema_version",
    "required_input_refs",
    "output_schema_status",
    "timeout_degrade_status",
    "context_isolation_status",
    "world_truth_write_status",
    "verification_evidence",
}

ALLOWED_STATUSES = {status.value for status in ModelProviderReadinessStatus}
REQUIRED_KINDS = {kind.value for kind in ModelProviderKind}
FORBIDDEN_STATUS_VALUES = {"mock_verified", "static_verified", "contract_static_real_verified"}
SECRET_MARKERS = {"sk-", "api_key", "secret-key", "route-secret", "Bearer "}


def _validate_report(report: ModelProviderReadinessReport) -> list[str]:
    errors: list[str] = []
    payload = report.to_dict()
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return ["rows must be a list"]

    row_kinds = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {index} must be an object")
            continue
        missing = sorted(REQUIRED_ROW_KEYS.difference(row))
        if missing:
            errors.append(f"row {index} missing keys: {', '.join(missing)}")
        provider_kind = str(row.get("provider_kind", ""))
        row_kinds.add(provider_kind)
        status = str(row.get("readiness_status", ""))
        if status not in ALLOWED_STATUSES:
            errors.append(f"{provider_kind} has unsupported readiness_status={status}")
        if status in FORBIDDEN_STATUS_VALUES:
            errors.append(f"{provider_kind} uses forbidden readiness_status={status}")
        if status == ModelProviderReadinessStatus.REAL_PROVIDER_VERIFIED.value:
            evidence = " ".join(str(item) for item in row.get("verification_evidence", []))
            if "real adapter call" not in evidence:
                errors.append(f"{provider_kind} real_provider_verified lacks real adapter call evidence")
        if "forbidden" not in str(row.get("world_truth_write_status", "")):
            errors.append(f"{provider_kind} must explicitly forbid direct world-truth writes")
        if not row.get("required_input_refs"):
            errors.append(f"{provider_kind} must include required input refs")
        if not row.get("verification_evidence"):
            errors.append(f"{provider_kind} must include verification evidence")

    missing_kinds = sorted(REQUIRED_KINDS.difference(row_kinds))
    if missing_kinds:
        errors.append(f"missing provider rows: {', '.join(missing_kinds)}")

    serialized = json.dumps(payload, ensure_ascii=False)
    for marker in SECRET_MARKERS:
        if marker in serialized:
            errors.append(f"readiness report leaks secret marker: {marker}")
    return errors


def main() -> int:
    report = build_model_provider_readiness_report()
    errors = _validate_report(report)
    json_path, markdown_path = write_model_provider_readiness_report(report, project_root=PROJECT_ROOT)
    print(f"model_provider_readiness_report_json={json_path}")
    print(f"model_provider_readiness_report_md={markdown_path}")
    print(f"model_provider_readiness_overall_passed={report.overall_passed}")
    if errors:
        for error in errors:
            print(f"model_provider_readiness_error={error}")
        return 1
    for row in report.rows:
        print(f"provider={row.provider_kind} status={row.readiness_status} mode={row.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
