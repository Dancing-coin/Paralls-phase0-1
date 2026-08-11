from __future__ import annotations

import json
from hashlib import sha256

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import OwnerAuthorizedFragment
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
        from app.gameplay.p5.quest_evidence import QuestEvidenceAuthority
    except Exception as exc:  # pragma: no cover - explicit RED guard
        pytest.fail(f"production break: quest evidence authority module missing: {exc}")
    return QuestEvidenceAuthority


def _digest(hex_digit: str) -> str:
    return f"sha256:{hex_digit * 64}"


def _snapshot_hash(store: GameplayEventStore) -> str:
    payload = json.dumps(store.export_snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()


def _default_evidence_ref(request_id: str) -> str:
    return f"evidence:{request_id}"


def _evidence_stream_ref(evidence_ref: str) -> str:
    return f"gameplay:evidence:{evidence_ref}"


def _quest_stream_ref(quest_instance_ref: str) -> str:
    return f"gameplay:quest:{quest_instance_ref}"


def _registry() -> P5PolicyRegistry:
    objective = QuestObjectiveDefinition(
        objective_ref="objective:quest:ledger",
        prerequisite_fact_refs=("fact:case:open",),
        accepted_evidence_kind_refs=("evidence:receipt",),
        visibility="authority_only",
        expiry_policy_ref="expiry:never",
    )
    package = QuestPackageDefinition(
        package_ref="package:quest:ledger",
        package_revision="package:quest:ledger:v1",
        package_digest=_digest("3"),
        ruleset_revision="ruleset:p5:v1",
        objectives=(objective,),
    )
    return P5PolicyRegistry.build(
        registry_ref="registry:p5",
        registry_revision="registry:p5:v1",
        trusted_evidence_providers=(
            TrustedEvidenceProvider(
                provider_ref="provider:evidence:ledger",
                provider_revision="provider:evidence:ledger:v1",
                provider_digest=_digest("1"),
                allowed_evidence_kinds=("evidence:receipt",),
            ),
        ),
        owner_adapter_allowlist=(
            OwnerAdapterAllowance(
                owner_ref="owner:quest-authority",
                allowed_event_names=(
                    "gameplay.quest.evidence_registered",
                    "gameplay.quest.objective_transitioned",
                ),
                allowed_stream_grammar_refs=("grammar:p5:evidence", "grammar:p5:quest"),
            ),
        ),
        quest_packages=(package,),
        ruleset_revisions=("ruleset:p5:v1",),
        schema_pins=(
            P5SchemaPin(
                schema_ref="schema:p5:quest:evidence-registered",
                schema_version=1,
                schema_digest=_digest("4"),
            ),
            P5SchemaPin(
                schema_ref="schema:p5:quest:objective-transitioned",
                schema_version=1,
                schema_digest=_digest("5"),
            ),
        ),
        event_namespaces=(
            P5EventNamespace(
                namespace_ref="namespace:p5:quest",
                event_name_prefix="gameplay.quest.",
                allowed_event_names=(
                    "gameplay.quest.evidence_registered",
                    "gameplay.quest.objective_transitioned",
                ),
            ),
        ),
        event_catalog=(
            P5EventCatalogEntry(
                event_name="gameplay.quest.evidence_registered",
                namespace_ref="namespace:p5:quest",
                schema_ref="schema:p5:quest:evidence-registered",
                schema_version=1,
                stream_grammar_ref="grammar:p5:evidence",
            ),
            P5EventCatalogEntry(
                event_name="gameplay.quest.objective_transitioned",
                namespace_ref="namespace:p5:quest",
                schema_ref="schema:p5:quest:objective-transitioned",
                schema_version=1,
                stream_grammar_ref="grammar:p5:quest",
            ),
        ),
        stream_grammars=(
            P5StreamGrammar(grammar_ref="grammar:p5:evidence", pattern=r"^gameplay:evidence:.+$"),
            P5StreamGrammar(grammar_ref="grammar:p5:quest", pattern=r"^gameplay:quest:.+$"),
        ),
    )


def _command(
    *,
    request_id: str = "request:p5:quest-evidence:1",
    expected_revision: int = 0,
    read_revision: int = 0,
    evidence_ref: str | None = None,
    quest_instance_ref: str = "quest-instance-1",
    payload_updates: dict[str, object] | None = None,
) -> GameplayCommandEnvelope:
    evidence_ref = evidence_ref or _default_evidence_ref(request_id)
    evidence_stream_ref = _evidence_stream_ref(evidence_ref)
    quest_stream_ref = _quest_stream_ref(quest_instance_ref)
    payload: dict[str, object] = {
        "objective_ref": "objective:quest:ledger",
        "evidence_ref": evidence_ref,
        "evidence_kind_ref": "evidence:receipt",
        "evidence_stream_ref": evidence_stream_ref,
        "quest_instance_ref": quest_instance_ref,
        "quest_stream_ref": quest_stream_ref,
        "subject_ref": "actor:investigator",
        "provider_ref": "provider:evidence:ledger",
        "provenance_source_ref": "source:evidence:ledger-1",
        "visibility": "authority_only",
        "transition_ref": "transition:quest:evidence_registered",
        "satisfied_prerequisite_fact_refs": ("fact:case:open",),
        "package_ref": "package:quest:ledger",
        "package_revision": "package:quest:ledger:v1",
        "package_digest": _digest("3"),
        "expires_at": None,
        "observed_at": "2026-08-11T00:00:00Z",
    }
    if payload_updates:
        payload.update(payload_updates)
    return GameplayCommandEnvelope.model_validate(
        {
            "command_id": f"command:{request_id}",
            "command_type": "gameplay.quest.register_evidence",
            "command_version": 1,
            "principal_ref": "principal:p5",
            "actor_ref": "actor:investigator",
            "project_ref": "project:p5",
            "transaction_id": f"tx:{request_id}",
            "idempotency_key": f"idempotency:{request_id}",
            "expected_revisions": {
                evidence_stream_ref: expected_revision,
                quest_stream_ref: expected_revision,
            },
            "read_set_revisions": {
                evidence_stream_ref: read_revision,
                quest_stream_ref: read_revision,
            },
            "causation_id": f"cause:{request_id}",
            "correlation_id": f"corr:{request_id}",
            "source_ref": "source:godot",
            "submitted_at": "2026-08-11T00:00:00Z",
            "pinned_revisions": {
                "schema:p5:quest:evidence-registered": 1,
                "schema:p5:quest:objective-transitioned": 1,
            },
            "payload": payload,
        }
    )


def _request(
    registry: P5PolicyRegistry,
    *,
    request_id: str = "request:p5:quest-evidence:1",
    expected_revision: int = 0,
    read_revision: int = 0,
    evidence_ref: str | None = None,
    quest_instance_ref: str = "quest-instance-1",
    request_updates: dict[str, object] | None = None,
) -> P5ResolutionRequest:
    evidence_ref = evidence_ref or _default_evidence_ref(request_id)
    evidence_stream_ref = _evidence_stream_ref(evidence_ref)
    quest_stream_ref = _quest_stream_ref(quest_instance_ref)
    relationship_ref = build_directed_relationship_ref(
        source_ref="actor:investigator",
        relation_kind="investigates",
        target_ref="quest:ledger",
    )
    payload: dict[str, object] = {
        "request_ref": request_id,
        "registry_ref": registry.registry_ref,
        "registry_revision": registry.registry_revision,
        "registry_digest": registry.registry_digest,
        "package_ref": "package:quest:ledger",
        "package_revision": "package:quest:ledger:v1",
        "ruleset_revision": "ruleset:p5:v1",
        "evidence_provider_ref": "provider:evidence:ledger",
        "owner_adapter_ref": "owner:quest-authority",
        "provenance_source_ref": "source:evidence:ledger-1",
        "subject_scope_ref": "actor:investigator",
        "expected_revisions": P5RevisionVector(
            entries={
                evidence_stream_ref: expected_revision,
                quest_stream_ref: expected_revision,
            }
        ),
        "read_set_revisions": P5RevisionVector(
            entries={
                evidence_stream_ref: read_revision,
                quest_stream_ref: read_revision,
            }
        ),
        "required_schema_pins": (
            P5SchemaPin(
                schema_ref="schema:p5:quest:evidence-registered",
                schema_version=1,
                schema_digest=_digest("4"),
            ),
            P5SchemaPin(
                schema_ref="schema:p5:quest:objective-transitioned",
                schema_version=1,
                schema_digest=_digest("5"),
            ),
        ),
        "relationship_ref": relationship_ref,
        "proposed_events": (
            {
                "event_name": "gameplay.quest.evidence_registered",
                "schema_version": 1,
                "stream_ref": evidence_stream_ref,
                "visibility": "authority_only",
            },
            {
                "event_name": "gameplay.quest.objective_transitioned",
                "schema_version": 1,
                "stream_ref": quest_stream_ref,
                "visibility": "authority_only",
            },
        ),
    }
    if request_updates:
        payload.update(request_updates)
    return P5ResolutionRequest.model_validate(payload)


def _reward_fragment(
    *,
    request_id: str = "request:p5:quest-evidence:1",
    quest_instance_ref: str = "quest-instance-1",
) -> OwnerAuthorizedFragment:
    return OwnerAuthorizedFragment.model_validate(
        {
            "fragment_id": "fragment:reward:quest",
            "owner_principal_ref": "owner:quest-authority",
            "source_rule_ref": "rule:quest:reward",
            "expected_revisions": {
                _quest_stream_ref(quest_instance_ref): 0,
            },
            "read_set_revisions": {
                _evidence_stream_ref(_default_evidence_ref(request_id)): 0,
            },
            "event_specs": {
                _quest_stream_ref(quest_instance_ref): (
                    (
                        "gameplay.quest.objective_transitioned",
                        {
                            "objective_ref": "objective:quest:ledger",
                            "reward_ref": "reward:quest:ledger",
                        },
                    ),
                ),
            },
            "event_visibility_policies": {
                _quest_stream_ref(quest_instance_ref): ("authority_only",),
            },
            "pinned_revisions": {
                "schema:p5:quest:objective-transitioned": 1,
            },
        }
    )


def _event_count(store: GameplayEventStore) -> int:
    return len(store.read_events())


@pytest.fixture
def registry() -> P5PolicyRegistry:
    return _registry()


@pytest.fixture
def store() -> GameplayEventStore:
    return GameplayEventStore()


@pytest.fixture
def authority(registry: P5PolicyRegistry, store: GameplayEventStore):
    return _load_authority()(registry=registry, store=store)


@pytest.fixture
def satisfied_prerequisites() -> tuple[str, ...]:
    return ("fact:case:open",)


def test_import_guard_loads_quest_evidence_authority() -> None:
    authority_type = _load_authority()
    assert authority_type.__name__ == "QuestEvidenceAuthority"


def test_valid_evidence_registration_commits_two_canonical_events_in_one_batch(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
    satisfied_prerequisites: tuple[str, ...],
) -> None:
    evidence_ref = _default_evidence_ref("request:p5:quest-evidence:1")
    result = authority.resolve(
        command=_command(payload_updates={"satisfied_prerequisite_fact_refs": satisfied_prerequisites}),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "committed_success"
    assert result.receipt is not None and result.receipt.committed is True
    assert result.receipt.idempotency_status == "new_commit"
    assert len(store.read_transactions()) == 1
    assert len(store.read_transactions()[0].events) == 2
    events = store.read_events()
    assert [event.event_type for event in events] == [
        "gameplay.quest.evidence_registered",
        "gameplay.quest.objective_transitioned",
    ]
    assert [event.stream_id for event in events] == [
        _evidence_stream_ref(evidence_ref),
        _quest_stream_ref("quest-instance-1"),
    ]
    assert events[0].payload == {
        "request_ref": "request:p5:quest-evidence:1",
        "objective_ref": "objective:quest:ledger",
        "evidence_ref": evidence_ref,
        "evidence_kind_ref": "evidence:receipt",
        "provider_ref": "provider:evidence:ledger",
        "provenance_source_ref": "source:evidence:ledger-1",
        "subject_ref": "actor:investigator",
        "visibility": "authority_only",
        "observed_at": "2026-08-11T00:00:00Z",
        "registry_ref": registry.registry_ref,
        "registry_revision": registry.registry_revision,
        "registry_digest": registry.registry_digest,
        "package_ref": "package:quest:ledger",
        "package_revision": "package:quest:ledger:v1",
        "package_digest": _digest("3"),
        "schema_ref": "schema:p5:quest:evidence-registered",
        "schema_version": 1,
        "schema_digest": _digest("4"),
        "satisfied_prerequisite_fact_refs": list(satisfied_prerequisites),
    }
    assert events[1].payload == {
        "request_ref": "request:p5:quest-evidence:1",
        "objective_ref": "objective:quest:ledger",
        "quest_instance_ref": "quest-instance-1",
        "quest_stream_ref": _quest_stream_ref("quest-instance-1"),
        "transition_ref": "transition:quest:evidence_registered",
        "evidence_ref": evidence_ref,
        "provenance_source_ref": "source:evidence:ledger-1",
        "subject_ref": "actor:investigator",
        "visibility": "authority_only",
        "registry_ref": registry.registry_ref,
        "registry_revision": registry.registry_revision,
        "registry_digest": registry.registry_digest,
        "package_ref": "package:quest:ledger",
        "package_revision": "package:quest:ledger:v1",
        "package_digest": _digest("3"),
        "schema_ref": "schema:p5:quest:objective-transitioned",
        "schema_version": 1,
        "schema_digest": _digest("5"),
        "satisfied_prerequisite_fact_refs": list(satisfied_prerequisites),
    }
    assert result.settlement_plan is not None
    assert result.settlement_plan.expected_revision_vector == {
        _evidence_stream_ref(evidence_ref): 0,
        _quest_stream_ref("quest-instance-1"): 0,
    }


def test_missing_prerequisite_returns_typed_zero_write_and_no_events(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    result = authority.resolve(
        command=_command(payload_updates={"satisfied_prerequisite_fact_refs": ()}),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_prerequisite_unsatisfied"
    assert _event_count(store) == before


def test_disallowed_transition_returns_typed_zero_write_and_no_events(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    result = authority.resolve(
        command=_command(payload_updates={"transition_ref": "transition:quest:invalid"}),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_transition_disallowed"
    assert _event_count(store) == before


def test_wrong_subject_returns_typed_zero_write_and_no_events(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    result = authority.resolve(
        command=_command(payload_updates={"subject_ref": "actor:intruder"}),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_subject_scope_mismatch"
    assert result.receipt is None
    assert _event_count(store) == before


def test_hidden_visibility_returns_typed_zero_write_and_no_events(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    result = authority.resolve(
        command=_command(payload_updates={"visibility": "actor:other"}),
        request=_request(registry, request_updates={"proposed_events": (
            {
                "event_name": "gameplay.quest.evidence_registered",
                "schema_version": 1,
                "stream_ref": _evidence_stream_ref(_default_evidence_ref("request:p5:quest-evidence:1")),
                "visibility": "actor:other",
            },
            {
                "event_name": "gameplay.quest.objective_transitioned",
                "schema_version": 1,
                "stream_ref": _quest_stream_ref("quest-instance-1"),
                "visibility": "actor:other",
            },
        )}),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_evidence_hidden"
    assert _event_count(store) == before


def test_expired_evidence_returns_typed_zero_write_and_no_events(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    result = authority.resolve(
        command=_command(payload_updates={"expires_at": "2026-08-10T23:59:59Z"}),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_evidence_expired"
    assert _event_count(store) == before


def test_noncanonical_stream_refs_return_typed_zero_write_even_when_request_matches(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    evidence_ref = _default_evidence_ref("request:p5:quest-evidence:noncanonical")
    command = _command(
        request_id="request:p5:quest-evidence:noncanonical",
        evidence_ref=evidence_ref,
        payload_updates={
            "evidence_stream_ref": "gameplay:evidence:wrong-ledger-stream",
            "quest_stream_ref": "gameplay:quest:wrong-quest-stream",
        },
    ).model_copy(
        update={
            "expected_revisions": {
                "gameplay:evidence:wrong-ledger-stream": 0,
                "gameplay:quest:wrong-quest-stream": 0,
            },
            "read_set_revisions": {
                "gameplay:evidence:wrong-ledger-stream": 0,
                "gameplay:quest:wrong-quest-stream": 0,
            },
        },
        deep=True,
    )
    request = _request(
        registry,
        request_id="request:p5:quest-evidence:noncanonical",
        evidence_ref=evidence_ref,
        request_updates={
            "expected_revisions": P5RevisionVector(
                entries={
                    "gameplay:evidence:wrong-ledger-stream": 0,
                    "gameplay:quest:wrong-quest-stream": 0,
                }
            ),
            "read_set_revisions": P5RevisionVector(
                entries={
                    "gameplay:evidence:wrong-ledger-stream": 0,
                    "gameplay:quest:wrong-quest-stream": 0,
                }
            ),
            "proposed_events": (
                {
                    "event_name": "gameplay.quest.evidence_registered",
                    "schema_version": 1,
                    "stream_ref": "gameplay:evidence:wrong-ledger-stream",
                    "visibility": "authority_only",
                },
                {
                    "event_name": "gameplay.quest.objective_transitioned",
                    "schema_version": 1,
                    "stream_ref": "gameplay:quest:wrong-quest-stream",
                    "visibility": "authority_only",
                },
            ),
        },
    )

    before = _event_count(store)
    result = authority.resolve(
        command=command,
        request=request,
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_canonical_stream_mismatch"
    assert _event_count(store) == before


def test_single_proposed_event_returns_typed_zero_write_and_no_events(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    request = _request(
        registry,
        request_updates={
            "proposed_events": (
                {
                    "event_name": "gameplay.quest.evidence_registered",
                    "schema_version": 1,
                    "stream_ref": _evidence_stream_ref(_default_evidence_ref("request:p5:quest-evidence:1")),
                    "visibility": "authority_only",
                },
            ),
        },
    )
    before = _event_count(store)

    result = authority.resolve(
        command=_command(),
        request=request,
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_required_events_invalid"
    assert _event_count(store) == before


def test_stale_objective_returns_typed_zero_write_and_no_events(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    first = authority.resolve(
        command=_command(),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )
    assert first.receipt is not None and first.receipt.committed
    before = _event_count(store)

    stale = authority.resolve(
        command=_command(request_id="request:p5:quest-evidence:stale", expected_revision=0, read_revision=0),
        request=_request(registry, request_id="request:p5:quest-evidence:stale", expected_revision=0, read_revision=0),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert stale.resolution.result_kind == "rejected_zero_write"
    assert stale.resolution.failure_code == "p5_objective_stale"
    assert _event_count(store) == before


def test_package_digest_pin_mismatch_returns_zero_write_and_no_events(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    result = authority.resolve(
        command=_command(payload_updates={"package_digest": _digest("f")}),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_package_digest_pin_mismatch"
    assert _event_count(store) == before


def test_duplicate_request_returns_prior_receipt_without_duplicate_append(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    first = authority.resolve(
        command=_command(),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )
    before = _event_count(store)

    duplicate = authority.resolve(
        command=_command(),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert first.receipt is not None and first.receipt.committed
    assert duplicate.resolution.result_kind == "committed_success"
    assert duplicate.receipt is not None
    assert duplicate.receipt.idempotency_status == "duplicate_replayed"
    assert duplicate.receipt.transaction_id == first.receipt.transaction_id
    assert duplicate.receipt.committed_event_ids == first.receipt.committed_event_ids
    assert _event_count(store) == before
    assert len(store.read_transactions()) == 1


def test_changed_package_digest_changes_idempotency_inputs(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    first = authority.resolve(
        command=_command(request_id="request:p5:quest-evidence:digest"),
        request=_request(registry, request_id="request:p5:quest-evidence:digest"),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )
    before = _event_count(store)

    changed = authority.resolve(
        command=_command(
            request_id="request:p5:quest-evidence:digest",
            payload_updates={"package_digest": _digest("8")},
        ),
        request=_request(registry, request_id="request:p5:quest-evidence:digest"),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert first.receipt is not None and first.receipt.committed
    assert changed.resolution.result_kind == "rejected_zero_write"
    assert changed.resolution.failure_code == "idempotency_key_reused"
    assert _event_count(store) == before


def test_reward_fragment_rejected_by_owner_returns_zero_write(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    fragment = _reward_fragment(request_id="request:p5:quest-evidence:owner-reject").model_copy(
        update={"owner_principal_ref": "owner:foreign"}
    )

    result = authority.resolve(
        command=_command(request_id="request:p5:quest-evidence:owner-reject"),
        request=_request(registry, request_id="request:p5:quest-evidence:owner-reject"),
        reward_fragments=(fragment,),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_reward_owner_rejected"
    assert _event_count(store) == before


def test_reward_fragment_missing_visibility_policies_returns_zero_write(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    fragment = _reward_fragment(request_id="request:p5:quest-evidence:missing-visibility").model_copy(
        update={"event_visibility_policies": {}}
    )

    result = authority.resolve(
        command=_command(request_id="request:p5:quest-evidence:missing-visibility"),
        request=_request(registry, request_id="request:p5:quest-evidence:missing-visibility"),
        reward_fragments=(fragment,),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_reward_visibility_rejected"
    assert _event_count(store) == before


def test_reward_fragment_nonallowed_visibility_returns_zero_write(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    fragment = _reward_fragment(request_id="request:p5:quest-evidence:bad-visibility").model_copy(
        update={
            "event_visibility_policies": {
                _quest_stream_ref("quest-instance-1"): ("public",),
            }
        },
        deep=True,
    )

    result = authority.resolve(
        command=_command(request_id="request:p5:quest-evidence:bad-visibility"),
        request=_request(registry, request_id="request:p5:quest-evidence:bad-visibility"),
        reward_fragments=(fragment,),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_reward_visibility_rejected"
    assert _event_count(store) == before


def test_reward_fragment_rejected_by_registry_returns_zero_write(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    before = _event_count(store)
    fragment = _reward_fragment(request_id="request:p5:quest-evidence:registry-reject").model_copy(
        update={
            "event_specs": {
                "stream:foreign": (
                    (
                        "gameplay.quest.objective_transitioned",
                        {"objective_ref": "objective:quest:ledger"},
                    ),
                ),
            },
            "expected_revisions": {"stream:foreign": 0},
        }
    )

    result = authority.resolve(
        command=_command(request_id="request:p5:quest-evidence:registry-reject"),
        request=_request(registry, request_id="request:p5:quest-evidence:registry-reject"),
        reward_fragments=(fragment,),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_reward_registry_rejected"
    assert _event_count(store) == before


def test_snapshot_reload_replays_to_equivalent_hash_and_events(
    registry: P5PolicyRegistry,
    tmp_path,
) -> None:
    QuestEvidenceAuthority = _load_authority()
    original_store = GameplayEventStore()
    original_authority = QuestEvidenceAuthority(registry=registry, store=original_store)

    first = original_authority.resolve(
        command=_command(),
        request=_request(registry),
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )
    assert first.receipt is not None and first.receipt.committed

    snapshot_path = tmp_path / "quest-evidence-store.json"
    original_store.save_snapshot(snapshot_path)
    restored_store = GameplayEventStore.load_snapshot(snapshot_path)
    restored_authority = QuestEvidenceAuthority(registry=registry, store=restored_store)

    command_two = _command(
        request_id="request:p5:quest-evidence:2",
        evidence_ref="evidence:request:p5:quest-evidence:2",
    ).model_copy(
        update={
            "expected_revisions": {
                _evidence_stream_ref("evidence:request:p5:quest-evidence:2"): 0,
                _quest_stream_ref("quest-instance-1"): 1,
            },
            "read_set_revisions": {
                _evidence_stream_ref("evidence:request:p5:quest-evidence:2"): 0,
                _quest_stream_ref("quest-instance-1"): 1,
            },
        },
        deep=True,
    )
    request_two = _request(
        registry,
        request_id="request:p5:quest-evidence:2",
        evidence_ref="evidence:request:p5:quest-evidence:2",
    ).model_copy(
        update={
            "expected_revisions": P5RevisionVector(
                entries={
                    _evidence_stream_ref("evidence:request:p5:quest-evidence:2"): 0,
                    _quest_stream_ref("quest-instance-1"): 1,
                }
            ),
            "read_set_revisions": P5RevisionVector(
                entries={
                    _evidence_stream_ref("evidence:request:p5:quest-evidence:2"): 0,
                    _quest_stream_ref("quest-instance-1"): 1,
                }
            ),
        },
        deep=True,
    )

    original_second = original_authority.resolve(
        command=command_two,
        request=request_two,
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )
    restored_second = restored_authority.resolve(
        command=command_two,
        request=request_two,
        reward_fragments=(),
        now="2026-08-11T00:00:00Z",
    )

    assert original_second.receipt is not None and original_second.receipt.committed
    assert restored_second.receipt is not None and restored_second.receipt.committed
    assert _snapshot_hash(original_store) == _snapshot_hash(restored_store)
    assert [event.model_dump(mode="json") for event in original_store.read_events()] == [
        event.model_dump(mode="json") for event in restored_store.read_events()
    ]
