from __future__ import annotations

import json
from hashlib import sha256

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import OwnerAuthorizedFragment, ProjectionCheckpoint, ReplayResult
from app.gameplay.p5.contracts import (
    P5ResolutionRequest,
    P5RevisionVector,
    P5SchemaPin,
    QuestObjectiveDefinition,
    QuestPackageDefinition,
    build_directed_relationship_ref,
)
from app.gameplay.p5.registry import (
    OwnerAdapterAllowance,
    P5EventCatalogEntry,
    P5EventNamespace,
    P5PolicyRegistry,
    P5StreamGrammar,
    TrustedEvidenceProvider,
)
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _load_authority():
    try:
        from app.gameplay.p5.investigation_conflict import InvestigationConflictAuthority
    except Exception as exc:  # pragma: no cover - explicit RED guard
        pytest.fail(f"production break: investigation conflict authority module missing: {exc}")
    return InvestigationConflictAuthority


def _digest(hex_digit: str) -> str:
    return f"sha256:{hex_digit * 64}"


def _canonical_sha256_digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _snapshot_hash(store: GameplayEventStore) -> str:
    return _canonical_sha256_digest(store.export_snapshot())


REGISTRY_REF = "registry:p5:investigation-conflict"
REGISTRY_REVISION = "registry:p5:investigation-conflict:v1"
PACKAGE_REF = "package:p5:investigation-conflict"
PACKAGE_REVISION = "package:p5:investigation-conflict:v1"
RULESET_REVISION = "ruleset:p5c:v1"
CASE_REF = "case:bakery-theft"
ATTEMPT_REF = "attempt:bakery-theft:1"
INVESTIGATION_STREAM = "gameplay:investigation:bakery-theft"
CONFLICT_STREAM = "gameplay:conflict:attempt-1"
ALARM_STREAM = "gameplay:conflict:alarm-1"
STATUS_STREAM = "gameplay:status:alerted"
RELATIONSHIP_REF = build_directed_relationship_ref(
    source_ref="character:guard:alpha",
    relation_kind="suspects",
    target_ref="character:thief:beta",
)
KNOWLEDGE_STREAM = "gameplay:knowledge:clue-hidden"


