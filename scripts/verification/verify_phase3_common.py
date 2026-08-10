from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def write_report(name: str, report: dict[str, object]) -> int:
    directory = root() / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        f"# {name}",
        "",
        f"- overall: `{report.get('overall_passed')}`",
        f"- replay_hash: `{report.get('replay_hash', '')}`",
        f"- zero_write: `{report.get('zero_write')}`",
        f"- stop_reason: `{report.get('stop_reason')}`",
    ]
    (directory / f"{name}-report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"overall_{name.replace('-', '_')}_passed={report.get('overall_passed')}")
    return 0 if report.get("overall_passed") else 1


def run_focused() -> tuple[bool, str]:
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(root() / "backend")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "backend/tests/test_population_continuity.py",
        ],
        cwd=root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, result.stdout + result.stderr
