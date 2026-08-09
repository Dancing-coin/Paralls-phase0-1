from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.frost_farm_package import frost_farm_manifest
from app.gameplay.frost_farm_runtime import FrostFarmAuthority, project_frost_result
from app.gameplay.replay import GameplayProjectionReplay
from common import repo_root, verification_dir, write_json, write_markdown
from phase1b_contract_fixtures import build_effect_resistance_fixture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    parser.parse_args()
    root = repo_root()
    evidence_dir = verification_dir(root)
    predecessor_path = evidence_dir / "phase1b-contract-verification-report.json"
    try:
        predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        predecessor = {}
    predecessor_ok = predecessor.get("overall_phase1b_contract_verification_passed") is True
    fixture = build_effect_resistance_fixture()
    effect_payload = {
        "plot_ref": "plot:frost:1",
        "crop_ref": "crop:wheat:1",
        "resistance": 0.25,
        "frost_intensity": 0.8,
        "permission_scope": "owner:farm",
    }
    from app.gameplay.frost_farm_runtime import CropState, EnvironmentFact, FarmPlot, FrostEffectInput, ResistanceProfile

    effect = FrostEffectInput(
        plot=FarmPlot(plot_ref="plot:frost:1", jurisdiction_ref="jurisdiction:north", owner_ref="owner:farm"),
        crop=CropState(crop_ref="crop:wheat:1", plot_ref="plot:frost:1", state="growing", health=100),
        resistance=ResistanceProfile(profile_ref="resistance:wheat:v1", resistance=0.25),
        frost_intensity=0.8,
        permission_scope="owner:farm",
        environment_fact=EnvironmentFact(fact_ref="fact:frost:1", kind="frost", intensity=0.8, evidence_ref="evidence:frost:1"),
    )
    store = GameplayEventStore()
    from app.gameplay.shared_contracts import GameplayCommandEnvelope

    command = GameplayCommandEnvelope(
        command_id="command:frost:1", command_type="farm.apply_frost", command_version=1, principal_ref="owner:farm",
        actor_ref="actor:farm", project_ref="project:farm", transaction_id="transaction:frost:1", idempotency_key="idempotency:frost:1",
        expected_revisions={"plot:frost:1": 0}, causation_id="cause:frost:1", correlation_id="corr:frost:1", source_ref="source:environment",
        submitted_at="2026-08-07T00:00:00Z", pinned_revisions={"world": 1, "policy": 1},
        payload={"stream_ref": "plot:frost:1", "event_type": "farm.crop_frost_evaluated"},
    )
    result = FrostFarmAuthority.settle(effect, command=command, store=store)
    replay = GameplayProjectionReplay(projector_id="projection:frost", projector_version="v1").full_replay(store.read_events())
    report = {
        "overall_phase1c_frost_farm_passed": predecessor_ok and result.committed and replay.succeeded and frost_farm_manifest().content_digest.startswith("sha256:"),
        "predecessor_passed": predecessor_ok,
        "manifest": frost_farm_manifest().model_dump(mode="json"),
        "effect": effect_payload,
        "settlement": result.model_dump(mode="json"),
        "replay": {"succeeded": replay.succeeded, "projection_hash": replay.projection_hash},
        "projection": project_frost_result(replay, scope="public").model_dump(mode="json") if replay.succeeded else {},
    }
    json_path = evidence_dir / "phase1c-frost-farm-report.json"
    md_path = evidence_dir / "phase1c-frost-farm-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "P1C Frost Farm Verification Report", report, "overall_phase1c_frost_farm_passed")
    print(f"phase1c_frost_farm_report_json={json_path}")
    print(f"phase1c_frost_farm_report_md={md_path}")
    print(f"overall_phase1c_frost_farm_passed={report['overall_phase1c_frost_farm_passed']}")
    return 0 if report["overall_phase1c_frost_farm_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
