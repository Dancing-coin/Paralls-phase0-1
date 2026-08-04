from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from common import repo_root, resolve_godot_exe, resolve_python_exe, run_command, verification_dir, write_json, write_markdown

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.gameplay.adventure_basic_closure import capture_adventure_basic_closure
from app.gameplay.adventure_basic_mirror_source import AdventureBasicMirrorSource
from app.gameplay.adventure_basic_reference import (
    AdventureBasicScenario1,
    AdventureBasicScenario2,
    AdventureBasicScenario3,
    AdventureBasicScenario4,
    AdventureBasicScenario5,
)


TEST_FILES = [
    "backend/tests/test_adventure_basic_reference.py",
    "backend/tests/test_adventure_basic_scenario1.py",
    "backend/tests/test_adventure_basic_scenario2.py",
    "backend/tests/test_adventure_basic_scenario3.py",
    "backend/tests/test_adventure_basic_scenario4.py",
    "backend/tests/test_adventure_basic_scenario5.py",
    "backend/tests/test_adventure_basic_closure_evidence.py",
    "backend/tests/test_adventure_basic_mirror_source.py",
    "backend/tests/test_adventure_basic_mirror_runtime.py",
]

CLOSURE_EVIDENCE_FILENAME = "adventure-basic-closure-evidence.json"
LIVE_MIRROR_REPORT_FILENAME = "live-adventure-basic-mirror-report.json"
LIVE_MIRROR_VERIFIER = "scripts/verification/verify_live_adventure_basic_mirror.py"

SCOPE = (
    "digest-valid governed adventure-basic manifest plus Scenarios 1 through 5 backend compositions; "
    "each scenario now has an authoritative rebuilt domain facade, online/full/checkpoint-tail replay evidence, "
    "a backend-owned filtered mirror projection source, and real Godot mirror delivery after canonical authority commits; "
    "it does not prove Patch activation, client authority, prediction, or generic transport durability"
)


def _build_closure_evidence() -> dict[str, object]:
    scenario1 = AdventureBasicScenario1.create()
    assert scenario1.purchase_sword().committed
    assert scenario1.equip_sword().committed

    scenario2 = AdventureBasicScenario2.create()
    assert scenario2.purchase_sword().committed
    assert scenario2.equip_sword().committed
    assert scenario2.swing_sword().accepted

    scenario3 = AdventureBasicScenario3.create()
    assert scenario3.equip_storage_ring().committed
    assert scenario3.move_to_storage_ring(scenario3.cargo_item_id).committed

    scenario4 = AdventureBasicScenario4.create()
    assert scenario4.purchase_land().committed
    assert scenario4.issue_deed_credential().committed
    assert scenario4.transfer_land_right().committed

    scenario5 = AdventureBasicScenario5.create()
    assert scenario5.gift_archive_relic().committed
    assert scenario5.issue_archive_debt().committed
    assert scenario5.repay_archive_debt(scenario5.debt_principal).committed
    assert scenario5.create_service_contract().committed
    assert scenario5.discard_contract_document().committed
    assert scenario5.complete_service_contract().committed

    scenario_pairs = [
        ("scenario-1", scenario1),
        ("scenario-2", scenario2),
        ("scenario-3", scenario3),
        ("scenario-4", scenario4),
        ("scenario-5", scenario5),
    ]
    evidence = [
        capture_adventure_basic_closure(scenario_id=scenario_id, scenario=scenario)
        for scenario_id, scenario in scenario_pairs
    ]
    mirror_projections = {
        scenario_id: _mirror_projection(scenario_id=scenario_id, scenario=scenario)
        for scenario_id, scenario in scenario_pairs
    }
    return {
        "scope": "Backend-authoritative rebuilt facades, generic event replay, and filtered mirror source only; no delivery or Godot completion claim.",
        "scenarios": [asdict(item) for item in evidence],
        "mirror_projections": mirror_projections,
        "all_facade_replay_hashes_match": all(
            item.online_facade_hash == item.full_replay_facade_hash == item.checkpoint_tail_facade_hash
            and item.online_replay_hash == item.full_replay_hash == item.checkpoint_tail_replay_hash
            for item in evidence
        ),
        "all_backend_mirror_projections_present": len(mirror_projections) == 5,
    }