def _registry() -> P5PolicyRegistry:
    objective = QuestObjectiveDefinition(
        objective_ref="objective:p5c:bakery-theft",
        prerequisite_fact_refs=("fact:p5c:case-open",),
        accepted_evidence_kind_refs=("evidence:observation",),
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
                provider_ref="provider:evidence:p5c",
                provider_revision="provider:evidence:p5c:v1",
                provider_digest=_digest("1"),
                allowed_evidence_kinds=("evidence:observation", "evidence:threat", "evidence:alarm"),
            ),
        ),
        owner_adapter_allowlist=(
            OwnerAdapterAllowance(
                owner_ref="owner:investigation-authority",
                allowed_event_names=(
                    "gameplay.investigation.observation_resolved",
                    "gameplay.conflict.attempt_resolved",
                    "gameplay.conflict.alarm_raised",
                    "gameplay.status_tag.applied",
                ),
                allowed_stream_grammar_refs=(
                    "grammar:p5:investigation",
                    "grammar:p5:conflict",
                    "grammar:p5:status",
                ),
            ),
        ),
        quest_packages=(package,),
        ruleset_revisions=(RULESET_REVISION,),
        schema_pins=(
            P5SchemaPin(schema_ref="schema:p5:investigation:observation-resolved", schema_version=1, schema_digest=_digest("4")),
            P5SchemaPin(schema_ref="schema:p5:conflict:attempt-resolved", schema_version=1, schema_digest=_digest("5")),
            P5SchemaPin(schema_ref="schema:p5:conflict:alarm-raised", schema_version=1, schema_digest=_digest("6")),
            P5SchemaPin(schema_ref="schema:p5:status:tag-applied", schema_version=1, schema_digest=_digest("7")),
        ),
        event_namespaces=(
            P5EventNamespace(
                namespace_ref="namespace:p5:investigation",
                event_name_prefix="gameplay.investigation.",
                allowed_event_names=("gameplay.investigation.observation_resolved",),
            ),
            P5EventNamespace(
                namespace_ref="namespace:p5:conflict",
                event_name_prefix="gameplay.conflict.",
                allowed_event_names=("gameplay.conflict.attempt_resolved", "gameplay.conflict.alarm_raised"),
            ),
            P5EventNamespace(
                namespace_ref="namespace:p5:status",
                event_name_prefix="gameplay.status_tag.",
                allowed_event_names=("gameplay.status_tag.applied",),
            ),
        ),
        event_catalog=(
            P5EventCatalogEntry(
                event_name="gameplay.investigation.observation_resolved",
                namespace_ref="namespace:p5:investigation",
                schema_ref="schema:p5:investigation:observation-resolved",
                schema_version=1,
                stream_grammar_ref="grammar:p5:investigation",
            ),
            P5EventCatalogEntry(
                event_name="gameplay.conflict.attempt_resolved",
                namespace_ref="namespace:p5:conflict",
                schema_ref="schema:p5:conflict:attempt-resolved",
                schema_version=1,
                stream_grammar_ref="grammar:p5:conflict",
            ),
            P5EventCatalogEntry(
                event_name="gameplay.conflict.alarm_raised",
                namespace_ref="namespace:p5:conflict",
                schema_ref="schema:p5:conflict:alarm-raised",
                schema_version=1,
                stream_grammar_ref="grammar:p5:conflict",
            ),
            P5EventCatalogEntry(
                event_name="gameplay.status_tag.applied",
                namespace_ref="namespace:p5:status",
                schema_ref="schema:p5:status:tag-applied",
                schema_version=1,
                stream_grammar_ref="grammar:p5:status",
            ),
        ),
        stream_grammars=(
            P5StreamGrammar(grammar_ref="grammar:p5:investigation", pattern=r"^gameplay:investigation:[^:]+$"),
            P5StreamGrammar(grammar_ref="grammar:p5:conflict", pattern=r"^gameplay:conflict:[^:]+$"),
            P5StreamGrammar(grammar_ref="grammar:p5:status", pattern=r"^gameplay:status:[^:]+$"),
            P5StreamGrammar(grammar_ref="grammar:p5:relationship", pattern=r"^gameplay:relationship:[0-9a-f]{64}$"),
            P5StreamGrammar(grammar_ref="grammar:p5:knowledge", pattern=r"^gameplay:knowledge:[^:]+$"),
        ),
    )


def _status_fragment(*, stream_ref: str = STATUS_STREAM) -> OwnerAuthorizedFragment:
    return OwnerAuthorizedFragment.model_validate(
        {
            "fragment_id": "fragment:p5c:status:alerted",
            "owner_principal_ref": "owner:investigation-authority",
            "source_rule_ref": "rule:p5c:alerted",
            "expected_revisions": {stream_ref: 0},
            "read_set_revisions": {CONFLICT_STREAM: 0, RELATIONSHIP_REF: 0},
            "event_specs": {
                stream_ref: (
                    (
                        "gameplay.status_tag.applied",
                        {
                            "status_tag_ref": "status:alerted",
                            "status_kind": "nonlethal",
                            "result_ref": "result:p5c:alerted",
                        },
                    ),
                )
            },
            "event_visibility_policies": {stream_ref: ("authority_only",)},
            "pinned_revisions": {"schema:p5:status:tag-applied": 1},
        }
    )


def _status_fragment_without_visibility(*, stream_ref: str = STATUS_STREAM) -> OwnerAuthorizedFragment:
    return OwnerAuthorizedFragment.model_validate(
        {
            "fragment_id": "fragment:p5c:status:no-visibility",
            "owner_principal_ref": "owner:investigation-authority",
            "source_rule_ref": "rule:p5c:alerted",
            "expected_revisions": {stream_ref: 0},
            "read_set_revisions": {CONFLICT_STREAM: 0, RELATIONSHIP_REF: 0},
            "event_specs": {
                stream_ref: (
                    (
                        "gameplay.status_tag.applied",
                        {
                            "status_tag_ref": "status:alerted",
                            "status_kind": "nonlethal",
                            "result_ref": "result:p5c:alerted",
                        },
                    ),
                )
            },
            "pinned_revisions": {"schema:p5:status:tag-applied": 1},
        }
    )


