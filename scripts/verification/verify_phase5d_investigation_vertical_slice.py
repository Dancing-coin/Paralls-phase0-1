from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from typing import Any

from common import repo_root
from verify_phase4_common import run_focused, write_report

PROFILE_NAME = "phase5d-investigation-vertical-slice"
TEST_FILES = (
    "backend/tests/test_p5_bakery_theft_slice.py",
    "backend/tests/test_p5_investigation_conflict.py",
    "backend/tests/test_p5_social_knowledge.py",
    "backend/tests/test_p5_quest_evidence.py",
    "backend/tests/test_p5_contracts.py",
    "backend/tests/test_gameplay_p5_batch_contract.py",
)


@dataclass
class Evidence:
    provenance: dict[str, object] = field(default_factory=dict)
    permission_redaction: dict[str, object] = field(default_factory=dict)
    decision_receipt: dict[str, object] = field(default_factory=dict)
    replay_hash: dict[str, object] = field(default_factory=dict)
    failure_zero_write: dict[str, object] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _load_tests() -> Any:
    path = repo_root() / "backend" / "tests" / "test_p5_bakery_theft_slice.py"
    sys.path.insert(0, str(repo_root()))
    sys.path.insert(0, str(repo_root() / "backend"))
    spec = importlib.util.spec_from_file_location("phase5d_harness_tests", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_evidence() -> Evidence:
    evidence = Evidence()
    try:
        fixtures = _load_tests()
        from app.gameplay.event_store import GameplayEventStore
        from app.gameplay.models import ProjectionCheckpoint
        from app.gameplay.survival_runtime import SurvivalMode

        registry = fixtures._social_registry()
        authority_type = fixtures._load_slice()
        authority = authority_type(
            social_registry=registry,
            quest_registry=fixtures._quest_registry(),
            conflict_registry=fixtures._conflict_registry(),
            store=GameplayEventStore(),
        )
        bundle = fixtures._success_bundle(request_id="request:harness:p5d:success")
        success = authority.resolve(
            social_command=bundle["social_command"], social_request=bundle["social_request"],
            quest_command=bundle["quest_command"], quest_request=bundle["quest_request"],
            conflict_command=bundle["conflict_command"], conflict_request=bundle["conflict_request"],
            owner_fragments=(), reward_fragments=(), survival_mode=SurvivalMode.DISABLED,
            now="2026-08-11T00:00:00Z",
        )
        duplicate = authority.resolve(
            social_command=bundle["social_command"], social_request=bundle["social_request"],
            quest_command=bundle["quest_command"], quest_request=bundle["quest_request"],
            conflict_command=bundle["conflict_command"], conflict_request=bundle["conflict_request"],
            owner_fragments=(), reward_fragments=(), survival_mode=SurvivalMode.DISABLED,
            now="2026-08-11T00:00:00Z",
        )
        adverse_store = GameplayEventStore()
        adverse_authority = authority_type(
            social_registry=registry,
            quest_registry=fixtures._quest_registry(),
            conflict_registry=fixtures._conflict_registry(),
            store=adverse_store,
        )
        adverse_bundle = fixtures._success_bundle(request_id="request:harness:p5d:alarm")
        adverse = adverse_authority.resolve(
            social_command=adverse_bundle["social_command"], social_request=adverse_bundle["social_request"],
            quest_command=adverse_bundle["quest_command"], quest_request=adverse_bundle["quest_request"],
            conflict_command=fixtures._conflict_command(
                request_id="request:harness:p5d:alarm", resistance_ref="resistance:guard-alert",
                alarm_ref="alarm:bakery", status_revision_ref="status:alerted",
            ),
            conflict_request=fixtures._conflict_request(
                fixtures._conflict_registry(), request_id="request:harness:p5d:alarm",
                resistance_ref="resistance:guard-alert", alarm_ref="alarm:bakery",
                status_revision_ref="status:alerted",
            ),
            owner_fragments=(fixtures._status_fragment(),), reward_fragments=(),
            survival_mode=SurvivalMode.NARRATIVE, now="2026-08-11T00:00:00Z",
        )
        public = authority.view_for(recipient_ref="character:outsider", now="2026-08-11T00:00:00Z")
        private = authority.view_for(recipient_ref="character:investigator:alpha", now="2026-08-11T00:00:00Z")
        full = authority.replay_full(now="2026-08-11T00:00:00Z")
        checkpoint = ProjectionCheckpoint(
            checkpoint_id="checkpoint:harness:p5d", projector_id=full.projector_id,
            projector_version=full.projector_version, projection_schema_version=1,
            source_revision_vector=full.source_revision_vector, last_global_sequence=full.last_global_sequence,
            state=full.state, applied_event_ids=full.applied_event_ids, projection_hash=full.projection_hash,
        )
        tail = authority.replay_checkpoint_tail(checkpoint=checkpoint, now="2026-08-11T00:00:00Z")

        hidden_store = GameplayEventStore()
        hidden_authority = authority_type(
            social_registry=registry, quest_registry=fixtures._quest_registry(),
            conflict_registry=fixtures._conflict_registry(), store=hidden_store,
        )
        hidden = hidden_authority.resolve(
            social_command=bundle["social_command"].model_copy(update={"payload": {**bundle["social_command"].payload, "knowledge_fact": {**bundle["knowledge_fact"], "visibility": "public"}}}, deep=True),
            social_request=bundle["social_request"], quest_command=bundle["quest_command"],
            quest_request=bundle["quest_request"], conflict_command=bundle["conflict_command"],
            conflict_request=bundle["conflict_request"], owner_fragments=(), reward_fragments=(),
            survival_mode=SurvivalMode.DISABLED, now="2026-08-11T00:00:00Z",
        )
        unsupported_store = GameplayEventStore()
        unsupported = authority_type(
            social_registry=registry, quest_registry=fixtures._quest_registry(),
            conflict_registry=fixtures._conflict_registry(), store=unsupported_store,
        ).resolve(
            social_command=bundle["social_command"], social_request=bundle["social_request"],
            quest_command=bundle["quest_command"], quest_request=bundle["quest_request"],
            conflict_command=bundle["conflict_command"], conflict_request=bundle["conflict_request"],
            owner_fragments=(), reward_fragments=(), survival_mode=SurvivalMode.LIGHTWEIGHT,
            now="2026-08-11T00:00:00Z",
        )
        survival_bundle = fixtures._success_bundle(request_id="request:harness:p5d:survival")
        disabled_store = GameplayEventStore()
        narrative_store = GameplayEventStore()
        disabled = authority_type(
            social_registry=registry, quest_registry=fixtures._quest_registry(),
            conflict_registry=fixtures._conflict_registry(), store=disabled_store,
        ).resolve(
            social_command=survival_bundle["social_command"], social_request=survival_bundle["social_request"],
            quest_command=survival_bundle["quest_command"], quest_request=survival_bundle["quest_request"],
            conflict_command=survival_bundle["conflict_command"], conflict_request=survival_bundle["conflict_request"],
            owner_fragments=(), reward_fragments=(), survival_mode=SurvivalMode.DISABLED,
            now="2026-08-11T00:00:00Z",
        )
        narrative_authority = authority_type(
            social_registry=registry, quest_registry=fixtures._quest_registry(),
            conflict_registry=fixtures._conflict_registry(), store=narrative_store,
        )
        narrative = narrative_authority.resolve(
            social_command=survival_bundle["social_command"], social_request=survival_bundle["social_request"],
            quest_command=survival_bundle["quest_command"], quest_request=survival_bundle["quest_request"],
            conflict_command=survival_bundle["conflict_command"], conflict_request=survival_bundle["conflict_request"],
            owner_fragments=(), reward_fragments=(), survival_mode=SurvivalMode.NARRATIVE,
            now="2026-08-11T00:00:00Z",
        )
        evidence.provenance = {
            "registry_ref": registry.registry_ref, "registry_revision": registry.registry_revision,
            "registry_digest": registry.registry_digest, "event_count": len(authority._store.read_events()),
        }
        evidence.permission_redaction = {
            "public_hidden_clue_redacted": "hidden_clue_ref" not in public["conflict"]["investigations"][0],
            "private_hidden_clue_ref": private["conflict"]["investigations"][0].get("hidden_clue_ref"),
            "public_quest_events_redacted": not public["quest"]["evidence_events"],
            "public_private_hashes_differ": public["projection_hash"] != private["projection_hash"],
        }
        evidence.decision_receipt = {
            "result_kind": success.resolution.result_kind,
            "committed": bool(success.resolution.committed_event_refs),
            "event_refs": list(success.resolution.committed_event_refs),
            "duplicate_event_refs": list(duplicate.resolution.committed_event_refs),
            "duplicate_component_receipts": [
                receipt.idempotency_status
                for receipt in (duplicate.social_result.receipt, duplicate.quest_result.receipt, duplicate.conflict_result.receipt)
                if receipt is not None
            ],
            "alarm_event_present": any(e.event_type == "gameplay.conflict.alarm_raised" for e in adverse_store.read_events()),
            "nonlethal_status_present": any(e.event_type == "gameplay.status_tag.applied" for e in adverse_store.read_events()),
            "adverse_result_kind": adverse.conflict_result.resolution.result_kind,
            "survival_disabled_result_kind": disabled.resolution.result_kind,
            "survival_narrative_result_kind": narrative.resolution.result_kind,
            "survival_write_equivalent": [e.event_type for e in disabled_store.read_events()] == [e.event_type for e in narrative_store.read_events()],
        }
        evidence.replay_hash = {
            "full_succeeded": full.succeeded, "tail_succeeded": tail.succeeded,
            "full_hash": full.projection_hash, "tail_hash": tail.projection_hash,
            "hash_equal": full.projection_hash == tail.projection_hash,
        }
        evidence.failure_zero_write = {
            "hidden_result_kind": hidden.resolution.result_kind,
            "hidden_failure_code": hidden.resolution.failure_code,
            "hidden_zero_write": hidden_store.read_events() == [],
            "unsupported_result_kind": unsupported.resolution.result_kind,
            "unsupported_failure_code": unsupported.resolution.failure_code,
            "unsupported_zero_write": unsupported_store.read_events() == [],
        }
    except Exception as exc:  # pragma: no cover
        evidence.errors.append(f"scenario_collection_failed:{exc}")
    return evidence


def _scenario_passed(e: Evidence) -> bool:
    return not e.errors and e.decision_receipt.get("result_kind") == "committed_success" and e.decision_receipt.get("committed") is True and e.decision_receipt.get("duplicate_event_refs") == e.decision_receipt.get("event_refs") and e.decision_receipt.get("duplicate_component_receipts") == ["duplicate_replayed"] * 3 and e.decision_receipt.get("adverse_result_kind") == "committed_adverse_outcome" and e.decision_receipt.get("alarm_event_present") is True and e.decision_receipt.get("nonlethal_status_present") is True and e.decision_receipt.get("survival_disabled_result_kind") == "committed_success" and e.decision_receipt.get("survival_narrative_result_kind") == "committed_success" and e.decision_receipt.get("survival_write_equivalent") is True and e.permission_redaction.get("public_hidden_clue_redacted") is True and e.permission_redaction.get("public_quest_events_redacted") is True and e.replay_hash.get("hash_equal") is True and e.failure_zero_write.get("hidden_result_kind") == "rejected_zero_write" and e.failure_zero_write.get("hidden_zero_write") is True and e.failure_zero_write.get("unsupported_result_kind") == "rejected_zero_write" and e.failure_zero_write.get("unsupported_zero_write") is True


def main() -> int:
    focused_ok, focused_log = run_focused(*TEST_FILES)
    scenario = collect_evidence()
    report = {
        "overall_passed": focused_ok and _scenario_passed(scenario),
        "focused_tests_passed": focused_ok, "focused_test_files": list(TEST_FILES),
        "focused_log": focused_log, "provenance": scenario.provenance,
        "permission_redaction": scenario.permission_redaction,
        "decision_receipt": scenario.decision_receipt,
        "replay_hash": scenario.replay_hash,
        "failure_zero_write": scenario.failure_zero_write,
    }
    if scenario.errors:
        report["errors"] = scenario.errors
    return write_report(PROFILE_NAME, report)


if __name__ == "__main__":
    raise SystemExit(main())
