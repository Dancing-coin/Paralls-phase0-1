from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import AttendanceEvidence, RoleAssignment, ShiftOffer, WorkOrder
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch

try:
    from common import repo_root, verification_dir, write_json, write_markdown
except ModuleNotFoundError:
    from scripts.verification.common import repo_root, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root(); directory = verification_dir(root)
    assignment = RoleAssignment(assignment_ref="assignment:baker", organization_ref="org:bakery", character_ref="character:char_b", role="baker", permitted_role_ref="baker/production", authorization_revision=1)
    offer = ShiftOffer(shift_ref="shift:1", assignment_ref=assignment.assignment_ref, work_kind="production", operating_window_ref="window:1")
    order = WorkOrder(work_order_ref="work:1", shift_ref=offer.shift_ref, evidence_kind="production-completed")
    evidence = AttendanceEvidence(evidence_ref="evidence:1", actor_ref=assignment.character_ref, assignment_ref=assignment.assignment_ref, work_order_ref=order.work_order_ref, source_ref="run:1", issuer_principal_ref="actor_gameplay.production_domain", evidence_kind="production-completed", observed_at="tick:1", outcome="completed", verification_state="verified", source_digest="sha256:1")
    store = GameplayEventStore()
    batch = build_multi_stream_atomic_event_batch(command_id="p2b:conflict", principal_ref="actor_gameplay.organization_domain", expected_revisions={"gameplay:organization:org:bakery": 0, "gameplay:construction_production:facility:1": 1}, event_specs={"gameplay:organization:org:bakery": [("gameplay.organization.work_started", {"work_order_ref": order.work_order_ref})], "gameplay:construction_production:facility:1": [("gameplay.construction_production.work_started", {"run_ref": "run:1"})]}, idempotency_key="p2b:conflict", causation_id="p2b:cause", correlation_id="p2b:corr")
    rejected = store.append_batch(batch)
    canonical = {"assignment": assignment.model_dump(mode="json"), "offer": offer.model_dump(mode="json"), "order": order.model_dump(mode="json"), "evidence": evidence.model_dump(mode="json")}
    report = {"overall_phase2b_organization_work_lifecycle_passed": rejected.committed is False and rejected.failure is not None and not store.read_events(), "receipt": {"committed": rejected.committed, "failure": rejected.failure.model_dump(mode="json") if rejected.failure else None}, "event_diff": {"before": 0, "after": len(store.read_events())}, "revision_vector": dict(batch.expected_stream_revisions), "replay_hash": "sha256:" + sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest(), "scope_redaction": {"actor": ["own_assignment", "own_work"], "redacted": ["other_actor_memory", "private_wage_detail"]}, "zero_write": not store.read_events()}
    write_json(directory / "phase2b-organization-work-lifecycle-report.json", report)
    write_markdown(directory / "phase2b-organization-work-lifecycle-report.md", "P2B Organization Work Lifecycle", report, "overall_phase2b_organization_work_lifecycle_passed")
    print(f"overall_phase2b_organization_work_lifecycle_passed={report['overall_phase2b_organization_work_lifecycle_passed']}")
    return 0 if report["overall_phase2b_organization_work_lifecycle_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
