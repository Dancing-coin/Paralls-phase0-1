"""Run one frozen selection in bounded serial batches and compare outcomes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    expected = {x["test_name"]: x for x in selection["tests"]}
    if len(expected) != len(selection["tests"]) or not expected:
        raise SystemExit("selection must contain unique nodes")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runner = repo / "docs/verification/g0-939c6746/run_baseline.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "backend")
    nodes = list(expected)
    problems = []
    improvements = []
    for offset in range(0, len(nodes), 40):
        batch = nodes[offset:offset + 40]
        run_dir = output / f"batch-{offset // 40:04d}"
        command = [sys.executable, str(runner), "--repo", str(repo), "--output", str(run_dir)]
        for node in batch:
            command.extend(["--test", node])
        with (output / f"batch-{offset // 40:04d}.log").open("w", encoding="utf-8") as log:
            proc = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, text=True)
        result_path = run_dir / "results.json"
        if not result_path.exists():
            problems.append(f"batch {offset // 40}: no results (exit {proc.returncode})")
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        actual = {x["test_name"]: x for x in result["tests"]}
        failures = {}
        for failure in result["failures"]:
            failures.setdefault(failure["test_name"], []).append([failure["phase"], failure["error_type"]])
        if result["collection_errors"] or set(actual) != set(batch):
            problems.append(f"batch {offset // 40}: collection mismatch or error")
        for node in batch:
            old = expected[node]
            current = actual.get(node, {}).get("outcome", "missing")
            if old["outcome"] == "failed" and current == "passed":
                improvements.append(node)
            elif current != old["outcome"]:
                problems.append(f"{node}: {old['outcome']} -> {current}")
            elif current in {"failed", "error"} and sorted(failures.get(node, [])) != sorted(old["failures"]):
                problems.append(f"{node}: failure phase/type changed")
    print(f"selected={len(nodes)} problems={len(problems)} improvements={len(improvements)}")
    for problem in problems:
        print("PROBLEM", problem)
    for node in improvements:
        print("IMPROVED", node)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
