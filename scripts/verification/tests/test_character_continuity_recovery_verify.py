from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import harness
from registry import load_profile_registry


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_character_continuity_recovery_profile_is_registered() -> None:
    registry = load_profile_registry(PROJECT_ROOT)
    assert "character-continuity-recovery" in registry.profiles
    profile = registry.profiles["character-continuity-recovery"]
    assert profile["script"] == "scripts/verification/verify_character_continuity_recovery.py"
    assert profile["requires_godot"] is False
    assert harness._profiles_for_selection("character-continuity-recovery", registry) == [
        "character-continuity-recovery"
    ]


def test_character_continuity_recovery_verifier_proves_graph_restart() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_character_continuity_recovery.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stdout
    report = json.loads(
        (PROJECT_ROOT / ".harness/verification/character-continuity-recovery-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["overall_character_continuity_recovery_passed"] is True
    assert all(entry["status"] == "proved" for entry in report["results"])
