from __future__ import annotations

from pathlib import Path

import pytest

from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter
from app.character_agent.profile import CharacterProfileLoader, CharacterProfileRegistry
from app.gameplay.event_schema_registry import (
    PHASE2A_WORK_INTENT_EVENT_SCHEMAS,
    register_phase2a_work_intent_event_schemas,
    EventSchemaRegistry,
)
from app.gameplay.shared_contracts import GameplayPackageManifest


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _registry() -> CharacterProfileRegistry:
    return CharacterProfileRegistry.from_directory(PROFILE_DIR)


def _package_manifest(*, actor_allowlist: tuple[str, ...] = ("char_a", "char_b", "char_c")) -> GameplayPackageManifest:
    return GameplayPackageManifest(
        package_id="package:bakery-authored-agents",
        package_revision="package:bakery-authored-agents:v1",
        domain_id="bakery-authored-agents",
        maturity_level="sample",
        required_core_version="gameplay-core:v1",
        owned_aggregates=("shift", "work_order", "attendance"),
        state_groups=("organization", "production", "survival"),
        commands=(
            "gameplay.work.respond_shift",
            "gameplay.work.start_work",
            "gameplay.work.finish_work",
            "gameplay.work.report_absence",
            "gameplay.work.request_break",
        ),
        events=tuple(schema.event_type for schema in PHASE2A_WORK_INTENT_EVENT_SCHEMAS),
        projections=("projection:bakery-authored-agents",),
        declared_schemas=tuple(f"{schema.event_type}:v{schema.schema_version}" for schema in PHASE2A_WORK_INTENT_EVENT_SCHEMAS),
        dependencies=("gameplay-core:v1",),
        conflicts=(),
        capabilities=("work-intent",),
        privacy_policies=("actor-scoped",),
        mirror_bindings=("godot_actor_scope",),
        compatibility_range="gameplay-core:v1",
        migration_refs=(),
        content_digest="sha256:bakery-authored-agents-v1",
        actor_allowlist=actor_allowlist,
    )


def test_profile_registry_resolves_real_actor_refs_and_rejects_unknown_or_synthetic_refs() -> None:
    registry = _registry()

    assert registry.get("char_a").identity_core.canonical_name == "Lin Yue"

    with pytest.raises(KeyError):
        registry.get("character:npc:1")
    with pytest.raises(KeyError):
        registry.get("character:synthetic:1")


def test_actor_scoped_profile_projection_keeps_identity_filtered_and_scope_explicit() -> None:
    registry = _registry()
    profile = registry.get("char_b")
    view = registry.build_gameplay_scope_view("char_b", profile_registry_revision="profile-registry:v1")

    assert view.actor_ref == "char_b"
    assert view.canonical_name == profile.identity_core.canonical_name
    assert view.occupation_role == profile.identity_core.occupation_role
    assert view.profile_registry_revision == "profile-registry:v1"
    assert view.permitted_role_refs == ("security steward",)


def test_l4_adapter_builds_typed_envelopes_for_all_five_work_intents_without_store_access() -> None:
    registry = _registry()
    adapter = CharacterAgentL4Adapter()
    scope_view = registry.build_gameplay_scope_view("char_b", profile_registry_revision="profile-registry:v1")
    package_manifest = _package_manifest()

    intents = (
        ("respond_shift", {"assignment_ref": "assignment:shift:1", "shift_ref": "shift:1", "response_kind": "accept"}),
        ("start_work", {"work_order_ref": "work_order:1", "operating_window_ref": "window:1"}),
        ("finish_work", {"work_order_ref": "work_order:1", "evidence_refs": ("evidence:work:1",)}),
        ("report_absence", {"shift_ref": "shift:1", "absence_reason": "ill"}),
        ("request_break", {"operating_window_ref": "window:1", "requested_duration_minutes": 15}),
    )

    for intent_kind, payload in intents:
        result = adapter.build_work_intent_result(
            actor_scope_view=scope_view,
            package_manifest=package_manifest,
            intent_kind=intent_kind,
            command_id=f"command:{intent_kind}:1",
            idempotency_key=f"idempotency:{intent_kind}:1",
            source_ref="character-agent:char_b",
            causation_id=f"causation:{intent_kind}:1",
            correlation_id=f"correlation:{intent_kind}:1",
            expected_revisions={"assignment:1": 1, "work_order:1": 1},
            pinned_revisions={"package": 1, "policy": 7, "recipe": 3, "survival": 2, "wage": 5},
            **payload,
        )

        assert result.accepted is True
        assert result.zero_write_guarantee is True
        assert result.rejection is None
        assert result.command_envelope is not None
        assert result.command_envelope.actor_ref == "char_b"
        assert result.command_envelope.causation_id == f"causation:{intent_kind}:1"
        assert result.command_envelope.correlation_id == f"correlation:{intent_kind}:1"
        assert result.command_envelope.pinned_revisions["package"] == 1
        assert result.command_envelope.command_type == f"gameplay.work.{intent_kind}"


def test_package_allowlist_denies_unlisted_actor_with_zero_write() -> None:
    registry = _registry()
    adapter = CharacterAgentL4Adapter()
    scope_view = registry.build_gameplay_scope_view("char_b", profile_registry_revision="profile-registry:v1")

    result = adapter.build_work_intent_result(
        actor_scope_view=scope_view,
        package_manifest=_package_manifest(actor_allowlist=("char_a",)),
        intent_kind="respond_shift",
        command_id="command:denied:1",
        idempotency_key="idempotency:denied:1",
        source_ref="character-agent:char_b",
        causation_id="causation:denied:1",
        correlation_id="correlation:denied:1",
        assignment_ref="assignment:shift:1",
        shift_ref="shift:1",
        response_kind="accept",
        expected_revisions={"assignment:1": 1},
        pinned_revisions={"package": 1},
    )

    assert result.accepted is False
    assert result.zero_write_guarantee is True
    assert result.rejection is not None
    assert result.rejection.error_code == "package_actor_not_allowed"


