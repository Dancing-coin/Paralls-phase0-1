from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_gameplay_foundation_all as verifier
from harness import _profile_command
from registry import load_profile_registry


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


def test_gameplay_foundation_all_passes_godot_to_its_godot_child_gate() -> None:
    project_root = Path(__file__).resolve().parents[3]
    profile = load_profile_registry(project_root).profiles["gameplay-foundation-all"]

    command = _profile_command(
        "gameplay-foundation-all",
        project_root,
        "C:/Python/python.exe",
        "D:/Godot/Godot.exe",
        {"gameplay-foundation-all": profile},
    )

    assert command[2:4] == ["--godot-exe", "D:/Godot/Godot.exe"]
