from __future__ import annotations

from datetime import datetime, timezone

import pytest


def test_replay_context_and_evidence_pin_revision_and_projection_digest() -> None:
    from app.gameplay.replay import GameplayProjectionReplay, ReplayContext
    from test_gameplay_event_store_contract import _event

    event = _event("evt:replay:1", stream_id="stream:replay")
    event["stream_revision"] = 1
    event["global_sequence"] = 1
    context = ReplayContext(
        stream_scope=("stream:replay",),
        event_schema_registry_revision="schema:v1",
        upcaster_chain_digests=("sha256:upcaster",),
        active_world_revision_digest="sha256:world",
        projector_id="projection:replay",
        projector_version="v1",
    )
    evidence = GameplayProjectionReplay(projector_id="projection:replay", projector_version="v1").replay_with_context([event], context)
    assert evidence.success is True
    assert evidence.active_world_revision_digest == "sha256:world"
    assert evidence.resulting_projection_digest


def test_package_lifecycle_rejects_invalid_transition() -> None:
    from app.gameplay.replay import PackageLifecycleAuthority

    authority = PackageLifecycleAuthority()
    authority.transition("package:demo", "validated")
    with pytest.raises(ValueError, match="package_compatibility_failed"):
        authority.transition("package:demo", "active")


def test_authorization_decision_requires_matching_project_and_unexpired_policy() -> None:
    from app.gameplay.replay import authorize_project_decision
    from app.gameplay.shared_contracts import AuthorizationDecision

    decision = AuthorizationDecision(
        decision_id="decision:1",
        principal_ref="principal:reader",
        project_scope="project:demo",
        capability="reader",
        data_classification="project",
        policy_revision="policy:v1",
        decision="allow",
        reason_code="ok",
        expires_at="2099-01-01T00:00:00Z",
        audit_ref="audit:1",
    )
    assert authorize_project_decision(decision, project_ref="project:demo", now=datetime.now(timezone.utc)) is True
    with pytest.raises(ValueError, match="permission_denied"):
        authorize_project_decision(decision, project_ref="project:other", now=datetime.now(timezone.utc))


def test_package_manifest_keeps_explicit_actor_allowlist_for_permission_gates() -> None:
    from app.gameplay.shared_contracts import GameplayPackageManifest

    manifest = GameplayPackageManifest(
        package_id="package:bakery-authored-agents",
        package_revision="package:bakery-authored-agents:v1",
        domain_id="bakery-authored-agents",
        maturity_level="sample",
        required_core_version="gameplay-core:v1",
        owned_aggregates=("shift",),
        state_groups=("organization",),
        commands=("gameplay.work.respond_shift",),
        events=("gameplay.work.respond_shift",),
        projections=("projection:bakery-authored-agents",),
        declared_schemas=("gameplay.work.respond_shift:v1",),
        dependencies=("gameplay-core:v1",),
        conflicts=(),
        capabilities=("work-intent",),
        privacy_policies=("actor-scoped",),
        mirror_bindings=("godot_actor_scope",),
        compatibility_range="gameplay-core:v1",
        migration_refs=(),
        content_digest="sha256:bakery-authored-agents-v1",
        actor_allowlist=("char_a", "char_b"),
    )

    assert manifest.actor_allowlist == ("char_a", "char_b")
