from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_adventure_basic as verifier


def test_adventure_basic_verifier_requires_five_scenario_live_godot_mirror_closure() -> None:
    assert "backend/tests/test_adventure_basic_scenario2.py" in verifier.TEST_FILES
    assert "backend/tests/test_adventure_basic_scenario3.py" in verifier.TEST_FILES
    assert "backend/tests/test_adventure_basic_scenario4.py" in verifier.TEST_FILES
    assert "backend/tests/test_adventure_basic_scenario5.py" in verifier.TEST_FILES
    assert "backend/tests/test_adventure_basic_closure_evidence.py" in verifier.TEST_FILES
    assert "backend/tests/test_adventure_basic_mirror_source.py" in verifier.TEST_FILES
    assert "backend/tests/test_adventure_basic_mirror_runtime.py" in verifier.TEST_FILES
    assert "Scenarios 1 through 5 backend compositions" in verifier.SCOPE
    assert "replay" in verifier.SCOPE
    assert "mirror projection" in verifier.SCOPE
    assert "real Godot mirror delivery" in verifier.SCOPE
    assert verifier.CLOSURE_EVIDENCE_FILENAME == "adventure-basic-closure-evidence.json"
    assert verifier.LIVE_MIRROR_REPORT_FILENAME == "live-adventure-basic-mirror-report.json"
    assert verifier.LIVE_MIRROR_VERIFIER == "scripts/verification/verify_live_adventure_basic_mirror.py"
