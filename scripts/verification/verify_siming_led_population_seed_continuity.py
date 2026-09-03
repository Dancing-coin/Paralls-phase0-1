from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.population_continuity.vertical import SimingLedPopulationFixture
from verify_phase3_common import root, write_report


def run_focused() -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root() / "backend")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "backend/tests/test_siming_led_population_seed_continuity.py",
        ],
        cwd=root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, result.stdout + result.stderr


def _predecessor_report(name: str) -> bool:
    path = root() / ".harness" / "verification" / f"{name}-report.json"
    if not path.exists():
        return False
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return payload.get("overall_passed") is True


def main() -> int:
    focused, focused_log = run_focused()
    evidence = SimingLedPopulationFixture.create().run()
    predecessors = {
        "phase3-population-continuity": _predecessor_report(
            "phase3-population-continuity"
        ),
        "phase3d-bakery-district-population": _predecessor_report(
            "phase3d-bakery-district-population"
        ),
    }
    replay = evidence["replay"]
    rejections = evidence["rejections"]
    architecture = evidence["architecture"]
    single_bus = (
        architecture["authority_bus_identity"]
        == architecture["pipeline_bus_identity"]
        and architecture["authority_bus_publish_count"] > 0
    )
    single_tick_path = (
        architecture["population_tick_count"]
        == architecture["authority_bus_publish_count"]
        and len(set(architecture["population_tick_cadence_ids"])) == 1
    )
    report = {
        "overall_passed": bool(
            focused
            and all(predecessors.values())
            and evidence["cadence"]["status"] == "accepted"
            and evidence["population"]["seed_count"] == 1
            and evidence["owner"]["owner_ref"]
            == "actor_gameplay.organization_domain"
            and evidence["character"]["continuity_status"] == "committed"
            and evidence["activation"]["status"] == "active"
            and evidence["activation"]["same_character_identity"] is True
            and evidence["activation"]["actual_player_input_path"] is True
            and bool(evidence["activation"]["local_structured_intent"])
            and replay["full_equals_checkpoint_tail"] is True
            and replay["independent_character_rebuilds"] is True
            and rejections["stale_read_set_zero_write"] is True
            and rejections["private_memory_without_exposure_zero_write"] is True
            and rejections["duplicate_seed_zero_write"] is True
            and rejections["unknown_behavior_zero_write"] is True
            and rejections["duplicate_status"] == "accepted"
            and rejections["duplicate_owner_idempotency_status"]
            == "duplicate_replayed"
            and rejections["duplicate_continuity_status"] == "idempotent_replay"
            and rejections["duplicate_continuity_projection_unchanged"] is True
            and single_bus
            and single_tick_path
        ),
        "predecessors": predecessors,
        "harness_checks": {
            "focused_pytest": focused,
            "single_authority_event_bus": single_bus,
            "single_siming_tick_path": single_tick_path,
            "owner_mediated_settlement": evidence["owner"]["event_family"]
            == "gameplay.organization.commerce_commitment_accepted",
            "same_character_activation": evidence["activation"][
                "same_character_identity"
            ],
        },
        "seed_projection": evidence["character"],
        "activation": evidence["activation"],
        "replay_hash": replay["full_hash"],
        "zero_write": all(
            rejections[key]
            for key in (
                "stale_read_set_zero_write",
                "private_memory_without_exposure_zero_write",
                "duplicate_seed_zero_write",
                "unknown_behavior_zero_write",
            )
        ),
        "rejections": rejections,
        "cadence": evidence["cadence"],
        "population": evidence["population"],
        "owner": evidence["owner"],
        "character": evidence["character"],
        "architecture": architecture,
        "focused_log": focused_log,
    }
    return write_report("siming-led-population-seed-continuity", report)


if __name__ == "__main__":
    raise SystemExit(main())
