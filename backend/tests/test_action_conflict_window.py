from __future__ import annotations

import json
from hashlib import sha256

from app.gameplay.action_graph_content import ActionGraphDefinition, ActionGraphNode
from app.gameplay.action_window_runtime import ActionWindowIntent, SpatialSnapshotRef
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.contracts import (
    P5SchemaPin,
    QuestObjectiveDefinition,
    QuestPackageDefinition,
)
from app.gameplay.p5.investigation_conflict import InvestigationConflictAuthority
from app.gameplay.p5.registry import (
    OwnerAdapterAllowance,
    P5EventCatalogEntry,
    P5EventNamespace,
    P5PolicyRegistry,
    P5StreamGrammar,
    TrustedEvidenceProvider,
)
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.settlement_plan import build_atomic_event_batch


REGISTRY_REF = "registry:p5:action-window"
REGISTRY_REVISION = "registry:p5:action-window:v1"
PACKAGE_REF = "package:p5:action-window"
PACKAGE_REVISION = "package:p5:action-window:v1"
RULESET_REVISION = "ruleset:p5:action-window:v1"
EVENT_STREAM = "gameplay:conflict:encounter:bakery-theft"
SOURCE_STREAM = "world:encounter:bakery-theft"
ROLE_REF = "role:survivor@1"

EVENT_TYPES = (
    "gameplay.conflict.encounter_started",
    "gameplay.conflict.action_window_resolved",
    "gameplay.conflict.control_changed",
    "gameplay.conflict.terminal_outcome_recorded",
    "gameplay.conflict.encounter_closed",
)


def _digest(hex_digit: str) -> str:
    return f"sha256:{hex_digit * 64}"


def _registry() -> P5PolicyRegistry:
    objective = QuestObjectiveDefinition(
        objective_ref="objective:p5:action-window",
        prerequisite_fact_refs=("fact:encounter:opened",),
        accepted_evidence_kind_refs=("evidence:window",),
        visibility="authority_only",
        expiry_policy_ref="expiry:never",
    )
    package = QuestPackageDefinition(
        package_ref=PACKAGE_REF,
        package_revision=PACKAGE_REVISION,
        package_digest=_digest("3"),
        ruleset_revision=RULESET_REVISION,
        objectives=(objective,),
    )
    return P5PolicyRegistry.build(
        registry_ref=REGISTRY_REF,
        registry_revision=REGISTRY_REVISION,
        trusted_evidence_providers=(
            TrustedEvidenceProvider(
                provider_ref="provider:evidence:action-window",
                provider_revision="provider:evidence:action-window:v1",
                provider_digest=_digest("1"),
                allowed_evidence_kinds=("evidence:window",),
            ),
        ),
        owner_adapter_allowlist=(
            OwnerAdapterAllowance(
                owner_ref="owner:action-window-authority",
                allowed_event_names=EVENT_TYPES,
                allowed_stream_grammar_refs=("grammar:p5:action-window",),
            ),
        ),
        quest_packages=(package,),
        ruleset_revisions=(RULESET_REVISION,),
        schema_pins=tuple(
            P5SchemaPin(schema_ref=f"schema:p5:action-window:{suffix}", schema_version=1, schema_digest=_digest(digest))
            for suffix, digest in (
                ("encounter-started", "4"),
                ("window-resolved", "5"),
                ("control-changed", "6"),
                ("terminal-outcome-recorded", "7"),
                ("encounter-closed", "8"),
            )
        ),
        event_namespaces=(
            P5EventNamespace(
                namespace_ref="namespace:p5:action-window",
                event_name_prefix="gameplay.conflict.",
                allowed_event_names=EVENT_TYPES,
            ),
        ),
        event_catalog=tuple(
            P5EventCatalogEntry(
                event_name=event_type,
                namespace_ref="namespace:p5:action-window",
                schema_ref=schema_ref,
                schema_version=1,
                stream_grammar_ref="grammar:p5:action-window",
            )
            for event_type, schema_ref in zip(
                EVENT_TYPES,
                (
                    "schema:p5:action-window:encounter-started",
                    "schema:p5:action-window:window-resolved",
                    "schema:p5:action-window:control-changed",
                    "schema:p5:action-window:terminal-outcome-recorded",
                    "schema:p5:action-window:encounter-closed",
                ),
                strict=True,
            )
        ),
        stream_grammars=(
            P5StreamGrammar(grammar_ref="grammar:p5:action-window", pattern=r"^gameplay:conflict:encounter:[^:]+$"),
            P5StreamGrammar(grammar_ref="grammar:p5:action-window-source", pattern=r"^world:encounter:[^:]+$"),
        ),
    )