def _status_fragment_with_visibility(
    visibility: str,
    *,
    stream_ref: str = STATUS_STREAM,
) -> OwnerAuthorizedFragment:
    return OwnerAuthorizedFragment.model_validate(
        {
            "fragment_id": f"fragment:p5c:status:{visibility.replace(':', '-')}",
            "owner_principal_ref": "owner:investigation-authority",
            "source_rule_ref": "rule:p5c:alerted",
            "expected_revisions": {stream_ref: 0},
            "read_set_revisions": {CONFLICT_STREAM: 0, RELATIONSHIP_REF: 0},
            "event_specs": {
                stream_ref: (
                    (
                        "gameplay.status_tag.applied",
                        {
                            "status_tag_ref": "status:alerted",
                            "status_kind": "nonlethal",
                            "result_ref": "result:p5c:alerted",
                        },
                    ),
                )
            },
            "event_visibility_policies": {stream_ref: (visibility,)},
            "pinned_revisions": {"schema:p5:status:tag-applied": 1},
        }
    )


def _command(
    *,
    request_id: str = "request:p5c:1",
    perception_visibility: str = "public",
    affordance_ref: str = "affordance:investigate",
    skill_ref: str = "skill:observe",
    resistance_ref: str = "resistance:guard-alert",
    status_revision_ref: str = "status:alerted",
    alarm_ref: str = "alarm:bakery",
    hidden_clue_ref: str = "fact:clue:bread-knife",
    payload_updates: dict[str, object] | None = None,
) -> GameplayCommandEnvelope:
    payload: dict[str, object] = {
        "case_ref": CASE_REF,
        "attempt_ref": ATTEMPT_REF,
        "actor_ref": "character:investigator:alpha",
        "target_ref": "character:guard:alpha",
        "relationship_ref": RELATIONSHIP_REF,
        "perception_visibility": perception_visibility,
        "perception_ref": "perception:visible-clue" if perception_visibility == "public" else "perception:hidden-clue",
        "hidden_clue_ref": hidden_clue_ref,
        "affordance_ref": affordance_ref,
        "skill_ref": skill_ref,
        "resistance_ref": resistance_ref,
        "status_revision_ref": status_revision_ref,
        "alarm_ref": alarm_ref,
        "investigation_stream_ref": INVESTIGATION_STREAM,
        "conflict_stream_ref": CONFLICT_STREAM,
        "alarm_stream_ref": ALARM_STREAM,
        "knowledge_stream_ref": KNOWLEDGE_STREAM,
    }
    if payload_updates:
        payload.update(payload_updates)
    return GameplayCommandEnvelope.model_validate(
        {
            "command_id": f"command:{request_id}",
            "command_type": "gameplay.investigation.resolve_conflict",
            "command_version": 1,
            "principal_ref": "principal:p5c",
            "actor_ref": "character:investigator:alpha",
            "project_ref": "project:p5",
            "transaction_id": f"tx:{request_id}",
            "idempotency_key": f"idempotency:{request_id}",
            "expected_revisions": {
                INVESTIGATION_STREAM: 0,
                CONFLICT_STREAM: 0,
                ALARM_STREAM: 0,
                STATUS_STREAM: 0,
            },
            "read_set_revisions": {
                INVESTIGATION_STREAM: 0,
                CONFLICT_STREAM: 0,
                ALARM_STREAM: 0,
                STATUS_STREAM: 0,
                RELATIONSHIP_REF: 0,
                KNOWLEDGE_STREAM: 0,
            },
            "causation_id": f"cause:{request_id}",
            "correlation_id": f"corr:{request_id}",
            "source_ref": "source:godot",
            "submitted_at": "2026-08-11T00:00:00Z",
            "pinned_revisions": {
                "schema:p5:investigation:observation-resolved": 1,
                "schema:p5:conflict:attempt-resolved": 1,
                "schema:p5:conflict:alarm-raised": 1,
                "schema:p5:status:tag-applied": 1,
            },
            "payload": payload,
        }
    )


