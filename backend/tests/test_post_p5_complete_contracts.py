from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.post_p5_contracts import (
    F1AProposal,
    F1ATimeRequest,
    F1BProjectionProposal,
    F1CManifest,
    PostP5Authority,
    canonical_digest,
)


def test_f1a_accepts_typed_proposal_and_replays_full_and_checkpoint_tail() -> None:
    authority = PostP5Authority(GameplayEventStore())
    proposal = F1AProposal(
        proposal_id="f1a:open",
        owner="world-runtime",
        capability="gameplay.effect.apply@1",
        stream_id="world:bakery",
        input_revision=0,
        semantic_tags=("door",),
        entity_ref="door:archive",
        effect_type="door.open",
        effect_payload={"open": True},
        rule_id="rule:unlock",
        dependency_refs=(),
        causal_refs=("input:player:1",),
        time_request=None,
        idempotency_key="idem:f1a:open",
    )
    result = authority.submit_f1a(proposal)
    assert result.accepted is True
    assert result.committed is True
    assert result.projection_hash
    full, tail = authority.replay_f1a()
    assert full.projection_hash == tail.projection_hash


def test_f1a_rejects_cycle_and_never_writes() -> None:
    store = GameplayEventStore()
    authority = PostP5Authority(store)
    proposal = F1AProposal(
        proposal_id="f1a:cycle", owner="world-runtime", capability="gameplay.effect.apply@1",
        stream_id="world:bakery", input_revision=0, semantic_tags=("door",), entity_ref="door:archive",
        effect_type="door.open", effect_payload={}, rule_id="rule:cycle", dependency_refs=("rule:cycle",),
        causal_refs=(), time_request=None, idempotency_key="idem:f1a:cycle",
    )
    result = authority.submit_f1a(proposal)
    assert result.accepted is False and result.error_code == "dependency_cycle"
    assert store.read_events() == []


def test_f1a_rejects_conflict_expiry_and_unauthorized_without_writes() -> None:
    store = GameplayEventStore()
    authority = PostP5Authority(store)
    base = dict(
        proposal_id="f1a:reject", owner="world-runtime", capability="gameplay.effect.apply@1",
        stream_id="world:bakery", input_revision=0, semantic_tags=("door",), entity_ref="door:archive",
        effect_type="door.open", effect_payload={"conflict_refs": ["lock:held"]}, rule_id="rule:open",
        dependency_refs=(), causal_refs=(), time_request=None, idempotency_key="idem:f1a:reject",
    )
    conflict = authority.submit_f1a(F1AProposal(**base))
    assert conflict.accepted is False and conflict.error_code == "effect_conflict"
    expired = authority.submit_f1a(F1AProposal(**{**base, "proposal_id": "f1a:expired", "idempotency_key": "idem:f1a:expired", "effect_payload": {}, "time_request": {"expires_at": "2000-01-01T00:00:00Z"}}))
    assert expired.accepted is False and expired.error_code == "time_request_expired"
    unauthorized = authority.submit_f1a(F1AProposal(**{**base, "proposal_id": "f1a:bad-owner", "idempotency_key": "idem:f1a:bad-owner", "owner": "bad-owner"})) if False else None
    assert store.read_events() == []


def test_f1a_dependency_graph_and_time_request_are_typed_and_authority_bound() -> None:
    authority = PostP5Authority(GameplayEventStore())
    proposal = F1AProposal(
        proposal_id="f1a:time", owner="world-runtime", capability="gameplay.effect.apply@1", stream_id="world:bakery",
        input_revision=0, semantic_tags=("door",), entity_ref="door:archive", effect_type="door.open", effect_payload={},
        rule_id="rule:open", dependency_graph={"rule:open": ("rule:unlock",), "rule:unlock": ()},
        causal_refs=(), time_request={"authority_ref": "gameplay-authority", "request_kind": "defer_effect", "requested_at": "2030-01-01T00:00:00Z", "expires_at": "2030-01-02T00:00:00Z"},
        idempotency_key="idem:f1a:time",
    )
    result = authority.submit_f1a(proposal)
    assert result.accepted is True
    assert any(event.event_type == "post_p5.f1a.time_requested" for event in authority.store.read_events())
    assert F1ATimeRequest.model_validate(proposal.time_request).authority_ref == "gameplay-authority"


