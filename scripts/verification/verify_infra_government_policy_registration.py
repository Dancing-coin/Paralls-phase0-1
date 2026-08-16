from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_government_policy_registration.py"
    selectors = {
        "register_one_append_batch": "test_government_registers_a_fixed_policy_on_its_existing_stream_through_one_append_batch",
        "exact_duplicate_idempotency": "test_government_policy_registration_replays_an_exact_duplicate_without_writing",
        "changed_duplicate_zero_write": "test_government_policy_registration_rejects_changed_duplicate_without_writing",
        "stale_revision_zero_write": "test_government_policy_registration_rejects_stale_revision_without_writing",
        "privacy_zero_write": "test_government_policy_registration_rejects_nonproject_scope_without_writing",
        "unknown_policy_kind_zero_write": "test_government_policy_registration_rejects_unknown_policy_kind_before_authority_write",
        "revoke_one_append_batch": "test_government_revokes_the_fixed_policy_on_its_existing_stream_through_one_append_batch",
        "full_checkpoint_tail_replay": "test_government_policy_registration_replays_full_and_checkpoint_tail_view",
    }
    checks, evidence = {}, []
    for check, selector in selectors.items():
        path = verification_dir(root) / f"infra-government-policy-registration-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, path)
        checks[check] = result.returncode == 0
        evidence.append(str(path.relative_to(root)).replace("\\", "/"))
    report = {"profile": "infra-government-policy-registration", "overall_passed": all(checks.values()), "checks": checks, "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")], "evidence": evidence, "run_id": f"infra-government-policy-registration-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "commit": evidence_revision(root), "limitations": ["One fixed Government policy type only.", "It opens or settles no obligation and admits no generic payment or cross-domain writer."]}
    path = verification_dir(root) / "infra-government-policy-registration-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2K Government Policy Registration Report", {"results": [{"id": name, "status": "proved" if value else "missing", "title": name} for name, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
