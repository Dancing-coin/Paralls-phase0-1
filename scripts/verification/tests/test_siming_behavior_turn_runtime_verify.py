from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harness
from registry import load_profile_registry

ROOT = Path(__file__).resolve().parents[3]


def test_siming_behavior_turn_profile_is_registered() -> None:
    registry = load_profile_registry(ROOT)
    assert "siming-behavior-turn-runtime" in registry.profiles
    assert harness._profiles_for_selection("siming-behavior-turn-runtime", registry) == [
        "siming-behavior-turn-runtime"
    ]


def test_siming_behavior_turn_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_siming_behavior_turn_runtime.py"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stdout
    report = json.loads(
        (ROOT / ".harness/verification/siming-behavior-turn-runtime-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["overall_siming_behavior_turn_runtime_passed"] is True
