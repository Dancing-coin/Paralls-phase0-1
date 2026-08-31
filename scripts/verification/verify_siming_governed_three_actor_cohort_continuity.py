from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.population_continuity.vertical import ThreeActorCohortContinuityFixture
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
            "backend/tests/test_siming_governed_three_actor_cohort_continuity.py",
        ],
        cwd=root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, result.stdout + result.stderr


def predecessor_report(name: str) -> bool:
    path = root() / ".harness" / "verification" / f"{name}-report.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("overall_passed") is True
    except (OSError, ValueError):
        return False


def main() -> int:
    focused, focused_log = run_focused()
    evidence = ThreeActorCohortContinuityFixture.create().run()
    predecessors = {
        "phase3-population-continuity": predecessor_report("phase3-population-continuity"),
        "siming-led-population-seed-continuity": predecessor_report("siming-led-population-seed-continuity"),
    }
    architecture = evidence["architecture"]
    rejections = evidence["rejections"]
    w0 = evidence["w0"]
    w1 = evidence["w1"]
    character = evidence["character"]
    w0_receipts = {item["actor_ref"]: item for item in w0["continuity_receipts"]}
    w1_receipts = {item["actor_ref"]: item for item in w1["continuity_receipts"]}
    w1_new_source = (
        w0["window"] == "W0"
        and w1["window"] == "W1"
        and w0["cadence_id"] != w1["cadence_id"]
        and w0["source_revision_vector"] != w1["source_revision_vector"]
    )
    actor_revision_progression = all(
        w0_receipts[actor]["character_revision_before"]
        < w1_receipts[actor]["character_revision_before"]
        and w0_receipts[actor]["character_revision_after"]
        <= w1_receipts[actor]["character_revision_after"]
        for actor in ("character:char_a", "character:char_b")
        if actor in w0_receipts and actor in w1_receipts
    ) and all(actor in w0_receipts and actor in w1_receipts for actor in ("character:char_a", "character:char_b"))
    no_char_c_command = all(
        actor != "character:char_c" for actor in character["continuity_commands"]
    )
    char_b_pending_empty = character["char_b_pending_memory_count"] == 0
    same_existing_record = (
        evidence["activation"]["existing_record_ref"] == "character:char_c"
        and evidence["activation"]["existing_record_ref_before"]
        == evidence["activation"]["existing_record_ref_after"]
        and evidence["activation"]["new_identity_created"] is False
    )
    zero_write_keys = tuple(
        key for key, value in rejections.items() if key.endswith("_zero_write")
    )
    zero_write_checks = all(rejections[key] is True for key in zero_write_keys)
    single_bus = architecture["authority_bus_identity"] == architecture["pipeline_bus_identity"]
    single_tick = (
        architecture["population_tick_count"] == architecture["authority_bus_publish_count"]
        and architecture["population_tick_count"] >= 2
    )
    report = {
        "overall_passed": bool(
            focused
            and all(predecessors.values())
            and evidence["w0"]["status"] == "accepted"
            and evidence["w1"]["status"] == "accepted"
            and evidence["w0"]["selected"] == ["character:char_a", "character:char_b", "character:char_c"]
            and evidence["w1"]["selected"] == evidence["w0"]["selected"]
            and evidence["owner"]["actor_ref"] == "character:char_a"
            and evidence["owner"]["event_family"] == "gameplay.organization.commerce_commitment_accepted"
            and evidence["character"]["seeded_actors"] == ["character:char_a", "character:char_b"]
            and evidence["character"]["activation_only_actors"] == ["character:char_c"]
            and char_b_pending_empty
            and no_char_c_command
            and w1_new_source
            and actor_revision_progression
            and evidence["activation"]["same_character_identity"] is True
            and same_existing_record
            and evidence["replay"]["full_equals_checkpoint_tail"] is True
            and single_bus
            and single_tick
            and rejections["changed_duplicate_idempotency_status"]
            == "idempotency_key_reused"
            and rejections["duplicate_owner_idempotency_status"]
            == "duplicate_replayed"
            and rejections["duplicate_continuity_status"] == "idempotent_replay"
            and rejections["changed_duplicate_status"] == "owner_settlement_required"
            and zero_write_checks
        ),
        "predecessors": predecessors,
        "harness_checks": {
            "focused_pytest": focused,
            "single_authority_event_bus": single_bus,
            "single_siming_tick_path": single_tick,
            "owner_event_family": evidence["owner"]["event_family"],
            "seeded_actors": evidence["character"]["seeded_actors"],
            "activation_only_actor": evidence["character"]["activation_only_actors"],
            "replay_equal": evidence["replay"]["full_equals_checkpoint_tail"],
            "char_b_pending_memory_empty": char_b_pending_empty,
            "char_c_continuity_command_absent": no_char_c_command,
            "w1_new_source_revision_and_window": w1_new_source,
            "per_actor_revision_monotonic": actor_revision_progression,
            "same_existing_character_record": same_existing_record,
            "zero_write_fields": list(zero_write_keys),
        },
        "w0": evidence["w0"],
        "w1": evidence["w1"],
        "owner": evidence["owner"],
        "character": evidence["character"],
        "activation": evidence["activation"],
        "replay": evidence["replay"],
        "zero_write": evidence["zero_write"],
        "rejections": rejections,
        "architecture": architecture,
        "focused_log": focused_log,
    }
    return write_report("siming-governed-three-actor-cohort-continuity-v1", report)


if __name__ == "__main__":
    raise SystemExit(main())
