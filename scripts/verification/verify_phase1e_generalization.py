from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.gameplay.ownership_contract_debt_sample import OwnershipContractDebtSample
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay, ReplayContext
from app.gameplay.settlement_plan import SettlementPlan
from common import repo_root, verification_dir, write_json, write_markdown
from phase1e_comparison import build_generalization_comparison


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    parser.parse_args()
    root = repo_root()
    directory = verification_dir(root)
    predecessor_names = ("phase1b-contract-verification-report.json", "phase1c-frost-farm-report.json", "phase1d-econ1-bakery-report.json")
    predecessors = []
    for name in predecessor_names:
        try:
            payload = json.loads((directory / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        predecessors.append({"name": name, "passed": any(value is True for key, value in payload.items() if key.startswith("overall_"))})
    sample = OwnershipContractDebtSample(applicant_ref="character:char_a", collateral_ref="ownership:right:1", principal=100, term_ticks=10)
    success = sample.settle(custody_ref="ownership:right:1", permission_scope="character:char_a")
    sample_store = GameplayEventStore()
    sample_settlement = sample.settle_authorities(
        store=sample_store,
        custody_ref="ownership:right:1",
        permission_scope="character:char_a",
    )
    sample_events = sample_store.read_events()
    replay_engine = GameplayProjectionReplay(projector_id="projection:ownership-contract-debt", projector_version="v1")
    sample_replay = replay_engine.full_replay(sample_events)
    checkpoint = replay_engine.create_checkpoint(sample_events[:3], active_patch_set_revision="p1e", registry_revision="p1e", world_config_revision="p1e")
    checkpoint_tail = replay_engine.checkpoint_plus_tail_replay(checkpoint, sample_events[3:], active_patch_set_revision="p1e", registry_revision="p1e", world_config_revision="p1e")
    scoped_replay = replay_engine.replay_with_context(
        sample_events,
        ReplayContext(
            stream_scope=("gameplay:ownership", "gameplay:contract", "gameplay:debt"),
            event_schema_registry_revision="p1e",
            upcaster_chain_digests=(),
            active_world_revision_digest="p1e",
            projector_id="projection:ownership-contract-debt",
            projector_version="v1",
        ),
    )
    failure_matrix = _failure_matrix(sample)
    comparison = build_generalization_comparison()
    passed = (
        all(item["passed"] for item in predecessors)
        and bool(success["result_digest"])
        and sample_settlement["receipt"].committed
        and sample_replay.succeeded
        and checkpoint_tail.succeeded
        and checkpoint_tail.projection_hash == sample_replay.projection_hash
        and scoped_replay.success
        and scoped_replay.applied_event_ids
        and all(item["zero_write"] for item in failure_matrix)
        and all(item["resolved"] for item in failure_matrix)
        and len(comparison.samples) == 3
        and set(comparison.replay_hashes) == set(comparison.samples)
    )
    report = {
        "overall_phase1e_generalization_gate_passed": passed,
        "predecessors": predecessors,
        "sample": success,
        "sample_settlement": sample_settlement["receipt"].model_dump(mode="json"),
        "sample_replay_hash": sample_replay.projection_hash,
        "checkpoint_tail_replay": {"succeeded": checkpoint_tail.succeeded, "projection_hash": checkpoint_tail.projection_hash},
        "scoped_projection": {"succeeded": scoped_replay.success, "applied_event_ids": list(scoped_replay.applied_event_ids), "projection_digest": scoped_replay.resulting_projection_digest},
        "failure_matrix": failure_matrix,
        "applicant_backed_by_existing_profile": sample.applicant_ref in sample.existing_character_refs(),
        "comparison": comparison.__dict__,
        "non_claims": list(comparison.deferred_domains),
    }
    json_path = directory / "phase1e-generalization-gate-report.json"
    md_path = directory / "phase1e-generalization-gate-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "P1E Generalization Gate Verification Report", report, "overall_phase1e_generalization_gate_passed")
    print(f"phase1e_generalization_gate_report_json={json_path}")
    print(f"phase1e_generalization_gate_report_md={md_path}")
    print(f"overall_phase1e_generalization_gate_passed={passed}")
    return 0 if passed else 1


def _failure_matrix(sample: OwnershipContractDebtSample) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []

    def rejected(name: str, operation) -> None:  # type: ignore[no-untyped-def]
        store = GameplayEventStore()
        before = len(store.read_events())
        try:
            operation(store)
        except ValueError as exc:
            code = str(exc)
            resolved = True
        else:
            code = "unexpected_success"
            resolved = False
        entries.append({"case": name, "error_code": code, "zero_write": len(store.read_events()) == before, "resolved": resolved})

    rejected("permission_denied", lambda _store: sample.settle(custody_ref=sample.collateral_ref, permission_scope="character:char_b"))
    rejected("missing_custody", lambda _store: sample.settle(custody_ref="ownership:missing", permission_scope=sample.applicant_ref))

    stale_store = GameplayEventStore()
    stale_command = sample.to_command(custody_ref=sample.collateral_ref, permission_scope=sample.applicant_ref).model_copy(update={"expected_revisions": {f"stream:ownership-contract-debt:{sample.applicant_ref}": 1}})
    stale_result = stale_store.append_batch(SettlementPlan.from_command_envelope(stale_command).to_atomic_event_batch())
    entries.append({"case": "stale_revision", "error_code": stale_result.failure.error_code if stale_result.failure else "unexpected_success", "zero_write": not stale_result.committed and not stale_store.read_events(), "resolved": stale_result.failure is not None})

    duplicate_store = GameplayEventStore()
    duplicate_batch = SettlementPlan.from_command_envelope(sample.to_command(custody_ref=sample.collateral_ref, permission_scope=sample.applicant_ref)).to_atomic_event_batch()
    first = duplicate_store.append_batch(duplicate_batch)
    before_duplicate = len(duplicate_store.read_events())
    duplicate = duplicate_store.append_batch(duplicate_batch)
    entries.append({"case": "duplicate", "error_code": duplicate.idempotency_status, "zero_write": first.committed and duplicate.idempotency_status == "duplicate_replayed" and len(duplicate_store.read_events()) == before_duplicate, "resolved": duplicate.committed})

    conflict_store = GameplayEventStore()
    sample.settle_authorities(store=conflict_store, custody_ref=sample.collateral_ref, permission_scope=sample.applicant_ref)
    before_conflict = len(conflict_store.read_events())
    try:
        sample.model_copy(update={"principal": sample.principal + 1}).settle_authorities(store=conflict_store, custody_ref=sample.collateral_ref, permission_scope=sample.applicant_ref)
    except ValueError as exc:
        conflict_code = str(exc)
        conflict_resolved = True
    else:
        conflict_code = "unexpected_success"
        conflict_resolved = False
    entries.append({"case": "term_conflict", "error_code": conflict_code, "zero_write": len(conflict_store.read_events()) == before_conflict, "resolved": conflict_resolved})
    return entries


if __name__ == "__main__":
    raise SystemExit(main())
