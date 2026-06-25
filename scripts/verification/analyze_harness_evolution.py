from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import repo_root, verification_dir
from evolution import (
    analyze_harness_evolution,
    build_candidate_from_analysis,
    load_evolution_config,
    load_replay_set,
    write_candidate_manifest,
)


def _write_report(project_root: Path, report: dict[str, object]) -> dict[str, Path]:
    log_dir = verification_dir(project_root)
    json_path = log_dir / "harness-evolution-report.json"
    md_path = log_dir / "harness-evolution-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Harness Evolution Report",
        "",
        f"- History Status: `{report.get('history_status')}`",
        f"- Patterns: `{len(report.get('failure_patterns', []))}`",
        f"- Telemetry Gaps: `{len(report.get('telemetry_gaps', []))}`",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["analyze", "propose"], default="analyze")
    parser.add_argument("--candidate-id", default=None)
    parser.add_argument("--replay-set", default="default")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else repo_root()
    config, config_errors = load_evolution_config(project_root)
    _replay_set, replay_errors = load_replay_set(project_root, args.replay_set)
    if config_errors or replay_errors:
        for error in [*config_errors, *replay_errors]:
            print(f"harness_evolution_error={error}")
        return 1

    report = analyze_harness_evolution(project_root, config)
    report_paths = _write_report(project_root, report)
    print(f"harness_evolution_report_json={report_paths['json']}")
    print(f"harness_evolution_report_md={report_paths['markdown']}")

    if args.mode == "propose":
        if not args.candidate_id:
            print("harness_evolution_error=--candidate-id is required in propose mode")
            return 1
        try:
            candidate = build_candidate_from_analysis(
                candidate_id=args.candidate_id,
                analysis=report,
                config=config,
                replay_set_id=args.replay_set,
            )
            candidate_path = write_candidate_manifest(project_root, candidate)
        except (FileExistsError, ValueError) as exc:
            print(f"harness_evolution_error={exc}")
            return 1
        print(f"harness_evolution_candidate={candidate_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
