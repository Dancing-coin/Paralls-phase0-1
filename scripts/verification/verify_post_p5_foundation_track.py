from __future__ import annotations

import sys
from pathlib import Path

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TRACKS = {
    "f1a": {
        "report": "post-p5-f1a-foundation-report.json",
        "title": "Post-P5 F1A Narrow Semantic and Causal Foundation",
        "scope": "partial-foundation; existing Patch Rule Runtime and event replay only",
        "tests": [
            "backend/tests/test_gameplay_patch_runtime.py",
            "backend/tests/test_gameplay_patch_rule_settlement.py",
            "backend/tests/test_gameplay_event_replay.py",
        ],
        "non_goals": ["generic Rule IR", "second scheduler/clock", "direct world write"],
    },
    "f1b": {
        "report": "post-p5-f1b-foundation-report.json",
        "title": "Post-P5 F1B Narrow Social and Privacy Foundation",
        "scope": "partial-foundation; existing P5 social authority and scoped projections only",
        "tests": [
            "backend/tests/test_p5_social_knowledge.py",
            "backend/tests/test_p5_contracts.py",
            "backend/tests/test_gameplay_p5_batch_contract.py",
        ],
        "non_goals": ["family simulator", "social truth store", "omniscient knowledge"],
    },
    "f1c": {
        "report": "post-p5-f1c-foundation-report.json",
        "title": "Post-P5 F1C Narrow Package Governance Foundation",
        "scope": "partial-foundation; existing patch manifest/lifecycle authority only",
        "tests": [
            "backend/tests/test_gameplay_patch_runtime.py",
            "backend/tests/test_gameplay_patch_lifecycle_authority.py",
            "backend/tests/test_gameplay_event_replay.py",
        ],
        "non_goals": ["full creator control plane", "public marketplace", "arbitrary executable plugin"],
    },
}


def main() -> int:
    stem = Path(sys.argv[0]).stem
    track = stem.split("_f1", 1)[1].split("_", 1)[0] if "_f1" in stem else ""
    track = f"f1{track}" if track else ""
    config = TRACKS.get(track)
    if config is None:
        raise SystemExit(f"unknown post-p5 foundation track: {track}")
    project_root = repo_root()
    python_exe = resolve_python_exe(None)
    log_path = verification_dir(project_root) / f"post-p5-{track}-foundation-pytest.log"
    result = run_command([python_exe, "-m", "pytest", "-q", *config["tests"]], project_root, log_path)
    passed = result.returncode == 0
    report = {
        "profile": f"post-p5-{track}-foundation",
        "scope": config["scope"],
        "overall_passed": passed,
        "focused_tests_passed": passed,
        "focused_test_files": config["tests"],
        "evidence": [str(log_path.relative_to(project_root)).replace("\\", "/")],
        "non_goals": config["non_goals"],
        "notes": "A green result proves only this bounded foundation slice; it does not promote the generic F1 track or authorize P6/P7.",
    }
    report_path = verification_dir(project_root) / config["report"]
    write_json(report_path, report)
    write_markdown(report_path.with_suffix(".md"), config["title"], {"results": [{"id": "focused_tests", "status": "proved" if passed else "missing", "title": config["scope"], "notes": report["notes"]}], "overall_passed": passed}, "overall_passed")
    print(f"post_p5_{track}_foundation_report_json={report_path}")
    print(f"overall_post_p5_{track}_foundation_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
