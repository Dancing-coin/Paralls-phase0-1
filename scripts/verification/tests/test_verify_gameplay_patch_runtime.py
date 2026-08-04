from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_gameplay_patch_runtime as verifier


def test_patch_runtime_verifier_reports_each_migration_closure_gate_separately() -> None:
    assert verifier.TEST_GROUPS == [
        (
            "patch-contract-and-lifecycle",
            "Trusted manifest, lifecycle authority, and explicit state-group control tests pass",
            (
                "backend/tests/test_gameplay_patch_runtime.py",
                "backend/tests/test_gameplay_patch_lifecycle_authority.py",
                "backend/tests/test_state_group_lifecycle_authority.py",
            ),
        ),
        (
            "migration-replay-and-zero-write-rejection",
            "Typed migration replay, checkpoint equivalence, and pre-write rejection tests pass",
            (
                "backend/tests/test_resource_body_runtime.py",
                "backend/tests/test_gameplay_event_replay.py",
                "backend/tests/test_phase3_state_composer.py",
            ),
        ),
        (
            "post-commit-godot-projection",
            "Patch migration refreshes only the filtered Godot projection after commit",
            (
                "backend/tests/test_gameplay_event_spine.py",
                "backend/tests/test_phase3_mirror_source.py",
                "backend/tests/test_godot_gameplay_mirror_delivery.py",
                "backend/tests/test_godot_gameplay_mirror_projection.py",
            ),
        ),
        (
            "patch-rule-ir-and-capability-boundary",
            "Rule IR remains deterministic and capability-gated without a generic domain writer",
            (
                "backend/tests/test_gameplay_runtime_state.py",
                "backend/tests/test_gameplay_patch_rule_settlement.py",
            ),
        ),
    ]