def _graph() -> ActionGraphDefinition:
    return ActionGraphDefinition(
        graph_ref="graph:warehouse-case",
        graph_revision="graph:warehouse-case@1",
        action_family="scripted_mystery",
        role_refs=(ROLE_REF,),
        primitive_refs=("primitive:advance@1",),
        nodes=(
            ActionGraphNode(
                node_ref="node:start",
                primitive_ref="primitive:advance@1",
                phase="active",
                duration_window=(0, 1),
                cancel_targets=("node:start",),
                condition_refs=("state:entry@1",),
                asset_ref="asset:door@1",
                contact_marker_refs=("marker:doorway@1",),
            ),
        ),
        edges=(),
        capability_refs=("capability:observe@1",),
        observation_requirements=("observation:visibility@1",),
        asset_refs=("asset:door@1",),
        interruption_policy="policy:interrupt-default@1",
        recovery_policy="policy:recovery@1",
        policy_revision="policy:action-graph@1",
    )


def _intent() -> ActionWindowIntent:
    return ActionWindowIntent.model_validate(
        {
            "attempt_ref": "attempt:bakery-theft:1",
            "encounter_ref": "encounter:bakery-theft",
            "actor_ref": "character:survivor:alpha",
            "window_index": 0,
            "window_start_tick": 0,
            "window_end_tick": 1,
            "graph_ref": "graph:warehouse-case",
            "graph_revision": "graph:warehouse-case@1",
            "node_ref": "node:start",
            "target_refs": ("room:hall",),
            "expected_revision_vector": {SOURCE_STREAM: 1},
            "local_position_sample": (0.0, 0.0, 0.0),
            "facing_sample": (0.0, 0.0, 1.0),
            "visibility_sample": {"visible": True},
            "sound_sample": {"heard": False},
            "contact_sample": {"in_contact": False},
            "navigation_revision": "nav:warehouse@1",
            "collision_revision": "collision:warehouse@1",
            "occlusion_revision": "occlusion:warehouse@1",
            "sound_zone_revision": "sound:warehouse@1",
            "deterministic_seed": "seed:warehouse:1",
            "evidence_refs": ("evidence:window:1",),
        }
    )


def _snapshot() -> SpatialSnapshotRef:
    return SpatialSnapshotRef(
        snapshot_ref="snapshot:warehouse@1",
        navigation_revision="nav:warehouse@1",
        collision_revision="collision:warehouse@1",
        occlusion_revision="occlusion:warehouse@1",
        sound_zone_revision="sound:warehouse@1",
        source_revision_vector={SOURCE_STREAM: 1},
        visibility_by_target={"room:hall": True},
        sound_by_target={"room:hall": False},
        contact_by_target={"room:hall": False},
        distance_band_by_target={"room:hall": "near"},
    )


def _command() -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id="command:action-window:1",
        command_type="gameplay.conflict.resolve_action_window",
        command_version=1,
        principal_ref="authority:p5:investigation-conflict",
        actor_ref="character:survivor:alpha",
        project_ref="project:action-window",
        transaction_id="transaction:action-window:1",
        idempotency_key="idempotency:action-window:1",
        expected_revisions={EVENT_STREAM: 0},
        read_set_revisions={SOURCE_STREAM: 1},
        causation_id="causation:action-window:1",
        correlation_id="correlation:action-window:1",
        source_ref="source:action-window:1",
        submitted_at="2026-09-05T00:00:00Z",
        pinned_revisions={},
        payload={},
    )


def _seed_source(store: GameplayEventStore) -> None:
    result = store.append_batch(
        build_atomic_event_batch(
            command_id="source:action-window:1",
            principal_ref="authority:source-fixture",
            stream_id=SOURCE_STREAM,
            expected_revision=0,
            event_specs=(("world.encounter.snapshot_committed", {"actor_ref": "character:survivor:alpha", "visibility_policy": "project"}),),
            idempotency_key="source:action-window:1",
            causation_id="source:action-window:1",
            correlation_id="encounter:bakery-theft",
        )
    )
    assert result.committed


def test_action_window_facade_commits_the_small_conflict_surface() -> None:
    store = GameplayEventStore()
    _seed_source(store)
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)

    result = authority.resolve_action_window(
        command=_command(),
        intent=_intent(),
        graph=_graph(),
        spatial_snapshot=_snapshot(),
        role_ref=ROLE_REF,
        now="2026-09-05T00:00:00Z",
    )

    assert result.window_result.accepted is True
    assert result.receipt is not None and result.receipt.committed is True
    assert [event.event_type for event in authority._store.read_events() if event.event_type in EVENT_TYPES] == list(EVENT_TYPES)


