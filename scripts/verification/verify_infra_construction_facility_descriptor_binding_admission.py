from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    catalog_tests = root / "backend" / "tests" / "test_infra_governed_authority_contract_catalog.py"
    platform_tests = root / "backend" / "tests" / "test_inf_p_federated_gameplay_extension_platform.py"
    cases = {
        "exact_catalog_descriptor_and_contract": (
            catalog_tests,
            "test_catalog_pins_only_the_approved_inf_1ag_descriptor_and_construction_contract",
        ),
        "frozen_package_exact_binding_without_construction_write": (
            catalog_tests,
            "test_frozen_inf_1ag_package_binds_to_the_one_admitted_descriptor_without_construction_write",
        ),
        "candidate_unknown_descriptor_zero_write": (
            platform_tests,
            "test_complete_nonempty_binding_package_is_candidate_valid_but_unadmitted_binding_is_activation_zero_write",
        ),
        "activation_exact_one_pins_and_snapshot_replay": (
            platform_tests,
            "test_activation_resolves_exactly_one_readonly_descriptor_and_persists_binding_pins",
        ),
        "multiple_mismatch_zero_write": (
            platform_tests,
            "test_unknown_multiple_or_mismatched_descriptor_rejects_activation_without_mutation",
        ),
        "checkpoint_tail_binding_replay": (
            platform_tests,
            "test_checkpoint_tail_candidate_replay_retains_binding_pins",
        ),
        "lifecycle_binding_pin_replay": (
            platform_tests,
            "test_lifecycle_replay_requires_persisted_activation_binding_pins",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for selector, (test_file, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-construction-facility-descriptor-binding-admission-{selector}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_file}::{test_name}"], root, log_path)
        checks[selector] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))

    report = {
        "profile": "infra-construction-facility-descriptor-binding-admission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(catalog_tests.relative_to(root)).replace("\\", "/"),
            str(platform_tests.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": evidence,
        "run_id": f"infra-construction-facility-descriptor-binding-admission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "admitted_descriptor": {
            "descriptor_ref": "descriptor:construction-facility-package-declared-transform@1",
            "descriptor_revision": "descriptor:construction-facility-package-declared-transform@1",
            "capability_ref": "capability:construction-facility-package-declared-transform@1",
            "outcome_family_ref": "outcome:construction-facility-package-declared-transform@1",
            "contract_ref": "inf:construction-facility-package-declared-transform@1",
            "owner_ref": "actor_gameplay.construction_production_domain",
        },
        "frozen_package": {
            "package_revision": "package:industrial-facilities:v1",
            "content_digest": "sha256:41e1b40bcd1fd13e1692f2f51aed7dea6dceee0b1605bf215fe6c673fcd11f88",
            "declaration_digest": "sha256:04869873a57a24b834cc123a14440444717bdd482910eb9d8ae1d50cc3bc2ed8",
        },
        "write_path": "GameplayPatchManifest -> existing GameplayPatchRegistry candidate/active binding snapshot",
        "construction_write": "not invoked by this profile",
        "limitations": [
            "The profile admits and replays only the exact immutable descriptor/binding metadata.",
            "No Construction verifier, reducer, append, business event, or facility transform is exercised.",
            "No generic owner, transform, router, registry, coordinator, writer, settlement authority, or second runtime is introduced.",
        ],
    }
    path = verification_dir(root) / "infra-construction-facility-descriptor-binding-admission-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AG Construction Descriptor/Binding Admission Report",
        {
            "results": [
                {"id": name, "status": "proved" if passed else "missing", "title": name}
                for name, passed in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_construction_facility_descriptor_binding_admission_report_json={path}")
    print(f"overall_infra_construction_facility_descriptor_binding_admission_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
