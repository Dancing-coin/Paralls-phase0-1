from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_gameplay_foundation_all as verifier


def test_gameplay_foundation_all_declares_the_required_dependency_order() -> None:
    assert verifier.GAMEPLAY_FOUNDATION_PROFILES == [
        "gameplay-foundation-contract",
        "gameplay-event-replay",
        "gameplay-foundation-event-spine",
        "gameplay-state-groups",
        "gameplay-resource-body",
        "gameplay-status-tags",
        "gameplay-effective-stats",
        "gameplay-ability-affordance",
        "gameplay-inventory",
        "gameplay-possession-equipment",
        "gameplay-ownership-authority",
        "gameplay-economy-authority",
        "gameplay-patch-runtime",
        "godot-gameplay-mirror",
        "adventure-basic",
    ]


def test_gameplay_foundation_all_requires_a_green_child_report() -> None:
    assert verifier._child_report_passed(
        "gameplay-foundation-contract",
        {"overall_gameplay_foundation_contract_passed": True},
    )
    assert not verifier._child_report_passed(
        "adventure-basic",
        {"overall_adventure_basic_passed": True},
    )
    assert verifier._child_report_passed(
        "adventure-basic",
        {
            "overall_adventure_basic_passed": True,
            "adventure_basic_required_scenarios_complete": True,
        },
    )
    assert not verifier._child_report_passed("adventure-basic", {})


def test_gameplay_foundation_all_runs_its_child_gates_when_godot_is_unavailable() -> None:
    profile_path = Path(__file__).resolve().parents[3] / ".harness" / "profiles" / "gameplay-foundation-all.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    assert profile["requires_godot"] is False