def _request(
    registry: P5PolicyRegistry,
    *,
    request_id: str = "request:p5c:1",
    perception_visibility: str = "public",
    affordance_ref: str = "affordance:investigate",
    skill_ref: str = "skill:observe",
    resistance_ref: str = "resistance:guard-alert",
    status_revision_ref: str = "status:alerted",
    alarm_ref: str = "alarm:bakery",
    proposed_events: tuple[dict[str, object], ...] | None = None,
    request_updates: dict[str, object] | None = None,
) -> P5ResolutionRequest:
    payload: dict[str, object] = {
        "request_ref": request_id,
        "registry_ref": registry.registry_ref,
        "registry_revision": registry.registry_revision,
        "registry_digest": registry.registry_digest,
        "package_ref": PACKAGE_REF,
        "package_revision": PACKAGE_REVISION,
        "ruleset_revision": RULESET_REVISION,
        "evidence_provider_ref": "provider:evidence:p5c",
        "owner_adapter_ref": "owner:investigation-authority",
        "provenance_source_ref": "source:evidence:casefile",
        "subject_scope_ref": "character:investigator:alpha",
        "expected_revisions": P5RevisionVector(
            entries={
                INVESTIGATION_STREAM: 0,
                CONFLICT_STREAM: 0,
                ALARM_STREAM: 0,
                STATUS_STREAM: 0,
            }
        ),
        "read_set_revisions": P5RevisionVector(
            entries={
                INVESTIGATION_STREAM: 0,
                CONFLICT_STREAM: 0,
                ALARM_STREAM: 0,
                STATUS_STREAM: 0,
                RELATIONSHIP_REF: 0,
                KNOWLEDGE_STREAM: 0,
            }
        ),
        "required_schema_pins": (
            P5SchemaPin(schema_ref="schema:p5:investigation:observation-resolved", schema_version=1, schema_digest=_digest("4")),
            P5SchemaPin(schema_ref="schema:p5:conflict:attempt-resolved", schema_version=1, schema_digest=_digest("5")),
            P5SchemaPin(schema_ref="schema:p5:conflict:alarm-raised", schema_version=1, schema_digest=_digest("6")),
            P5SchemaPin(schema_ref="schema:p5:status:tag-applied", schema_version=1, schema_digest=_digest("7")),
        ),
        "relationship_ref": RELATIONSHIP_REF,
        "proposed_events": proposed_events
            or (
                {
                    "event_name": "gameplay.investigation.observation_resolved",
                    "schema_version": 1,
                    "stream_ref": INVESTIGATION_STREAM,
                    "visibility": "public" if perception_visibility == "public" else "actor:character:investigator:alpha",
                },
            {
                "event_name": "gameplay.conflict.attempt_resolved",
                "schema_version": 1,
                "stream_ref": CONFLICT_STREAM,
                "visibility": "authority_only",
            },
            {
                "event_name": "gameplay.conflict.alarm_raised",
                "schema_version": 1,
                "stream_ref": ALARM_STREAM,
                "visibility": "authority_only",
            },
        ),
    }
    if request_updates:
        payload.update(request_updates)
    return P5ResolutionRequest.model_validate(payload)


def _view_hash(view: object) -> str:
    return _canonical_sha256_digest(view)


def test_import_guard_loads_investigation_conflict_authority() -> None:
    authority_type = _load_authority()
    assert authority_type.__name__ == "InvestigationConflictAuthority"


def test_visible_perception_commits_the_investigation_resolution() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    result = authority.resolve(command=_command(), request=_request(registry), now="2026-08-11T00:00:00Z")
    assert result.resolution.result_kind == "committed_success"


def test_hidden_perception_is_rejected_without_writes() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    result = authority.resolve(
        command=_command(perception_visibility="hidden"),
        request=_request(registry, perception_visibility="hidden"),
        now="2026-08-11T00:00:00Z",
    )
    assert result.resolution.result_kind == "rejected_zero_write"


def test_affordance_and_skill_gate_rejects_unauthorized_resolution() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    result = authority.resolve(
        command=_command(affordance_ref="affordance:lockpick", skill_ref="skill:unknown"),
        request=_request(registry, affordance_ref="affordance:lockpick", skill_ref="skill:unknown"),
        now="2026-08-11T00:00:00Z",
    )
    assert result.resolution.result_kind == "rejected_zero_write"


def test_resistance_commits_a_nonlethal_adverse_outcome() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    result = authority.resolve(
        command=_command(resistance_ref="resistance:guard-alert"),
        request=_request(registry, resistance_ref="resistance:guard-alert"),
        owner_fragments=(_status_fragment(),),
        now="2026-08-11T00:00:00Z",
    )
    assert result.resolution.result_kind == "committed_adverse_outcome"


