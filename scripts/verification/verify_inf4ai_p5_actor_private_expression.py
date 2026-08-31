from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "exact_source_and_append": (
            "backend/tests/test_inf4ai_p5_actor_private_expression.py",
            "test_completed_handshake_writes_two_actor_private_history_events_with_append_receipt",
        ),
        "zero_write_privacy_duplicate": (
            "backend/tests/test_inf4ai_p5_actor_private_expression.py",
            "test_handshake_shared_experience_rejects_incomplete_source_and_preserves_zero_write",
        ),
        "full_tail_replay": (
            "backend/tests/test_inf4ai_p5_actor_private_expression.py",
            "test_handshake_shared_experience_is_private_and_checkpoint_tail_replay_is_equal",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf4ai-p5-actor-private-expression-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", f"{root / relative}::{selector}"],
            root,
            log_path,
            env={"PYTHONPATH": "backend;backend/tests"},
        )
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf4ai-p5-actor-private-expression",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": ["backend/tests/test_inf4ai_p5_actor_private_expression.py"],
        "evidence": evidence,
        "run_id": f"inf4ai-p5-actor-private-expression-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "completed two-party handshake session -> Social actor-private shared experience",
        "owner": "authority:p5:social",
        "source_stream": "session:{session_id}",
        "target_stream": "gameplay:social:shared-experience:character:{participant_ref}",
        "event_type": "gameplay.social.handshake_shared_experience_recorded",
        "privacy": "actor_private",
        "boundaries": [
            "exact committed handshake session vector",
            "two distinct character participants and completed observations",
            "immutable P5 v2 vocabulary and read-only descriptor/catalog pins",
            "append-derived Social receipt",
            "actor-private projection and full/checkpoint-tail replay",
            "no relationship score, reputation, attendance, payment, material, compensation, or generic session adapter",
        ],
    }
    path = verification_dir(root) / "inf4ai-p5-actor-private-expression-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4AI P5 Actor-Private Expression Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"inf4ai_p5_actor_private_expression_report_json={path}")
    print(f"overall_inf4ai_p5_actor_private_expression_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