def test_action_window_duplicate_replays_without_new_write() -> None:
    store = GameplayEventStore()
    _seed_source(store)
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    first = authority.resolve_action_window(
        command=_command(),
        intent=_intent(),
        graph=_graph(),
        spatial_snapshot=_snapshot(),
        role_ref=ROLE_REF,
        now="2026-09-05T00:00:00Z",
    )
    second = authority.resolve_action_window(
        command=_command(),
        intent=_intent(),
        graph=_graph(),
        spatial_snapshot=_snapshot(),
        role_ref=ROLE_REF,
        now="2026-09-05T00:00:00Z",
    )

    assert first.committed is True
    assert second.committed is True
    assert second.idempotency_status == "duplicate_replayed"
    assert len([event for event in store.read_events() if event.event_type in EVENT_TYPES]) == 5


def test_action_window_changed_duplicate_is_zero_write() -> None:
    store = GameplayEventStore()
    _seed_source(store)
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    first = authority.resolve_action_window(
        command=_command(),
        intent=_intent(),
        graph=_graph(),
        spatial_snapshot=_snapshot(),
        role_ref=ROLE_REF,
        now="2026-09-05T00:00:00Z",
    )
    changed_intent = _intent().model_copy(update={"deterministic_seed": "seed:changed"}, deep=True)
    changed = authority.resolve_action_window(
        command=_command(),
        intent=changed_intent,
        graph=_graph(),
        spatial_snapshot=_snapshot(),
        role_ref=ROLE_REF,
        now="2026-09-05T00:00:00Z",
    )

    assert first.committed is True
    assert changed.committed is False
    assert changed.error_code == "action_window_idempotency_reused"
    assert len([event for event in store.read_events() if event.event_type in EVENT_TYPES]) == 5


def test_action_window_role_scope_and_source_revision_reject_without_partial_append() -> None:
    store = GameplayEventStore()
    _seed_source(store)
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    before = len(store.read_events())
    rejected_role = authority.resolve_action_window(
        command=_command(),
        intent=_intent(),
        graph=_graph(),
        spatial_snapshot=_snapshot(),
        role_ref="role:witness@1",
        now="2026-09-05T00:00:00Z",
    )
    rejected_revision = authority.resolve_action_window(
        command=_command().model_copy(update={"read_set_revisions": {SOURCE_STREAM: 2}}, deep=True),
        intent=_intent(),
        graph=_graph(),
        spatial_snapshot=_snapshot(),
        role_ref=ROLE_REF,
        now="2026-09-05T00:00:00Z",
    )

    assert rejected_role.committed is False
    assert rejected_role.error_code == "action_window_role_invalid"
    assert rejected_revision.committed is False
    assert rejected_revision.error_code == "action_window_source_revision_stale"
    assert len(store.read_events()) == before


def test_action_window_facade_rejects_changed_duplicate_and_private_evidence() -> None:
    store = GameplayEventStore()
    _seed_source(store)
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    intent = _intent()
    first = authority.resolve_action_window(
        command=_command(), intent=intent, graph=_graph(), spatial_snapshot=_snapshot(), role_ref=ROLE_REF, now="now"
    )
    assert first.committed
    changed = authority.resolve_action_window(
        command=_command(),
        intent=intent.model_copy(update={"deterministic_seed": "seed:changed"}),
        graph=_graph(),
        spatial_snapshot=_snapshot(),
        role_ref=ROLE_REF,
        now="now",
    )
    assert not changed.committed
    assert changed.error_code == "action_window_idempotency_reused"
    assert len([event for event in store.read_events() if event.event_type in EVENT_TYPES]) == 5

    private_intent = intent.model_copy(
        update={
            "window_index": 1,
            "window_start_tick": 1,
            "window_end_tick": 2,
            "visibility_sample": {"visible": True, "scope": "actor:other"},
        }
    )
    private = authority.resolve_action_window(
        command=_command().model_copy(update={"idempotency_key": "idempotency:private", "expected_revisions": {EVENT_STREAM: 5}}),
        intent=private_intent,
        graph=_graph(),
        spatial_snapshot=_snapshot(),
        role_ref=ROLE_REF,
        now="now",
    )
    assert not private.committed
    assert private.error_code == "action_window_private_evidence_leaked"
    assert len(store.read_events()) == 6
