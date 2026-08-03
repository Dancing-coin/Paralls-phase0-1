from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from common import repo_root, verification_dir, write_json, write_markdown
from vla_advisory_benchmark_metrics import MINIMUM_STATISTICAL_SAMPLE_COUNT, build_sample_record, summarize_route


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an explicit, capture-bound VLA advisory replay benchmark.")
    parser.add_argument("--allow-live-call", action="store_true", help="required before any provider call")
    parser.add_argument("--samples", type=int, default=3, help="attempts per route (default: 3)")
    parser.add_argument("--route", action="append", choices=["advisory-fast", "advisory-deep"], dest="routes")
    parser.add_argument(
        "--annotation-sample-id",
        action="append",
        dest="annotation_sample_ids",
        help="replay a reviewed annotation sample with its own runtime capture and PQF scope; repeat for multiple scenes",
    )
    parser.add_argument("--command-timeout-seconds", type=float, default=45.0)
    args = parser.parse_args()
    if not args.allow_live_call:
        parser.error("--allow-live-call is required")
    if args.samples < 1:
        parser.error("--samples must be positive")

    root = repo_root()
    evidence_dir = verification_dir(root)
    # Online policy is fast-only. Deep remains an explicit offline comparison
    # route and must never be selected merely because a benchmark omitted it.
    routes = args.routes or ["advisory-fast"]
    annotation_sample_ids = args.annotation_sample_ids or [""]
    run_dir = evidence_dir / "vla-advisory-replay-benchmark"
    run_dir.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, object]] = []

    for annotation_sample_id in annotation_sample_ids:
        for route in routes:
            report_name = "vla-provider-live-report.json" if route == "advisory-fast" else "vla-provider-live-deep-report.json"
            for index in range(args.samples):
                command = [
                    sys.executable,
                    str(root / "scripts" / "verification" / "verify_vla_provider_live.py"),
                    "--allow-live-call",
                    "--route",
                    route,
                ]
                if annotation_sample_id:
                    command.extend(["--annotation-sample-id", annotation_sample_id])
                else:
                    command.append("--use-godot-runtime-capture")
                try:
                    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=args.command_timeout_seconds)
                    command_status = "completed" if completed.returncode == 0 else "nonzero_exit"
                except subprocess.TimeoutExpired:
                    command_status = "benchmark_command_timeout"
                report_path = evidence_dir / report_name
                if not report_path.is_file():
                    samples.append({"route": route, "status": command_status, "archived_report": ""})
                    continue
                sample_label = annotation_sample_id or "main-demo-default"
                archived = run_dir / f"{sample_label}-{route}-{index + 1}.json"
                shutil.copy2(report_path, archived)
                payload = _read_json(archived)
                record = build_sample_record(payload, archived_report=str(archived.relative_to(root)))
                record["command_status"] = command_status
                record["annotation_sample_id"] = annotation_sample_id
                samples.append(record)

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for sample in samples:
        grouped[str(sample.get("route", "unknown"))].append(sample)
    report = {
        "schema_version": "vla-advisory-replay-benchmark.v1",
        "capture_requirement": "fresh matching Godot runtime capture required for every replay attempt",
        "minimum_statistical_sample_count": MINIMUM_STATISTICAL_SAMPLE_COUNT,
        "routes": {route: summarize_route(records) for route, records in grouped.items()},
        "samples": samples,
        "limitations": [
            "No semantic accuracy score is emitted without a separately reviewed annotation manifest.",
            "End-to-end timing includes local image encoding, provider transport, result validation, and bridge work.",
            "All outputs remain advisory; benchmark findings cannot write world truth, ESM authority, or actor controls.",
        ],
    }
    json_path = evidence_dir / "vla-advisory-replay-benchmark-report.json"
    markdown_path = evidence_dir / "vla-advisory-replay-benchmark-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "VLA Advisory Replay Benchmark", report, "schema_version")
    print(f"vla_advisory_replay_benchmark_json={json_path}")
    print(f"vla_advisory_replay_benchmark_md={markdown_path}")
    for route, summary in report["routes"].items():
        print(f"route={route} success_rate={summary['success_rate']} statistical_readiness={summary['statistical_readiness']}")
    return 0


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
