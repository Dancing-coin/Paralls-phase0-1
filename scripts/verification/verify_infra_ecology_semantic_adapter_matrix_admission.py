from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    matrix_path = root / "backend" / "tests" / "test_infra_state_lifecycle_adapter_matrix.py"
    ecology_path = root / "backend" / "tests" / "test_infra_semantic_ecology_frost_adapter.py"
    cases = {
        "matrix_row_apply_only": (matrix_path, "test_closed_adapter_matrix_admits_ecology_frost_apply_only"),
        "matrix_gate_zero_write": (ecology_path, "test_semantic_ecology_frost_requires_closed_adapter_matrix_row_without_write"),
        "closed_input": (ecology_path, "test_semantic_ecology_frost_command_forbids_free_owner_stream_and_payload_fields"),
        "owner_append": (ecology_path, "test_semantic_ecology_frost_maps_only_to_existing_ecology_owner_append"),
        "stale_revision_zero_write": (ecology_path, "test_semantic_ecology_frost_rejects_stale_revision_without_write"),
        "snapshot_zero_write": (ecology_path, "test_semantic_ecology_frost_rejects_snapshot_mismatch_without_write"),
        "exact_duplicate": (ecology_path, "test_semantic_ecology_frost_replays_exact_duplicate_without_second_write"),
        "changed_duplicate_zero_write": (ecology_path, "test_semantic_ecology_frost_rejects_changed_duplicate_without_write"),
        "source_privacy_zero_write": (ecology_path, "test_semantic_ecology_frost_rejects_authority_only_hazard_without_write"),
        "source_relation_zero_write": (ecology_path, "test_semantic_ecology_frost_rejects_forged_region_relation_without_write"),
        "checkpoint_tail_replay": (ecology_path, "test_semantic_ecology_frost_reuses_ecology_checkpoint_tail_replay"),
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for key, (path, selector) in cases.items():
        log = verification_dir(root) / f"infra-ecology-semantic-adapter-matrix-admission-{key}.log"
        result = run_command([python, "-m", "pytest", "-q", str(path), "-k", selector], root, log)
        checks[key] = result.returncode == 0
        logs.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-semantic-adapter-matrix-admission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "evidence": logs,
        "run_id": f"infra-ecology-semantic-adapter-matrix-admission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "write_path": "closed matrix -> strict semantic frost proposal -> Ecology-owned envelope -> EcologyHazardAuthority.apply_crop_state -> one append -> outbox/replay",
        "limitations": [
            "Only effect:frost -> state:frosted@1 is added to the immutable matrix.",
            "The generic state command cannot route Ecology because it lacks committed hazard/crop/region evidence.",
            "No generic registration API, semantic writer, scheduler, or new Ecology event family is admitted.",
        ],
    }
    target = verification_dir(root) / "infra-ecology-semantic-adapter-matrix-admission-report.json"
    write_json(target, report)
    write_markdown(
        target.with_suffix(".md"),
        "INF-1Y Ecology Semantic Adapter Matrix Admission Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(target)
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