def test_scope_denial_rejects_intent_outside_actor_projection() -> None:
    registry = _registry()
    adapter = CharacterAgentL4Adapter()
    scope_view = registry.build_gameplay_scope_view(
        "char_b",
        profile_registry_revision="profile-registry:v1",
        allowed_intent_kinds=("respond_shift", "report_absence"),
    )

    result = adapter.build_work_intent_result(
        actor_scope_view=scope_view,
        package_manifest=_package_manifest(),
        intent_kind="start_work",
        command_id="command:scope:1",
        idempotency_key="idempotency:scope:1",
        source_ref="character-agent:char_b",
        causation_id="causation:scope:1",
        correlation_id="correlation:scope:1",
        work_order_ref="work_order:1",
        operating_window_ref="window:1",
        expected_revisions={"work_order:1": 1},
        pinned_revisions={"package": 1},
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.error_code == "projection_scope_denied"
    assert result.zero_write_guarantee is True


def test_revision_payload_and_idempotency_rules_remain_deterministic() -> None:
    registry = _registry()
    adapter = CharacterAgentL4Adapter()
    scope_view = registry.build_gameplay_scope_view("char_b", profile_registry_revision="profile-registry:v1")
    package_manifest = _package_manifest()

    first = adapter.build_work_intent_result(
        actor_scope_view=scope_view,
        package_manifest=package_manifest,
        intent_kind="finish_work",
        command_id="command:duplicate:1",
        idempotency_key="idempotency:duplicate:1",
        source_ref="character-agent:char_b",
        causation_id="causation:duplicate:1",
        correlation_id="correlation:duplicate:1",
        work_order_ref="work_order:1",
        evidence_refs=("evidence:work:1",),
        expected_revisions={"work_order:1": 1},
        pinned_revisions={"package": 1},
    )
    duplicate = adapter.build_work_intent_result(
        actor_scope_view=scope_view,
        package_manifest=package_manifest,
        intent_kind="finish_work",
        command_id="command:duplicate:1",
        idempotency_key="idempotency:duplicate:1",
        source_ref="character-agent:char_b",
        causation_id="causation:duplicate:1",
        correlation_id="correlation:duplicate:1",
        work_order_ref="work_order:1",
        evidence_refs=("evidence:work:1",),
        expected_revisions={"work_order:1": 1},
        pinned_revisions={"package": 1},
    )
    payload_mismatch = adapter.build_work_intent_result(
        actor_scope_view=scope_view,
        package_manifest=package_manifest,
        intent_kind="finish_work",
        command_id="command:mismatch:1",
        idempotency_key="idempotency:mismatch:1",
        source_ref="character-agent:char_b",
        causation_id="causation:mismatch:1",
        correlation_id="correlation:mismatch:1",
        work_order_ref="work_order:1",
        evidence_refs=("evidence:work:1",),
        payload_digest="sha256:wrong",
        expected_revisions={"work_order:1": 1},
        pinned_revisions={"package": 1},
    )
    stale_revision = adapter.build_work_intent_result(
        actor_scope_view=scope_view,
        package_manifest=package_manifest,
        intent_kind="finish_work",
        command_id="command:stale:1",
        idempotency_key="idempotency:stale:1",
        source_ref="character-agent:char_b",
        causation_id="causation:stale:1",
        correlation_id="correlation:stale:1",
        work_order_ref="work_order:1",
        evidence_refs=("evidence:work:1",),
        expected_revisions={"work_order:1": 2},
        current_revisions={"work_order:1": 1},
        pinned_revisions={"package": 1},
    )

    assert first.command_envelope == duplicate.command_envelope
    assert payload_mismatch.accepted is False
    assert payload_mismatch.rejection is not None
    assert payload_mismatch.rejection.error_code == "payload_digest_mismatch"
    assert stale_revision.accepted is False
    assert stale_revision.rejection is not None
    assert stale_revision.rejection.error_code == "revision_conflict"

    changed_retry = adapter.build_work_intent_result(
        actor_scope_view=scope_view,
        package_manifest=package_manifest,
        intent_kind="finish_work",
        command_id="command:duplicate:changed",
        idempotency_key="idempotency:duplicate:1",
        source_ref="character-agent:char_b",
        causation_id="causation:duplicate:1",
        correlation_id="correlation:duplicate:1",
        work_order_ref="work_order:changed",
        evidence_refs=("evidence:work:1",),
        expected_revisions={"work_order:1": 1},
        pinned_revisions={"package": 1},
    )
    assert changed_retry.accepted is False
    assert changed_retry.rejection is not None
    assert changed_retry.rejection.error_code == "payload_digest_mismatch"


def test_phase2a_event_schema_versions_are_registered_for_replay_and_mirror_bootstrap() -> None:
    registry = EventSchemaRegistry()

    register_phase2a_work_intent_event_schemas(registry)

    assert [registration.event_type for registration in PHASE2A_WORK_INTENT_EVENT_SCHEMAS] == [
        "gameplay.work.respond_shift",
        "gameplay.work.start_work",
        "gameplay.work.finish_work",
        "gameplay.work.report_absence",
        "gameplay.work.request_break",
    ]
    for registration in PHASE2A_WORK_INTENT_EVENT_SCHEMAS:
        assert registry.get(registration.event_type, registration.schema_version) == registration