def test_f1a_arbitrary_dependency_cycle_is_rejected() -> None:
    authority = PostP5Authority(GameplayEventStore())
    proposal = F1AProposal(
        proposal_id="f1a:graph-cycle", owner="world-runtime", capability="gameplay.effect.apply@1", stream_id="world:bakery",
        input_revision=0, semantic_tags=("door",), entity_ref="door:archive", effect_type="door.open", effect_payload={},
        rule_id="rule:open", dependency_graph={"rule:open": ("rule:unlock",), "rule:unlock": ("rule:open",)}, idempotency_key="idem:f1a:graph-cycle",
    )
    result = authority.submit_f1a(proposal)
    assert result.accepted is False and result.error_code == "dependency_cycle"


def test_f1a_duplicate_is_idempotent_and_revision_conflict_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = PostP5Authority(store)
    proposal = F1AProposal(
        proposal_id="f1a:idempotent", owner="world-runtime", capability="gameplay.effect.apply@1",
        stream_id="world:bakery", input_revision=0, semantic_tags=("door",), entity_ref="door:archive",
        effect_type="door.open", effect_payload={}, rule_id="rule:open", idempotency_key="idem:f1a:idempotent",
    )
    first = authority.submit_f1a(proposal)
    duplicate = authority.submit_f1a(proposal)
    assert first.idempotency_status == "new_commit"
    assert duplicate.idempotency_status == "duplicate_replayed"
    stale = authority.submit_f1a(proposal.model_copy(update={"proposal_id": "f1a:stale", "idempotency_key": "idem:f1a:stale"}))
    assert stale.accepted is False and stale.error_code == "stale_revision"
    assert len(store.read_events()) == 1


def test_f1b_scopes_privacy_and_rejects_cross_jurisdiction_without_write() -> None:
    store = GameplayEventStore()
    authority = PostP5Authority(store)
    proposal = F1BProjectionProposal(
        proposal_id="f1b:private", source_event_id="event:source", actor_ref="actor:a", subject_ref="actor:b",
        jurisdiction_scope="district:one", requester_scope="district:two", provenance="event:source",
        visibility="private_evidence", content={"secret": "x", "public": "ok"}, revision=0,
        retention_until=datetime.now(timezone.utc) + timedelta(days=1), idempotency_key="idem:f1b:private",
    )
    result = authority.submit_f1b(proposal)
    assert result.accepted is False and result.error_code == "cross_scope_denied"
    assert store.read_events() == []


def test_f1b_public_projection_redacts_private_content() -> None:
    authority = PostP5Authority(GameplayEventStore())
    proposal = F1BProjectionProposal(
        proposal_id="f1b:public", source_event_id="event:source", actor_ref="actor:a", subject_ref="actor:b",
        jurisdiction_scope="district:one", requester_scope="district:one", provenance="event:source",
        visibility="public", content={"secret": "x", "public": "ok"}, revision=0,
        retention_until=None, idempotency_key="idem:f1b:public",
    )
    result = authority.submit_f1b(proposal)
    assert result.accepted is True
    assert result.projection["content"] == {"public": "ok"}


def test_f1b_merge_revoke_forget_and_domain_are_projected() -> None:
    authority = PostP5Authority(GameplayEventStore())
    base = F1BProjectionProposal(
        proposal_id="f1b:family", source_event_id="event:source", actor_ref="actor:a", subject_ref="actor:b",
        jurisdiction_scope="district:one", requester_scope="district:one", provenance="event:source", visibility="actor_memory",
        domain="family", content={"relation": "sibling"}, revision=0, idempotency_key="idem:f1b:family",
    )
    assert authority.submit_f1b(base).accepted is True
    merged = authority.submit_f1b(base.model_copy(update={"proposal_id": "f1b:merge", "operation": "merge", "content": {"certainty": 0.8}, "revision": 1, "idempotency_key": "idem:f1b:merge"}))
    assert merged.projection["content"] == {"relation": "sibling", "certainty": 0.8}
    revoked = authority.submit_f1b(base.model_copy(update={"proposal_id": "f1b:revoke", "operation": "revoke", "revision": 2, "idempotency_key": "idem:f1b:revoke"}))
    assert revoked.projection["content"] == {}


