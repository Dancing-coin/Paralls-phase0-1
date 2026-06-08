from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


STAGE1_SEAM_COMMIT_SUBJECT = "Prepare stable architecture seams before enhanced subsystem merges"
ALLOWED_UNTRACKED: set[str] = set()


def _result(
    result_id: str,
    title: str,
    status: str,
    evidence: list[str],
    notes: str = "",
) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": status,
        "evidence": evidence,
        "notes": notes,
    }


def _clean_status_lines(raw: str) -> list[str]:
    return [line.rstrip() for line in raw.splitlines() if line.strip()]


def _normalize_status_path(line: str) -> str:
    match = re.match(r"^[ MARCUD?!]{2}\s+(.+)$", line)
    return match.group(1).replace("\\", "/") if match else line.replace("\\", "/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)

    git_status_log = log_dir / "merge-preflight-git-status.log"
    git_log_log = log_dir / "merge-preflight-git-log.log"
    seam_tests_log = log_dir / "merge-preflight-seam-tests.log"

    git_status_result = run_command(["git", "status", "--short"], project_root, git_status_log)
    git_log_result = run_command(["git", "log", "--oneline", "-5"], project_root, git_log_log)
    seam_tests_result = run_command(
        [
            python_exe,
            "-m",
            "pytest",
            "-v",
            "tests/test_architecture_entrypoints.py",
            "tests/test_ws_protocol.py::test_authority_bus_router_entrypoint_matches_legacy_behavior",
        ],
        project_root / "backend",
        seam_tests_log,
    )

    raw_status_lines = _clean_status_lines(git_status_result.stdout)
    normalized_paths = [_normalize_status_path(line) for line in raw_status_lines]
    unexpected_paths = [path for path in normalized_paths if path not in ALLOWED_UNTRACKED]

    worktree_status = "proved" if not unexpected_paths else ("weak" if set(unexpected_paths) == set() else "missing")
    worktree_notes = ""
    if unexpected_paths:
        worktree_status = "missing"
        worktree_notes = "Unexpected worktree entries: %s" % ", ".join(unexpected_paths)
    elif normalized_paths:
        worktree_status = "weak"
        worktree_notes = "Only allowed unrelated files remain: %s" % ", ".join(normalized_paths)

    git_log_text = git_log_result.stdout
    seam_commit_present = STAGE1_SEAM_COMMIT_SUBJECT in git_log_text

    seam_tests_ok = seam_tests_result.returncode == 0

    report = {
        "results": [
            _result(
                "worktree_clean_enough",
                "Worktree is clean enough for enhanced subsystem merge preflight",
                worktree_status,
                normalized_paths if normalized_paths else ["git status clean"],
                worktree_notes,
            ),
            _result(
                "stage1_seam_commit_present",
                "Stage 1 seam commit is visible in recent history",
                "proved" if seam_commit_present else "missing",
                [STAGE1_SEAM_COMMIT_SUBJECT] if seam_commit_present else [],
                "" if seam_commit_present else "Expected Stage 1 seam commit subject was not found in the last five commits.",
            ),
            _result(
                "seam_tests_green",
                "Stage 1 seam tests are green before enhanced merges",
                "proved" if seam_tests_ok else "missing",
                ["architecture entrypoints", "authority bus guardrail"] if seam_tests_ok else [],
                "" if seam_tests_ok else "Run backend seam tests from backend/ and inspect %s" % seam_tests_log,
            ),
        ],
        "overall_enhanced_merge_preflight_passed": (
            worktree_status in {"proved", "weak"}
            and seam_commit_present
            and seam_tests_ok
        ),
        "artifacts": {
            "git_status_log": str(git_status_log),
            "git_log_log": str(git_log_log),
            "seam_tests_log": str(seam_tests_log),
        },
    }

    json_path = log_dir / "enhanced-merge-preflight-report.json"
    md_path = log_dir / "enhanced-merge-preflight-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Enhanced Merge Preflight Report", report, "overall_enhanced_merge_preflight_passed")

    print(f"enhanced_merge_preflight_report_json={json_path}")
    print(f"enhanced_merge_preflight_report_md={md_path}")
    print(f"overall_enhanced_merge_preflight_passed={report['overall_enhanced_merge_preflight_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_enhanced_merge_preflight_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
