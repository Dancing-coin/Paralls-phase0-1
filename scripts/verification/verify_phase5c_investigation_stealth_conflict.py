from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass, field
from typing import Any

from common import repo_root
from verify_phase4_common import run_focused, write_report


PROFILE_NAME = "phase5c-investigation-stealth-conflict"
TEST_FILES = (
    "backend/tests/test_p5_investigation_conflict.py",
    "backend/tests/test_p5_social_knowledge.py",
    "backend/tests/test_p5_quest_evidence.py",
    "backend/tests/test_p5_contracts.py",
    "backend/tests/test_gameplay_p5_batch_contract.py",
)


@dataclass
class Phase5cScenarioEvidence:
    provenance: dict[str, object]
    permission_redaction: dict[str, object]
    decision_receipt: dict[str, object]
    replay_hash: dict[str, object]
    failure_zero_write: dict[str, object]
    errors: list[str] = field(default_factory=list)


def _load_test_module() -> Any:
    backend_root = repo_root() / "backend"
    sys.path.insert(0, str(backend_root))
    module_path = repo_root() / "backend" / "tests" / "test_p5_investigation_conflict.py"
    spec = importlib.util.spec_from_file_location("phase5c_test_helpers", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _unavailable(reason: str) -> Phase5cScenarioEvidence:
    payload = {"status": "unavailable", "reason": reason}
    return Phase5cScenarioEvidence(
        provenance=dict(payload),
        permission_redaction=dict(payload),
        decision_receipt=dict(payload),
        replay_hash=dict(payload),
        failure_zero_write=dict(payload),
        errors=[reason],
    )


def _events_by_type(events: list[Any]) -> dict[str, Any]:
    return {event.event_type: event for event in events}


def _view_projection(view: dict[str, object]) -> dict[str, object]:
    return {
        "investigations": list(view.get("investigations", [])),
        "conflicts": list(view.get("conflicts", [])),
        "consequences": list(view.get("consequences", [])),
        "source_revision_vector": dict(view.get("source_revision_vector", {})),
        "projection_hash": view.get("projection_hash"),
    }


def collect_phase5c_scenario_evidence() -> Phase5cScenarioEvidence:
    try:
        fixtures = _load_test_module()
        from app.gameplay.event_store import GameplayEventStore
        from app.gameplay.models import ProjectionCheckpoint
    except Exception as exc:  # pragma: no cover - import failures are reported in the written profile report
        return _unavailable(f"scenario_import_failed:{exc}")

    try:
        registry = fixtures._registry()
        authority_type = fixtures._load_authority()

        success_store = GameplayEventStore()
        success_authority = authority_type(registry=registry, store=success_store)
        success_command = fixtures._command()
        success_request = fixtures._request(registry)
        success = success_authority.resolve(
            command=success_command,
            request=success_request,
            now="2026-08-11T00:00:00Z",
        )
        duplicate = success_authority.resolve(
            command=success_command,
            request=success_request,
            now="2026-08-11T00:00:00Z",
        )
        success_events = success_store.read_events()
        success_event_map = _events_by_type(success_events)

        public_view = success_authority.view_for(recipient_ref="character:outsider", now="2026-08-11T00:00:00Z")
        private_view = success_authority.view_for(
            recipient_ref="character:investigator:alpha",
            now="2026-08-11T00:00:00Z",
        )
        authority_view = success_authority.view_for(recipient_ref="authority:auditor", now="2026-08-11T00:00:00Z")

        adverse_store = GameplayEventStore()
        adverse_authority = authority_type(registry=registry, store=adverse_store)
        adverse = adverse_authority.resolve(
            command=fixtures._command(request_id="request:p5c:adverse"),
            request=fixtures._request(registry, request_id="request:p5c:adverse"),
            owner_fragments=(fixtures._status_fragment(),),
            now="2026-08-11T00:00:00Z",
        )
        adverse_events = adverse_store.read_events()
        adverse_event_map = _events_by_type(adverse_events)
        status_event = adverse_event_map["gameplay.status_tag.applied"]
        alarm_event = adverse_event_map["gameplay.conflict.alarm_raised"]
        conflict_event = adverse_event_map["gameplay.conflict.attempt_resolved"]

        skill_gate_store = GameplayEventStore()
        skill_gate_authority = authority_type(registry=registry, store=skill_gate_store)
        skill_gate_before = fixtures._snapshot_hash(skill_gate_store)
        skill_gate = skill_gate_authority.resolve(
            command=fixtures._command(
                request_id="request:p5c:skill-gate",
                affordance_ref="affordance:lockpick",
                skill_ref="skill:unknown",
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5c:skill-gate",
                affordance_ref="affordance:lockpick",
                skill_ref="skill:unknown",
            ),
            now="2026-08-11T00:00:00Z",
        )
        skill_gate_after = fixtures._snapshot_hash(skill_gate_store)

        resistance_store = GameplayEventStore()
        resistance_authority = authority_type(registry=registry, store=resistance_store)
        resistance_before = fixtures._snapshot_hash(resistance_store)
        resistance = resistance_authority.resolve(
            command=fixtures._command(
                request_id="request:p5c:resistance",
                resistance_ref="resistance:unknown",
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5c:resistance",
                resistance_ref="resistance:unknown",
            ),
            now="2026-08-11T00:00:00Z",
        )
        resistance_after = fixtures._snapshot_hash(resistance_store)

        hidden_store = GameplayEventStore()
        hidden_authority = authority_type(registry=registry, store=hidden_store)
        hidden_before = fixtures._snapshot_hash(hidden_store)
        hidden = hidden_authority.resolve(
            command=fixtures._command(
                request_id="request:p5c:hidden",
                perception_visibility="hidden",
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5c:hidden",
                perception_visibility="hidden",
            ),
            now="2026-08-11T00:00:00Z",
        )
        hidden_after = fixtures._snapshot_hash(hidden_store)

        malformed_store = GameplayEventStore()
        malformed_authority = authority_type(registry=registry, store=malformed_store)
        malformed_before = fixtures._snapshot_hash(malformed_store)
        malformed = malformed_authority.resolve(
            command=fixtures._command(
                request_id="request:p5c:malformed",
                payload_updates={"hidden_clue_ref": ""},
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5c:malformed",
                request_updates={"subject_scope_ref": "character:outsider"},
            ),
            now="2026-08-11T00:00:00Z",
        )
        malformed_after = fixtures._snapshot_hash(malformed_store)

        invalid_visibility_store = GameplayEventStore()
        invalid_visibility_authority = authority_type(registry=registry, store=invalid_visibility_store)
        invalid_visibility_before = fixtures._snapshot_hash(invalid_visibility_store)
        invalid_visibility = invalid_visibility_authority.resolve(
            command=fixtures._command(request_id="request:p5c:invalid-visibility"),
            request=fixtures._request(registry, request_id="request:p5c:invalid-visibility"),
            owner_fragments=(fixtures._status_fragment_with_visibility("project"),),
            now="2026-08-11T00:00:00Z",
        )
        invalid_visibility_after = fixtures._snapshot_hash(invalid_visibility_store)

        atomicity_store = GameplayEventStore()
        atomicity_authority = authority_type(registry=registry, store=atomicity_store)
        atomicity_before = fixtures._snapshot_hash(atomicity_store)
        overlapping_fragment = fixtures._status_fragment().model_copy(
            update={"expected_revisions": {fixtures.CONFLICT_STREAM: 0}},
            deep=True,
        )
        atomicity = atomicity_authority.resolve(
            command=fixtures._command(request_id="request:p5c:atomicity"),
            request=fixtures._request(registry, request_id="request:p5c:atomicity"),
            owner_fragments=(overlapping_fragment,),
            now="2026-08-11T00:00:00Z",
        )
        atomicity_after = fixtures._snapshot_hash(atomicity_store)

        replay_store = GameplayEventStore()
        replay_authority = authority_type(registry=registry, store=replay_store)
        replay_first = replay_authority.resolve(
            command=fixtures._command(request_id="request:p5c:replay-1"),
            request=fixtures._request(registry, request_id="request:p5c:replay-1"),
            now="2026-08-11T00:00:00Z",
        )
        prefix = replay_authority.replay_full(now="2026-08-11T00:00:00Z")
        checkpoint = ProjectionCheckpoint(
            checkpoint_id="checkpoint:p5c:harness",
            projector_id="projector:p5:investigation-conflict",
            projector_version="v1",
            projection_schema_version=1,
            source_revision_vector=prefix.source_revision_vector,
            last_global_sequence=prefix.last_global_sequence,
            state=prefix.state,
            applied_event_ids=tuple(prefix.applied_event_ids),
            projection_hash=prefix.projection_hash,
            active_patch_set_revision="patch:p5c:v1",
            registry_revision=registry.registry_revision,
            world_config_revision="world:p5c:v1",
        )
        revisions_two = {
            fixtures.INVESTIGATION_STREAM: 1,
            fixtures.CONFLICT_STREAM: 1,
            fixtures.ALARM_STREAM: 0,
            fixtures.STATUS_STREAM: 0,
        }
        replay_command_two = fixtures._command(request_id="request:p5c:replay-2").model_copy(
            update={
                "expected_revisions": revisions_two,
                "read_set_revisions": {
                    fixtures.INVESTIGATION_STREAM: 1,
                    fixtures.CONFLICT_STREAM: 1,
                    fixtures.ALARM_STREAM: 0,
                    fixtures.STATUS_STREAM: 0,
                    fixtures.RELATIONSHIP_REF: 0,
                    fixtures.KNOWLEDGE_STREAM: 0,
                },
            },
            deep=True,
        )
        replay_request_two = fixtures._request(registry, request_id="request:p5c:replay-2").model_copy(
            update={
                "expected_revisions": fixtures.P5RevisionVector(entries=revisions_two),
                "read_set_revisions": fixtures.P5RevisionVector(
                    entries={
                        fixtures.INVESTIGATION_STREAM: 1,
                        fixtures.CONFLICT_STREAM: 1,
                        fixtures.ALARM_STREAM: 0,
                        fixtures.STATUS_STREAM: 0,
                        fixtures.RELATIONSHIP_REF: 0,
                        fixtures.KNOWLEDGE_STREAM: 0,
                    }
                ),
            },
            deep=True,
        )
        replay_second = replay_authority.resolve(
            command=replay_command_two,
            request=replay_request_two,
            now="2026-08-11T01:00:00Z",
        )
        replay_full = replay_authority.replay_full(now="2026-08-11T00:00:00Z")
        replay_tail = replay_authority.replay_checkpoint_tail(checkpoint=checkpoint, now="2026-08-11T00:00:00Z")
        replay_public_view = replay_authority.view_for(
            recipient_ref="character:outsider",
            now="2026-08-11T01:00:00Z",
        )
        replay_private_view = replay_authority.view_for(
            recipient_ref="character:investigator:alpha",
            now="2026-08-11T01:00:00Z",
        )

        return Phase5cScenarioEvidence(
            provenance={
                "provider_ref": "provider:evidence:p5c",
                "registry_ref": registry.registry_ref,
                "registry_revision": registry.registry_revision,
                "registry_digest": registry.registry_digest,
                "case_ref": fixtures.CASE_REF,
                "attempt_ref": fixtures.ATTEMPT_REF,
                "perception_event_visibility": success_event_map["gameplay.investigation.observation_resolved"].visibility_policy,
                "perception_ref": success_event_map["gameplay.investigation.observation_resolved"].payload["perception_ref"],
                "hidden_clue_ref": success_event_map["gameplay.investigation.observation_resolved"].payload["hidden_clue_ref"],
                "knowledge_stream_ref": success_event_map["gameplay.investigation.observation_resolved"].payload["knowledge_stream_ref"],
                "relationship_ref": success_event_map["gameplay.investigation.observation_resolved"].payload["relationship_ref"],
                "conflict_stream_ref": success_event_map["gameplay.conflict.attempt_resolved"].stream_id,
                "investigation_stream_ref": success_event_map["gameplay.investigation.observation_resolved"].stream_id,
                "success_committed_event_ids": list(success.receipt.committed_event_ids) if success.receipt else [],
            },
            permission_redaction={
                "public_view": _view_projection(public_view),
                "private_view": _view_projection(private_view),
                "authority_view": _view_projection(authority_view),
                "public_hidden_clue_redacted": "hidden_clue_ref" not in public_view["investigations"][0],
                "public_hidden_evidence_redacted": "hidden_evidence" not in public_view["investigations"][0],
                "private_hidden_clue_ref": private_view["investigations"][0].get("hidden_clue_ref"),
                "private_hidden_evidence": private_view["investigations"][0].get("hidden_evidence"),
                "authority_hidden_clue_ref": authority_view["investigations"][0].get("hidden_clue_ref"),
                "authority_hidden_evidence": authority_view["investigations"][0].get("hidden_evidence"),
                "public_projection_hash": public_view["projection_hash"],
                "private_projection_hash": private_view["projection_hash"],
                "authority_projection_hash": authority_view["projection_hash"],
            },
            decision_receipt={
                "success_result_kind": success.resolution.result_kind,
                "success_committed": bool(success.receipt and success.receipt.committed),
                "success_transaction_id": success.receipt.transaction_id if success.receipt else None,
                "success_committed_event_ids": list(success.receipt.committed_event_ids) if success.receipt else [],
                "duplicate_result_kind": duplicate.resolution.result_kind,
                "duplicate_idempotency_status": duplicate.receipt.idempotency_status if duplicate.receipt else None,
                "duplicate_transaction_id": duplicate.receipt.transaction_id if duplicate.receipt else None,
                "duplicate_committed_event_ids": list(duplicate.receipt.committed_event_ids) if duplicate.receipt else [],
                "skill_gate_result_kind": skill_gate.resolution.result_kind,
                "skill_gate_failure_code": skill_gate.resolution.failure_code,
                "resistance_result_kind": resistance.resolution.result_kind,
                "resistance_failure_code": resistance.resolution.failure_code,
                "adverse_result_kind": adverse.resolution.result_kind,
                "adverse_committed": bool(adverse.receipt and adverse.receipt.committed),
                "adverse_transaction_id": adverse.receipt.transaction_id if adverse.receipt else None,
                "adverse_committed_event_ids": list(adverse.receipt.committed_event_ids) if adverse.receipt else [],
                "adverse_event_types": [event.event_type for event in adverse_events],
                "adverse_conflict_outcome": conflict_event.payload["outcome"],
                "adverse_alarm_ref": alarm_event.payload["alarm_ref"],
                "adverse_status_revision_ref": conflict_event.payload["status_revision_ref"],
                "registered_nonlethal_status_tag_ref": status_event.payload["status_tag_ref"],
                "registered_nonlethal_status_kind": status_event.payload["status_kind"],
                "registered_nonlethal_visibility": status_event.visibility_policy,
                "settlement_plan_event_mapping": dict(adverse.settlement_plan.event_mapping) if adverse.settlement_plan else {},
            },
            replay_hash={
                "event_count": len(replay_store.read_events()),
                "first_result_kind": replay_first.resolution.result_kind,
                "second_result_kind": replay_second.resolution.result_kind,
                "full_replay_succeeded": replay_full.succeeded,
                "checkpoint_tail_succeeded": replay_tail.succeeded,
                "full_replay_hash": replay_full.projection_hash,
                "checkpoint_tail_hash": replay_tail.projection_hash,
                "full_last_global_sequence": replay_full.last_global_sequence,
                "checkpoint_tail_last_global_sequence": replay_tail.last_global_sequence,
                "public_projection_hash": replay_public_view["projection_hash"],
                "private_projection_hash": replay_private_view["projection_hash"],
                "full_public_hidden_redacted": "hidden_evidence" not in replay_public_view["investigations"][0],
                "full_private_hidden_present": replay_private_view["investigations"][0].get("hidden_evidence"),
            },
            failure_zero_write={
                "hidden_perception_result_kind": hidden.resolution.result_kind,
                "hidden_perception_failure_code": hidden.resolution.failure_code,
                "hidden_perception_zero_write": hidden_before == hidden_after,
                "skill_gate_zero_write": skill_gate_before == skill_gate_after,
                "resistance_zero_write": resistance_before == resistance_after,
                "malformed_result_kind": malformed.resolution.result_kind,
                "malformed_failure_code": malformed.resolution.failure_code,
                "malformed_zero_write": malformed_before == malformed_after,
                "invalid_visibility_result_kind": invalid_visibility.resolution.result_kind,
                "invalid_visibility_failure_code": invalid_visibility.resolution.failure_code,
                "invalid_visibility_zero_write": invalid_visibility_before == invalid_visibility_after,
                "atomicity_result_kind": atomicity.resolution.result_kind,
                "atomicity_failure_code": atomicity.resolution.failure_code,
                "atomicity_zero_write": atomicity_before == atomicity_after,
            },
        )
    except Exception as exc:  # pragma: no cover - profile output should capture this directly
        return _unavailable(f"scenario_collection_failed:{exc}")


def _scenario_passed(scenario: Phase5cScenarioEvidence) -> bool:
    if scenario.errors:
        return False

    provenance = scenario.provenance
    permission = scenario.permission_redaction
    decision = scenario.decision_receipt
    replay = scenario.replay_hash
    failure = scenario.failure_zero_write
    return bool(
        provenance.get("provider_ref") == "provider:evidence:p5c"
        and provenance.get("perception_event_visibility") == "public"
        and decision.get("success_result_kind") == "committed_success"
        and decision.get("success_committed") is True
        and decision.get("duplicate_result_kind") == "committed_success"
        and decision.get("duplicate_idempotency_status") == "duplicate_replayed"
        and decision.get("duplicate_transaction_id") == decision.get("success_transaction_id")
        and decision.get("duplicate_committed_event_ids") == decision.get("success_committed_event_ids")
        and decision.get("skill_gate_result_kind") == "rejected_zero_write"
        and decision.get("skill_gate_failure_code") == "p5_capability_unauthorized"
        and decision.get("resistance_result_kind") == "rejected_zero_write"
        and decision.get("resistance_failure_code") == "p5_resistance_unregistered"
        and decision.get("adverse_result_kind") == "committed_adverse_outcome"
        and decision.get("adverse_committed") is True
        and decision.get("adverse_conflict_outcome") == "adverse"
        and decision.get("adverse_alarm_ref") == "alarm:bakery"
        and decision.get("adverse_status_revision_ref") == "status:alerted"
        and decision.get("registered_nonlethal_status_tag_ref") == "status:alerted"
        and decision.get("registered_nonlethal_status_kind") == "nonlethal"
        and decision.get("registered_nonlethal_visibility") == "authority_only"
        and permission.get("public_hidden_clue_redacted") is True
        and permission.get("public_hidden_evidence_redacted") is True
        and permission.get("private_hidden_clue_ref") == provenance.get("hidden_clue_ref")
        and permission.get("private_hidden_evidence") == provenance.get("hidden_clue_ref")
        and permission.get("authority_hidden_clue_ref") == provenance.get("hidden_clue_ref")
        and permission.get("authority_hidden_evidence") == provenance.get("hidden_clue_ref")
        and permission.get("public_projection_hash") != permission.get("private_projection_hash")
        and replay.get("full_replay_succeeded") is True
        and replay.get("checkpoint_tail_succeeded") is True
        and replay.get("full_replay_hash")
        and replay.get("full_replay_hash") == replay.get("checkpoint_tail_hash")
        and replay.get("full_public_hidden_redacted") is True
        and replay.get("full_private_hidden_present") == provenance.get("hidden_clue_ref")
        and failure.get("hidden_perception_result_kind") == "rejected_zero_write"
        and failure.get("hidden_perception_failure_code") == "p5_perception_hidden"
        and failure.get("hidden_perception_zero_write") is True
        and failure.get("skill_gate_zero_write") is True
        and failure.get("resistance_zero_write") is True
        and failure.get("malformed_result_kind") == "rejected_zero_write"
        and failure.get("malformed_failure_code") == "p5_investigation_input_invalid"
        and failure.get("malformed_zero_write") is True
        and failure.get("invalid_visibility_result_kind") == "rejected_zero_write"
        and failure.get("invalid_visibility_failure_code") == "p5_owner_fragment_rejected"
        and failure.get("invalid_visibility_zero_write") is True
        and failure.get("atomicity_result_kind") == "rejected_zero_write"
        and failure.get("atomicity_failure_code") == "p5_atomicity_violation"
        and failure.get("atomicity_zero_write") is True
    )


def build_report(
    *,
    focused_ok: bool,
    focused_log: str,
    scenario: Phase5cScenarioEvidence,
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
    scenario = collect_phase5c_scenario_evidence()
    report = build_report(focused_ok=focused_ok, focused_log=focused_log, scenario=scenario)
    return write_report(PROFILE_NAME, report)


if __name__ == "__main__":
    raise SystemExit(main())