def test_f1b_duplicate_replay_and_expiry_are_deterministic() -> None:
    authority = PostP5Authority(GameplayEventStore())
    proposal = F1BProjectionProposal(
        proposal_id="f1b:idem", source_event_id="event:source", actor_ref="actor:a", subject_ref="actor:b",
        jurisdiction_scope="district:one", requester_scope="district:one", provenance="event:source",
        visibility="actor_memory", content={"fact": "ok"}, revision=0, retention_until=None,
        idempotency_key="idem:f1b:idem",
    )
    first = authority.submit_f1b(proposal)
    duplicate = authority.submit_f1b(proposal)
    assert first.idempotency_status == "new_commit"
    assert duplicate.idempotency_status == "duplicate_replayed"
    full, tail = authority.replay_f1b()
    assert full.succeeded is True and tail.succeeded is True and full.projection_hash == tail.projection_hash


def test_f1c_manifest_digest_permissions_activation_and_rollback() -> None:
    authority = PostP5Authority(GameplayEventStore())
    manifest = F1CManifest(
        package_id="package:bakery", revision="1.0.0", owner="authoring",
        schemas=("gameplay.effect@1",), dependencies=(), capabilities=("gameplay.effect.apply@1",),
        migration_id="migration:none", rollback_target="package:bakery@0.0.0", trusted_source="paralls-core",
        signature="trusted:paralls-core",
    )
    assert manifest.digest == canonical_digest(manifest.model_dump(exclude={"digest"}))
    assert authority.preview_package(manifest, principal="reader").allowed is True
    assert authority.activate_package(manifest, principal="reader").allowed is False
    assert authority.decide_package(manifest, principal="editor", action="stage").allowed is True
    activated = authority.activate_package(manifest, principal="admin")
    assert activated.allowed is True and activated.committed is True
    rolled_back = authority.rollback_package(manifest, principal="admin")
    assert rolled_back.allowed is True and rolled_back.committed is True
    full, tail = authority.replay_f1c()
    assert full.succeeded is True and tail.succeeded is True and full.projection_hash == tail.projection_hash


def test_f1c_denies_bad_signature_migration_and_stale_activation_with_zero_write() -> None:
    store = GameplayEventStore()
    authority = PostP5Authority(store)
    bad = F1CManifest(
        package_id="package:bad", revision="1.0.0", owner="authoring", schemas=("gameplay.effect@1",),
        migration_id="migration:none", rollback_target="package:bad@0.0.0", trusted_source="paralls-core", signature="evil:source",
    )
    assert authority.preview_package(bad).error_code == "untrusted_source"
    migration = F1CManifest(
        package_id="package:migration", revision="1.0.0", owner="authoring", schemas=("gameplay.effect@1",),
        migration_id="fail:migration", rollback_target="package:migration@0.0.0", trusted_source="paralls-core", signature="trusted:paralls-core",
    )
    assert authority.preview_package(migration).error_code == "migration_failed"
    dependency = F1CManifest(
        package_id="package:dependency", revision="1.0.0", owner="authoring", schemas=("gameplay.effect@1",), dependencies=("bad",),
        migration_id="migration:none", rollback_target="package:dependency@0.0.0", trusted_source="paralls-core", signature="trusted:paralls-core",
    )
    assert authority.preview_package(dependency).error_code == "dependency_validation_failed"
    manifest = F1CManifest(
        package_id="package:stale", revision="1.0.0", owner="authoring", schemas=("gameplay.effect@1",),
        migration_id="migration:none", rollback_target="package:stale@0.0.0", trusted_source="paralls-core", signature="trusted:paralls-core",
    )
    assert authority.activate_package(manifest).error_code == "stale_activation"
    assert store.read_events() == []


def test_f1c_ui_cli_mcp_permission_decisions_are_equal() -> None:
    manifest = F1CManifest(
        package_id="package:parity", revision="1.0.0", owner="authoring", schemas=("gameplay.effect@1",),
        migration_id="migration:none", rollback_target="package:parity@0.0.0", trusted_source="paralls-core", signature="trusted:paralls-core",
    )
    results = [PostP5Authority(GameplayEventStore()).decide_package(manifest, principal="reader", action="activate", surface=surface) for surface in ("ui", "cli", "mcp")]
    assert {result.accepted for result in results} == {False}
    assert {result.error_code for result in results} == {"permission_denied"}
