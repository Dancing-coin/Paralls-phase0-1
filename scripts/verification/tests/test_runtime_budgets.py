from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import verify_phase0
import verify_phase1_slice


def test_phase0_runtime_budget_covers_full_autotest_loop() -> None:
    assert verify_phase0.MAIN_AUTOTEST_QUIT_AFTER_FRAMES >= 1000
    assert verify_phase0.FOCUS_AUTOTEST_QUIT_AFTER_FRAMES >= 500


def test_phase1_slice_runtime_budget_covers_full_autotest_loop() -> None:
    assert verify_phase1_slice.MAIN_AUTOTEST_QUIT_AFTER_FRAMES >= 1000
    assert verify_phase1_slice.FOCUS_AUTOTEST_QUIT_AFTER_FRAMES >= 500


def test_phase0_audit_receives_root_motion_source_inputs() -> None:
    source = Path(verify_phase0.__file__).read_text(encoding="utf-8")

    assert 'player_bridge_source=read_text(project_root / "scripts" / "player" / "Phase0PlayerBridge.gd")' in source
    assert 'character_replica_source=read_text(project_root / "scripts" / "character" / "CharacterReplica.gd")' in source