def test_status_revision_commits_the_alerted_state_change() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    result = authority.resolve(
        command=_command(status_revision_ref="status:alerted"),
        request=_request(registry, status_revision_ref="status:alerted"),
        owner_fragments=(_status_fragment(),),
        now="2026-08-11T00:00:00Z",
    )
    assert result.resolution.result_kind == "committed_adverse_outcome"


def test_alarm_commits_an_alarm_raised_event() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    result = authority.resolve(
        command=_command(alarm_ref="alarm:bakery"),
        request=_request(registry, alarm_ref="alarm:bakery"),
        owner_fragments=(_status_fragment(),),
        now="2026-08-11T00:00:00Z",
    )
    assert result.resolution.result_kind == "committed_adverse_outcome"


def test_registered_nonlethal_owner_fragment_is_accepted() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    result = authority.resolve(
        command=_command(),
        request=_request(registry),
        owner_fragments=(_status_fragment(),),
        now="2026-08-11T00:00:00Z",
    )
    assert result.receipt is not None


def test_owner_fragment_without_explicit_visibility_is_rejected_without_writes() -> None:
    authority_type = _load_authority()
    registry = _registry()
    store = GameplayEventStore()
    authority = authority_type(registry=registry, store=store)
    before = _snapshot_hash(store)
    result = authority.resolve(
        command=_command(),
        request=_request(registry),
        owner_fragments=(_status_fragment_without_visibility(),),
        now="2026-08-11T00:00:00Z",
    )
    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.receipt is None
    assert _snapshot_hash(store) == before


@pytest.mark.parametrize("visibility", ("project", "invalid"))
def test_owner_fragment_with_invalid_or_project_visibility_is_rejected_without_writes(visibility: str) -> None:
    authority_type = _load_authority()
    registry = _registry()
    store = GameplayEventStore()
    authority = authority_type(registry=registry, store=store)
    before = _snapshot_hash(store)
    result = authority.resolve(
        command=_command(),
        request=_request(registry),
        owner_fragments=(_status_fragment_with_visibility(visibility),),
        now="2026-08-11T00:00:00Z",
    )
    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.receipt is None
    assert _snapshot_hash(store) == before


def test_structured_zero_write_rejects_malformed_investigation_input() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    result = authority.resolve(
        command=_command(payload_updates={"hidden_clue_ref": ""}),
        request=_request(registry, request_updates={"subject_scope_ref": "character:outsider"}),
        now="2026-08-11T00:00:00Z",
    )
    assert result.resolution.result_kind == "rejected_zero_write"


def test_atomicity_rejects_partial_batched_investigation_writes() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    request = _request(
        registry,
        proposed_events=(
            {
                "event_name": "gameplay.investigation.observation_resolved",
                "schema_version": 1,
                "stream_ref": INVESTIGATION_STREAM,
                "visibility": "public",
            },
            {
                "event_name": "gameplay.conflict.attempt_resolved",
                "schema_version": 1,
                "stream_ref": CONFLICT_STREAM,
                "visibility": "authority_only",
            },
        ),
    )
    result = authority.resolve(
        command=_command(payload_updates={"skill_ref": "skill:unknown"}),
        request=request,
        now="2026-08-11T00:00:00Z",
    )
    assert result.resolution.result_kind == "rejected_zero_write"


def test_idempotency_replays_the_original_investigation_result() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    command = _command(request_id="request:p5c:idempotent")
    request = _request(registry, request_id="request:p5c:idempotent")
    first = authority.resolve(command=command, request=request, now="2026-08-11T00:00:00Z")
    second = authority.resolve(command=command, request=request, now="2026-08-11T00:00:00Z")
    assert first.receipt is not None and second.receipt is not None


def test_privacy_redacts_hidden_clue_from_public_view() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    authority.resolve(command=_command(), request=_request(registry), now="2026-08-11T00:00:00Z")
    public_view = authority.view_for(recipient_ref="character:outsider", now="2026-08-11T00:00:00Z")
    private_view = authority.view_for(recipient_ref="character:investigator:alpha", now="2026-08-11T00:00:00Z")
    authority_view = authority.view_for(recipient_ref="authority:auditor", now="2026-08-11T00:00:00Z")
    assert "hidden_evidence" not in public_view["investigations"][0]
    assert "hidden_clue_ref" not in public_view["investigations"][0]
    assert authority_view["investigations"][0]["hidden_evidence"] == "fact:clue:bread-knife"
    assert _view_hash(public_view) != _view_hash(private_view)


