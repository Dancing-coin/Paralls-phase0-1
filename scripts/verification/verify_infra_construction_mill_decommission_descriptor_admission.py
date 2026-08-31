from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_file = root / "backend" / "tests" / "test_infra_construction_mill_decommission_descriptor_admission.py"
    cases = {
        "exact_descriptor_contract_and_pins": "test_frozen_v3_binds_exactly_one_approved_descriptor_and_retains_all_activation_pins",
        "lifecycle_catalog_boundary": "test_exact_catalog_row_is_lifecycle_only_and_uses_existing_construction_spine",
        "exact_one_zero_write": "test_unadmitted_multiple_or_mismatched_descriptor_fails_before_active_mutation",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for selector, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-construction-mill-decommission-descriptor-admission-{selector}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_file}::{test_name}"], root, log_path)
        checks[selector] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))

    report = {
        "profile": "infra-construction-mill-decommission-descriptor-admission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_file": str(test_file.relative_to(root)).replace("\\", "/"),
        "evidence": evidence,
        "run_id": f"infra-construction-mill-decommission-descriptor-admission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "frozen_package": {
            "package_revision": "package:industrial-facilities:v3",
            "content_digest": "sha256:bde53b49ee207d90c2d2bfd7e7ff95ef03638a41719883a21c2b83a3e15930ca",
            "declaration_digest": "sha256:ad800530f5e9a85baad29c5825a0e7edfc7e6cfa664a20208f5d2566819a7c3c",
        },
        "admitted_descriptor": {
            "descriptor_ref": "descriptor:construction-facility-mill-decommission@1",
            "descriptor_revision": "descriptor:construction-facility-mill-decommission@1",
            "capability_ref": "capability:construction-facility-mill-decommission@1",
            "outcome_family_ref": "outcome:construction-facility-mill-decommission@1",
            "contract_ref": "inf:construction-facility-mill-decommission@1",
        },
        "limitations": [
            "The profile verifies only immutable descriptor/catalog admission and existing read-only activation binding pins.",
            "No lifecycle projector, verifier, reducer, append, business event, or facility decommission is exercised.",
            "No generic transform/decommission, owner, router, registry, coordinator, writer, settlement authority, or second runtime is introduced.",
        ],
    }
    path = verification_dir(root) / "infra-construction-mill-decommission-descriptor-admission-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AH Mill Decommission Descriptor/Binding Admission Report",
        {
            "results": [
                {"id": name, "status": "proved" if passed else "missing", "title": name}
                for name, passed in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_construction_mill_decommission_descriptor_admission_report_json={path}")
    print(f"overall_infra_construction_mill_decommission_descriptor_admission_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
