from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import AttendanceEvidence, OrganizationAuthority
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from fixtures.phase2_bakery_authored_agents import authored_bakery_fixture


def test_three_authored_actors_keep_identity_and_two_roles_complete() -> None:
    fixture = authored_bakery_fixture()
    assert set(fixture["actors"]) == {"character:char_a", "character:char_b", "character:char_c"}
    assignments = fixture["assignments"]
    assert assignments[1].role == "baker/production"
    assert assignments[2].role == "counter/procurement"
    evidence = AttendanceEvidence(evidence_ref="evidence:baker", actor_ref="character:char_b", assignment_ref="assignment:baker", work_order_ref="work:baker", source_ref="run:baker", issuer_principal_ref="actor_gameplay.production_domain", evidence_kind="production-completed", observed_at="tick:1", outcome="completed", verification_state="verified", source_digest="sha256:baker")
    assert OrganizationAuthority.completed_evidence(evidence).actor_ref == "character:char_b"


def test_vertical_failure_is_zero_write_and_replayable() -> None:
    store = GameplayEventStore()
    batch = build_atomic_event_batch(command_id="p2d:failure", principal_ref="actor_gameplay.organization_domain", stream_id="gameplay:organization:org:bakery-authored", expected_revision=1, event_specs=[("gameplay.organization.work_absent", {"actor_ref": "character:char_b"})], idempotency_key="p2d:failure", causation_id="p2d:cause", correlation_id="p2d:corr")
    result = store.append_batch(batch)
    assert result.committed is False and store.read_events() == []
    replay = GameplayProjectionReplay(projector_id="p2d", projector_version="1").full_replay(store.read_events())
    assert replay.succeeded
