from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common import repo_root
from verify_phase4_common import run_focused, write_report


PROFILE_NAME = "phase5a-quest-objective-evidence"
TEST_FILES = (
    "backend/tests/test_p5_quest_evidence.py",
    "backend/tests/test_p5_contracts.py",
    "backend/tests/test_gameplay_p5_batch_contract.py",
)


@dataclass
class Phase5aScenarioEvidence:
    provenance: dict[str, object]
    permission_redaction: dict[str, object]
    decision_receipt: dict[str, object]
    replay_hash: dict[str, object]
    failure_zero_write: dict[str, object]
    errors: list[str] = field(default_factory=list)


def _load_test_module() -> Any:
    backend_root = repo_root() / "backend"
    sys.path.insert(0, str(backend_root))
    module_path = repo_root() / "backend" / "tests" / "test_p5_quest_evidence.py"
    spec = importlib.util.spec_from_file_location("phase5a_test_helpers", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _unavailable(reason: str) -> Phase5aScenarioEvidence:
    payload = {"status": "unavailable", "reason": reason}
    return Phase5aScenarioEvidence(
        provenance=dict(payload),
        permission_redaction=dict(payload),
        decision_receipt=dict(payload),
        replay_hash=dict(payload),
        failure_zero_write=dict(payload),
        errors=[reason],
    )


def collect_phase5a_scenario_evidence() -> Phase5aScenarioEvidence:
    try:
        fixtures = _load_test_module()
        from app.gameplay.replay import GameplayProjectionReplay
    except Exception as exc:  # pragma: no cover - import failures are reported in the written profile report
        return _unavailable(f"scenario_import_failed:{exc}")

    try:
        registry = fixtures._registry()
        committed_store = fixtures.GameplayEventStore()
        authority = fixtures._load_authority()(registry=registry, store=committed_store)
        command = fixtures._command()
        request = fixtures._request(registry)

        committed = authority.resolve(
            command=command,
            request=request,
            reward_fragments=(),
            now="2026-08-11T00:00:00Z",
        )
        duplicate = authority.resolve(
            command=command,
            request=request,
            reward_fragments=(),
            now="2026-08-11T00:00:00Z",
        )

        events = committed_store.read_events()
        replay = GameplayProjectionReplay(projector_id="verification:phase5a", projector_version="v1")
        full = replay.full_replay(events)
        split_at = max(1, len(events) // 2)
        checkpoint = replay.create_checkpoint(events[:split_at])
        checkpoint_tail = replay.checkpoint_plus_tail_replay(checkpoint, events[split_at:])

        failure_store = fixtures.GameplayEventStore()
        failure_authority = fixtures._load_authority()(registry=registry, store=failure_store)
        before_failure_events = len(failure_store.read_events())
        hidden_request_id = "request:p5:quest-evidence:hidden"
        hidden_result = failure_authority.resolve(
            command=fixtures._command(
                request_id=hidden_request_id,
                payload_updates={"visibility": "actor:other"},
            ),
            request=fixtures._request(
                registry,
                request_id=hidden_request_id,
                request_updates={
                    "proposed_events": (
                        {
                            "event_name": "gameplay.quest.evidence_registered",
                            "schema_version": 1,
                            "stream_ref": fixtures._evidence_stream_ref(
                                fixtures._default_evidence_ref(hidden_request_id)
                            ),
                            "visibility": "actor:other",
                        },
                        {
                            "event_name": "gameplay.quest.objective_transitioned",
                            "schema_version": 1,
                            "stream_ref": fixtures._quest_stream_ref("quest-instance-1"),
                            "visibility": "actor:other",
                        },
                    )
                },
            ),
            reward_fragments=(),
            now="2026-08-11T00:00:00Z",
        )
        after_failure_events = len(failure_store.read_events())

        evidence_event = events[0]
        objective_event = events[1]
        objective = registry.quest_packages[0].objectives[0]

        return Phase5aScenarioEvidence(
            provenance={
                "provider_ref": evidence_event.payload["provider_ref"],
                "provenance_source_ref": evidence_event.payload["provenance_source_ref"],
                "subject_ref": evidence_event.payload["subject_ref"],
                "evidence_ref": evidence_event.payload["evidence_ref"],
                "registry_digest": evidence_event.payload["registry_digest"],
                "package_digest": evidence_event.payload["package_digest"],
                "evidence_stream_ref": evidence_event.stream_id,
                "quest_stream_ref": objective_event.stream_id,
            },
            permission_redaction={
                "objective_visibility": objective.visibility,
                "accepted_evidence_kind_refs": list(objective.accepted_evidence_kind_refs),
                "prerequisite_fact_refs": list(objective.prerequisite_fact_refs),
                "evidence_event_visibility": evidence_event.visibility_policy,
                "objective_event_visibility": objective_event.visibility_policy,
                "hidden_visibility_failure_code": hidden_result.resolution.failure_code,
            },
            decision_receipt={
                "result_kind": committed.resolution.result_kind,
                "committed": bool(committed.receipt and committed.receipt.committed),
                "transaction_id": committed.receipt.transaction_id if committed.receipt else None,
                "committed_event_ids": list(committed.receipt.committed_event_ids) if committed.receipt else [],
                "idempotency_status": committed.receipt.idempotency_status if committed.receipt else None,
                "duplicate_result_kind": duplicate.resolution.result_kind,
                "duplicate_idempotency_status": duplicate.receipt.idempotency_status if duplicate.receipt else None,
                "settlement_plan_event_mapping": dict(committed.settlement_plan.event_mapping) if committed.settlement_plan else {},
            },
            replay_hash={
                "event_count": len(events),
                "snapshot_hash": fixtures._snapshot_hash(committed_store),
                "full_replay_succeeded": full.succeeded,
                "checkpoint_tail_succeeded": checkpoint_tail.succeeded,
                "replay_hash": full.projection_hash,
                "checkpoint_tail_hash": checkpoint_tail.projection_hash,
            },
            failure_zero_write={
                "result_kind": hidden_result.resolution.result_kind,
                "failure_code": hidden_result.resolution.failure_code,
                "zero_write": before_failure_events == after_failure_events,
                "event_count_before": before_failure_events,
                "event_count_after": after_failure_events,
            },
        )
    except Exception as exc:  # pragma: no cover - profile output should capture this directly
        return _unavailable(f"scenario_collection_failed:{exc}")


def _scenario_passed(scenario: Phase5aScenarioEvidence) -> bool:
    if scenario.errors:
        return False

    decision = scenario.decision_receipt
    replay = scenario.replay_hash
    failure = scenario.failure_zero_write
    visibility = scenario.permission_redaction
    return bool(
        decision.get("result_kind") == "committed_success"
        and decision.get("committed") is True
        and decision.get("duplicate_idempotency_status") == "duplicate_replayed"
        and replay.get("full_replay_succeeded") is True
        and replay.get("checkpoint_tail_succeeded") is True
        and replay.get("replay_hash")
        and replay.get("replay_hash") == replay.get("checkpoint_tail_hash")
        and failure.get("result_kind") == "rejected_zero_write"
        and failure.get("failure_code") == "p5_evidence_hidden"
        and failure.get("zero_write") is True
        and visibility.get("objective_visibility") == "authority_only"
    )


def build_report(
    *,
    focused_ok: bool,
    focused_log: str,
    scenario: Phase5aScenarioEvidence,
) -> dict[str, object]:
    report: dict[str, object] = {
        "overall_passed": focused_ok and _scenario_passed(scenario),
        "focused_tests_passed": focused_ok,
        "focused_test_files": list(TEST_FILES),
        "focused_log": focused_log,
        "provenance": scenario.provenance,
        "permission_redaction": scenario.permission_redaction,
        "decision_receipt": scenario.decision_receipt,
        "replay_hash": scenario.replay_hash,
        "failure_zero_write": scenario.failure_zero_write,
    }
    if scenario.errors:
        report["errors"] = list(scenario.errors)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    parser.parse_args(argv)

    focused_ok, focused_log = run_focused(*TEST_FILES)
    scenario = collect_phase5a_scenario_evidence()
    report = build_report(focused_ok=focused_ok, focused_log=focused_log, scenario=scenario)
    return write_report(PROFILE_NAME, report)


if __name__ == "__main__":
    raise SystemExit(main())