def _mirror_projection(*, scenario_id: str, scenario: object) -> dict[str, object]:
    view = AdventureBasicMirrorSource(scenario_id=scenario_id, scenario=scenario).godot_view()  # type: ignore[arg-type]
    return {
        "actor_ref": view.actor_ref,
        "facade_revision": view.source_facade_revision,
        "source_revision_vector": dict(view.source_revision_vector),
        "view_checksum": view.view_checksum,
        "groups": {
            group_id: {
                "projection_revision": envelope.projection_revision,
                "payload": dict(envelope.payload),
            }
            for group_id, envelope in view.groups.items()
        },
    }


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _live_mirror_report_is_complete(report: dict[str, object]) -> bool:
    scenarios = report.get("scenarios", [])
    return (
        report.get("overall_live_adventure_basic_mirror_passed") is True
        and isinstance(scenarios, list)
        and len(scenarios) == 5
        and all(isinstance(item, dict) and item.get("status") == "proved" for item in scenarios)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log_dir = verification_dir(root)
    pytest_log = log_dir / "adventure-basic-pytest.log"
    python_exe = resolve_python_exe(args.python_exe)
    result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], root, pytest_log)
    closure_evidence_path = log_dir / CLOSURE_EVIDENCE_FILENAME
    closure_evidence: dict[str, object] = {}
    if result.returncode == 0:
        closure_evidence = _build_closure_evidence()
        write_json(closure_evidence_path, closure_evidence)
    facade_replay_proved = (
        result.returncode == 0
        and bool(closure_evidence.get("all_facade_replay_hashes_match", False))
        and bool(closure_evidence.get("all_backend_mirror_projections_present", False))
        and len(closure_evidence.get("scenarios", [])) == 5
    )
    live_mirror_log = log_dir / "adventure-basic-live-mirror.log"
    live_mirror_report_path = log_dir / LIVE_MIRROR_REPORT_FILENAME
    live_mirror_result = None
    live_mirror_report: dict[str, object] = {}
    if result.returncode == 0:
        try:
            godot_exe = resolve_godot_exe(args.godot_exe)
        except FileNotFoundError as exc:
            live_mirror_log.write_text(f"godot_runtime_unavailable={exc}\n", encoding="utf-8")
        else:
            live_mirror_result = run_command(
                [python_exe, LIVE_MIRROR_VERIFIER, "--godot-exe", str(godot_exe), "--python-exe", python_exe],
                root,
                live_mirror_log,
            )
            live_mirror_report = _read_json_object(live_mirror_report_path)
    live_mirror_proved = live_mirror_result is not None and live_mirror_result.returncode == 0 and _live_mirror_report_is_complete(live_mirror_report)
    required_scenarios_complete = facade_replay_proved and live_mirror_proved
    report = {
        "overall_adventure_basic_passed": result.returncode == 0 and required_scenarios_complete,
        "adventure_basic_required_scenarios_complete": required_scenarios_complete,
        "scope": SCOPE,
        "results": [
            {
                "id": "manifest-baseline",
                "title": "Adventure-basic manifest is strict and digest-valid before activation; Scenarios 1 through 5 exercise purchase/equip, body/resource constraints, equipment-gated storage-ring authority, deed/title separation, and gift/debt/typed-contract lifecycles",
                "status": "proved" if result.returncode == 0 else "missing",
                "evidence": [str(pytest_log)] if result.returncode == 0 else [],
                "notes": f"exit_code={result.returncode}",
            }
            ,
            {
                "id": "backend-facade-and-replay",
                "title": "Each of the five authoritative scenarios rebuilds a domain facade with revision/result metadata, source refs, matching online/full/checkpoint-tail replay hashes, and a filtered backend mirror source",
                "status": "proved" if facade_replay_proved else "missing",
                "evidence": [str(closure_evidence_path)] if facade_replay_proved else [],
                "notes": "Read-only backend replay and mirror-source evidence; it does not stand in for WebSocket delivery or Godot runtime proof.",
            },
            {
                "id": "full-adventure-closure",
                "title": "All five scenarios have authoritative backend, replay, mirror, explanation, and real Godot runtime evidence",
                "status": "proved" if required_scenarios_complete else "missing",
                "evidence": [str(live_mirror_log), str(live_mirror_report_path)] if required_scenarios_complete else [],
                "notes": "" if required_scenarios_complete else "The live Godot report must prove all five server-selected canonical deliveries; unavailable Godot or any missing scenario fails this closure.",
            }
        ],
        "artifacts": {
            "pytest_log": str(pytest_log),
            "closure_evidence": str(closure_evidence_path) if facade_replay_proved else "",
            "live_mirror_log": str(live_mirror_log),
            "live_mirror_report": str(live_mirror_report_path) if live_mirror_proved else "",
        },
    }
    json_path = log_dir / "adventure-basic-report.json"
    markdown_path = log_dir / "adventure-basic-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Adventure Basic Verification Report", report, "overall_adventure_basic_passed")
    print(f"adventure_basic_report_json={json_path}")
    print(f"adventure_basic_report_md={markdown_path}")
    print(f"overall_adventure_basic_passed={result.returncode == 0 and required_scenarios_complete}")
    return 0 if result.returncode == 0 and required_scenarios_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
