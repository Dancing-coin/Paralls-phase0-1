from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "verification"))

import verify_character_behavior_evaluation as verifier
from run_context import run_scope


def test_character_behavior_evaluation_profile_accepts_canonical_turn_chain() -> None:
    with run_scope(PROJECT_ROOT):
        assert verifier.main() == 0
