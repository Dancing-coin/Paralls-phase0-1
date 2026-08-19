from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_inf_p_federated_gameplay_extension_platform.py"
    cases = {
        "legacy_v1_digest_compatibility": "test_v1_digest_bytes_remain_legacy_compatible_and_v1_cannot_carry_extension",
        "v2_candidate_active_snapshot_replay": "test_v2_normalizes_declaration_digest_before_outer_digest_and_candidate_snapshot_replay",
        "declaration_digest_zero_write": "malformed_digest_order_or_authority_payload_is_rejected_before_registry_write",
        "author_order_and_authority_payload_zero_write": "malformed_digest_order_or_authority_payload_is_rejected_before_registry_write",
        "schema_pair_and_outer_order_zero_write": "test_v2_unknown_schema_pair_and_noncanonical_outer_arrays_are_rejected",
        "readonly_binding_without_descriptor_zero_write": "test_complete_nonempty_binding_package_is_candidate_valid_but_unadmitted_binding_is_activation_zero_write",
        "complete_binding_candidate_admission": "test_complete_nonempty_binding_package_is_candidate_valid_but_unadmitted_binding_is_activation_zero_write",
        "binding_structure_zero_write": "test_binding_structure_conflicts_are_rejected_before_candidate_write",
        "activation_unique_descriptor_and_pins": "test_activation_resolves_exactly_one_readonly_descriptor_and_persists_binding_pins",
        "activation_unknown_multiple_mismatch_zero_write": "test_unknown_multiple_or_mismatched_descriptor_rejects_activation_without_mutation",
        "checkpoint_tail_binding_replay": "test_checkpoint_tail_candidate_replay_retains_binding_pins",
        "lifecycle_binding_pins_replay": "test_lifecycle_replay_requires_persisted_activation_binding_pins",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for selector, test_name in cases.items():
        log_path = verification_dir(root) / f"inf-p-federated-gameplay-extension-platform-{selector}.log"
        result = run_command([python, "-m", "pytest", "-q", str(tests), "-k", test_name], root, log_path)
        checks[selector] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf-p-federated-gameplay-extension-platform",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"inf-p-federated-gameplay-extension-platform-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "existing_spine": "GameplayPatchManifest -> GameplayPatchRegistry candidate/active set -> existing snapshot/load and lifecycle replay boundary",
        "read_only_binding_boundary": "A complete non-empty binding installs as an immutable candidate, then activation resolves exactly one separately admitted, immutable descriptor. This profile adds no descriptor, catalog row, owner, or write path.",
        "limitations": [
            "No package content is frozen and no canonical digest for a real package is calculated.",
            "No INF-1/2/3/4 business vertical, catalog row, settlement fragment, or domain event is admitted.",
            "Future successful bindings require separately approved row-specific owner descriptors and remain outside INF-P.",
        ],
    }
    path = verification_dir(root) / "inf-p-federated-gameplay-extension-platform-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-P Federated Gameplay Extension Platform Report",
        {
            "results": [
                {"id": name, "status": "proved" if passed else "missing", "title": name}
                for name, passed in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"inf_p_federated_gameplay_extension_platform_report_json={path}")
    print(f"overall_inf_p_federated_gameplay_extension_platform_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