def test_checkpoint_tail_replay_advances_from_valid_prefix_and_matches_full_replay() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    first = authority.resolve(command=_command(), request=_request(registry), now="2026-08-11T00:00:00Z")
    assert first.receipt is not None and first.receipt.committed

    prefix = authority.replay_full(now="2026-08-11T00:00:00Z")
    checkpoint = ProjectionCheckpoint(
        checkpoint_id="checkpoint:p5c:1",
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
        INVESTIGATION_STREAM: 1,
        CONFLICT_STREAM: 1,
        ALARM_STREAM: 0,
        STATUS_STREAM: 0,
    }
    command_two = _command(request_id="request:p5c:tail").model_copy(
        update={
            "expected_revisions": revisions_two,
            "read_set_revisions": {
                INVESTIGATION_STREAM: 1,
                CONFLICT_STREAM: 1,
                ALARM_STREAM: 0,
                STATUS_STREAM: 0,
                RELATIONSHIP_REF: 0,
                KNOWLEDGE_STREAM: 0,
            },
        },
        deep=True,
    )
    request_two = _request(registry, request_id="request:p5c:tail").model_copy(
        update={
            "expected_revisions": P5RevisionVector(entries=revisions_two),
            "read_set_revisions": P5RevisionVector(
                entries={
                    INVESTIGATION_STREAM: 1,
                    CONFLICT_STREAM: 1,
                    ALARM_STREAM: 0,
                    STATUS_STREAM: 0,
                    RELATIONSHIP_REF: 0,
                    KNOWLEDGE_STREAM: 0,
                }
            ),
        },
        deep=True,
    )
    second = authority.resolve(command=command_two, request=request_two, now="2026-08-11T01:00:00Z")
    assert second.receipt is not None and second.receipt.committed

    full = authority.replay_full(now="2026-08-11T00:00:00Z")
    tail = authority.replay_checkpoint_tail(checkpoint=checkpoint, now="2026-08-11T00:00:00Z")
    assert isinstance(full, ReplayResult)
    assert isinstance(tail, ReplayResult)
    assert tail.succeeded is True
    assert tail.last_global_sequence > checkpoint.last_global_sequence
    assert tail.state != checkpoint.state
    assert tail.source_revision_vector != checkpoint.source_revision_vector
    assert tail.applied_event_ids != list(checkpoint.applied_event_ids)
    assert tail.state == full.state
    assert "hidden_evidence" not in full.state["investigations"][0]
    assert "hidden_evidence" not in tail.state["investigations"][0]
    assert full.projection_hash == tail.projection_hash


def test_checkpoint_tail_rejects_bogus_checkpoint_instead_of_silently_replaying_full() -> None:
    authority_type = _load_authority()
    registry = _registry()
    authority = authority_type(registry=registry, store=GameplayEventStore())
    committed = authority.resolve(command=_command(), request=_request(registry), now="2026-08-11T00:00:00Z")
    assert committed.receipt is not None and committed.receipt.committed

    bogus = ProjectionCheckpoint(
        checkpoint_id="checkpoint:p5c:bogus",
        projector_id="projector:p5:investigation-conflict",
        projector_version="v1",
        projection_schema_version=1,
        source_revision_vector={INVESTIGATION_STREAM: 999},
        last_global_sequence=1,
        state={"investigations": (), "conflicts": (), "consequences": (), "source_revision_vector": {}},
        applied_event_ids=("event:bogus",),
        projection_hash=_digest("9"),
        active_patch_set_revision="patch:p5c:v1",
        registry_revision=registry.registry_revision,
        world_config_revision="world:p5c:v1",
    )
    replay = authority.replay_checkpoint_tail(checkpoint=bogus, now="2026-08-11T00:00:00Z")
    assert replay.succeeded is False
    assert replay.failure is not None
    assert replay.failure.error_code == "p5_checkpoint_mismatch"
