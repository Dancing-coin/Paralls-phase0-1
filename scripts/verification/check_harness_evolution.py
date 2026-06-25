from __future__ import annotations

from common import repo_root, verification_dir, write_json, write_markdown
from evolution import (
    analyze_harness_evolution,
    evaluate_harness_evolution as evaluate_evolution_surface,
    load_evolution_config,
    load_replay_set,
)


def evaluate_harness_evolution(project_root) -> dict[str, object]:
    config, config_errors = load_evolution_config(project_root)
    _replay_set, replay_errors = load_replay_set(project_root, "default")
    if config_errors or replay_errors:
        return evaluate_evolution_surface(project_root)

    analysis = analyze_harness_evolution(project_root, config)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "harness-evolution-report.json"
    md_path = log_dir / "harness-evolution-report.md"
    write_json(json_path, analysis)
    write_markdown(md_path, "Harness Evolution Analysis Report", analysis, "overall_harness_evolution_analyzed")

    report = evaluate_evolution_surface(project_root)
    return {
        **analysis,
        "results": report["results"],
        "candidate_count": report["candidate_count"],
        "overall_harness_evolution_passed": report["overall_harness_evolution_passed"],
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_harness_evolution(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "harness-evolution-report.json"
    md_path = log_dir / "harness-evolution-report.md"
    combined = dict(report)
    write_json(json_path, combined)
    write_markdown(md_path, "Harness Evolution Verification Report", combined, "overall_harness_evolution_passed")

    print(f"harness_evolution_report_json={json_path}")
    print(f"harness_evolution_report_md={md_path}")
    print(f"overall_harness_evolution_passed={combined['overall_harness_evolution_passed']}")
    for entry in combined["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if combined["overall_harness_evolution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
