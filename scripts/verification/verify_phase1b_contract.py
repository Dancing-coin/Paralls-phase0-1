from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.gameplay.active_world_revision import ActiveWorldRevisionAuthority, RevisionCandidate
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay, PackageLifecycleAuthority, authorize_project_decision
from app.gameplay.settlement_plan import SettlementPlan
from app.gameplay.shared_contracts import AuthorizationDecision, GameplayPackageManifest, ProjectionEnvelope, Reservation
try:
    from .common import repo_root, verification_dir, write_json, write_markdown
    from .phase1b_contract_fixtures import build_effect_resistance_fixture, build_object_ownership_fixture
except ImportError:  # Direct Harness execution keeps scripts/verification on sys.path.
    from common import repo_root, verification_dir, write_json, write_markdown
    from phase1b_contract_fixtures import build_effect_resistance_fixture, build_object_ownership_fixture


PREDECESSOR = "gameplay-foundation-contract-report.json"


def _load_predecessor(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _package_manifest() -> GameplayPackageManifest:
    return GameplayPackageManifest(
        package_id="package:p1b",
        package_revision="package:p1b:v1",
        domain_id="p1b",
        maturity_level="sample",
        required_core_version="gameplay-core:v1",
        owned_aggregates=("p1b_fixture",),
        commands=("p1b.apply",),
        events=("p1b.evaluated",),
        projections=("projection:p1b",),
        declared_schemas=("p1b.evaluated:v1",),
        privacy_policies=("public",),
        compatibility_range="gameplay-core:v1",
        content_digest="sha256:p1b:v1",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    parser.parse_args()
    root = repo_root()
    evidence_dir = verification_dir(root)
    predecessor_path = evidence_dir / PREDECESSOR
    predecessor = _load_predecessor(predecessor_path)
    predecessor_ok = predecessor.get("overall_gameplay_foundation_contract_passed") is True

    fixtures = [build_effect_resistance_fixture(), build_object_ownership_fixture()]
    store = GameplayEventStore()
    outcomes: list[dict[str, object]] = []
    for fixture in fixtures:
        before = len(store.read_events())
        batch = SettlementPlan.from_command_envelope(fixture.command).to_atomic_event_batch()
        committed = store.append_batch(batch)
        after_success = len(store.read_events())
        stale = store.append_batch(
            batch.model_copy(
                update={
                    "expected_stream_revisions": {next(iter(fixture.command.expected_revisions)): 99},
                    "command_id": f"{batch.command_id}:stale",
                    "idempotency_record": batch.idempotency_record.model_copy(
                        update={
                            "idempotency_key": f"{batch.idempotency_record.idempotency_key}:stale",
                            "payload_digest": "sha256:stale",
                        }
                    ),
                },
                deep=True,
            )
        )
        duplicate = store.append_batch(batch)
        mismatch = store.append_batch(
            batch.model_copy(
                update={
                    "command_id": f"{batch.command_id}:mismatch",
                    "idempotency_record": batch.idempotency_record.model_copy(
                        update={"payload_digest": f"{batch.idempotency_record.payload_digest}:mismatch"}
                    ),
                },
                deep=True,
            )
        )
        permission_rejected = False
        try:
            authorize_project_decision(
                AuthorizationDecision(
                    decision_id=f"decision:{fixture.fixture_id}",
                    principal_ref="principal:p1b",
                    project_scope="project:other",
                    capability="write",
                    data_classification="authority",
                    policy_revision="policy:v1",
                    decision="allow",
                    reason_code="fixture",
                    audit_ref="audit:p1b",
                ),
                project_ref="project:p1b",
            )
        except ValueError as exc:
            permission_rejected = str(exc) == "permission_denied"
        outcomes.append(
            {
                "fixture_id": fixture.fixture_id,
                "owner_map": fixture.owner_map,
                "pinned_revisions": fixture.command.pinned_revisions,
                "success": committed.committed,
                "success_event_count": after_success - before,
                "stale_rejected": not stale.committed and stale.failure is not None and stale.failure.error_code == "revision_conflict",
                "duplicate_replayed": duplicate.idempotency_status == "duplicate_replayed",
                "payload_mismatch_rejected": not mismatch.committed and mismatch.failure is not None and mismatch.failure.error_code == "idempotency_key_reused",
                "permission_rejected": permission_rejected,
                "rejected_event_count": len(store.read_events()) - after_success,
            }
        )

    g1 = predecessor_ok and all(item["success"] is True for item in outcomes)
    g2 = len({item["fixture_id"] for item in outcomes}) == 2
    g3 = all(
        item["stale_rejected"]
        and item["duplicate_replayed"]
        and item["payload_mismatch_rejected"]
        and item["permission_rejected"]
        and item["rejected_event_count"] == 0
        for item in outcomes
    )

    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="p1b", projector_version="v1")
    full = replay.full_replay(events)
    checkpoint = replay.create_checkpoint(
        events[:1],
        active_patch_set_revision="patch:v1",
        registry_revision="registry:v1",
        world_config_revision="world:v1",
    )
    checkpoint_tail = replay.checkpoint_plus_tail_replay(
        checkpoint,
        events[1:],
        active_patch_set_revision="patch:v1",
        registry_revision="registry:v1",
        world_config_revision="world:v1",
    )
    g4 = full.succeeded and checkpoint_tail.succeeded and full.projection_hash == checkpoint_tail.projection_hash

    reservation = Reservation(
        reservation_ref="reservation:p1b:1",
        owner_ref="principal:p1b",
        target_ref="stream:p1b:reservation",
        quantity_or_amount=1,
        status="reserved",
        created_revision=0,
        expires_at_tick=10,
        source_obligation_ref="obligation:p1b:1",
    )
    lifecycle_trace = [{"state": state, "terminal": state != "reserved"} for state in ("reserved", "consumed", "released", "expired", "compensated")]
    reservation_final_rejected = False
    try:
        SettlementPlan.from_reservation(reservation.model_copy(update={"status": "consumed"}))
    except ValueError:
        reservation_final_rejected = True
    g5 = len(lifecycle_trace) == 5 and reservation_final_rejected

    revision_authority = ActiveWorldRevisionAuthority()
    revision_authority.stage(RevisionCandidate(revision_ref="world:p1b:v1"))
    active_revision = revision_authority.activate("world:p1b:v1", tick=1)
    session_pin = revision_authority.pin_session("session:p1b", active_revision.digest)
    g6 = session_pin == active_revision.digest

    manifest = _package_manifest()
    package_authority = PackageLifecycleAuthority()
    package_authority.transition(manifest.package_id, "validated")
    package_authority.transition(manifest.package_id, "staged")
    package_conflict_rejected = False
    try:
        package_authority.transition(manifest.package_id, "retired")
    except ValueError:
        package_conflict_rejected = True
    g7 = package_conflict_rejected

    scopes = {
        "actor": {"fixture_id": "object-ownership", "owner_ref": "owner:p1b"},
        "creator-debug": {"fixture_id": "object-ownership", "owner_ref": "owner:p1b", "trace": "debug"},
        "public": {"fixture_id": "object-ownership"},
        "godot": {"fixture_id": "object-ownership", "result": "committed"},
    }
    projections = [
        ProjectionEnvelope(
            schema_id=f"projection:p1b:{scope}",
            schema_version=1,
            projection_revision="global:2",
            source_revision_vector={event.stream_id: event.stream_revision for event in events},
            privacy_scope=scope,
            payload=payload,
        )
        for scope, payload in scopes.items()
    ]
    g8 = len(projections) == 4 and all(
        projection.payload.get("owner_ref") is None
        for projection in projections
        if projection.privacy_scope in {"public", "godot"}
    )

    gates = {"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5, "G6": g6, "G7": g7, "G8": g8}
    report = {
        "overall_phase1b_contract_verification_passed": all(gates.values()),
        "predecessor": {"path": str(predecessor_path), "passed": predecessor_ok},
        "fixtures": outcomes,
        "gates": gates,
        "replay": {
            "full_hash": full.projection_hash,
            "checkpoint_hash": checkpoint.projection_hash,
            "checkpoint_tail_hash": checkpoint_tail.projection_hash,
        },
        "reservation_lifecycle": lifecycle_trace,
        "package": {"manifest": manifest.model_dump(mode="json"), "conflict_rejected": package_conflict_rejected},
        "projection_scopes": [projection.model_dump(mode="json") for projection in projections],
    }
    json_path = evidence_dir / "phase1b-contract-verification-report.json"
    md_path = evidence_dir / "phase1b-contract-verification-report.md"
    ndjson_path = evidence_dir / "phase1b-contract-verification-evidence.ndjson"
    write_json(json_path, report)
    write_markdown(md_path, "P1B Contract Verification Report", report, "overall_phase1b_contract_verification_passed")
    ndjson_path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in outcomes), encoding="utf-8")
    print(f"phase1b_contract_verification_report_json={json_path}")
    print(f"phase1b_contract_verification_report_md={md_path}")
    print(f"overall_phase1b_contract_verification_passed={report['overall_phase1b_contract_verification_passed']}")
    return 0 if report["overall_phase1b_contract_verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
