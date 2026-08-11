from __future__ import annotations

import json
from hashlib import sha256

import pytest

from app.gameplay.event_store import GameplayEventStore
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
        from app.gameplay.p5.social_knowledge import SocialFactAuthority
    except Exception as exc:  # pragma: no cover - explicit RED guard
        pytest.fail(f"production break: social knowledge authority module missing: {exc}")
    return SocialFactAuthority


def _digest(hex_digit: str) -> str:
    return f"sha256:{hex_digit * 64}"


def _canonical_knowledge_stream_ref(*, knower_ref: str, fact_ref: str) -> str:
    payload = {"fact_ref": fact_ref, "knower_ref": knower_ref}
    return "gameplay:knowledge:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _snapshot_hash(store: GameplayEventStore) -> str:
    payload = json.dumps(store.export_snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()


def _relationship_ref(
    *,
    source_ref: str = "character:guard:alpha",
    target_ref: str = "character:baker:beta",
    relation_kind: str = "suspects",
) -> str:
    return build_directed_relationship_ref(
        source_ref=source_ref,
        relation_kind=relation_kind,
        target_ref=target_ref,
    )


def _relationship_stream_ref(
    *,
    source_ref: str = "character:guard:alpha",
    target_ref: str = "character:baker:beta",
    relation_kind: str = "suspects",
) -> str:
    return _relationship_ref(source_ref=source_ref, target_ref=target_ref, relation_kind=relation_kind)


def _knowledge_stream_ref(*, knower_ref: str, fact_ref: str) -> str:
    return _canonical_knowledge_stream_ref(knower_ref=knower_ref, fact_ref=fact_ref)


def _raw_knowledge_stream_ref(*, knower_ref: str, fact_ref: str) -> str:
    return f"gameplay:knowledge:{knower_ref}:{fact_ref}"


def _registry() -> P5PolicyRegistry:
    placeholder_objective = QuestObjectiveDefinition(
        objective_ref="objective:social:placeholder",
        prerequisite_fact_refs=(),
        accepted_evidence_kind_refs=("evidence:observation",),
        visibility="public",
        expiry_policy_ref="expiry:never",
    )
    package = QuestPackageDefinition(
        package_ref="package:social:facts",
        package_revision="package:social:facts:v1",
        package_digest=_digest("3"),
        ruleset_revision="ruleset:p5b:v1",
        objectives=(placeholder_objective,),
    )
    return P5PolicyRegistry.build(
        registry_ref="registry:p5:social",
        registry_revision="registry:p5:social:v1",
        trusted_evidence_providers=(
            TrustedEvidenceProvider(
                provider_ref="provider:evidence:social-observer",
                provider_revision="provider:evidence:social-observer:v1",
                provider_digest=_digest("1"),
                allowed_evidence_kinds=("evidence:observation", "evidence:ledger"),
            ),
        ),
        owner_adapter_allowlist=(
            OwnerAdapterAllowance(
                owner_ref="owner:social-authority",
                allowed_event_names=(
                    "gameplay.social.relationship_fact_recorded",
                    "gameplay.social.knowledge_observed",
                    "gameplay.social.visibility_revoked",
                ),
                allowed_stream_grammar_refs=("grammar:p5:relationship", "grammar:p5:knowledge"),
            ),
        ),
        quest_packages=(package,),
        ruleset_revisions=("ruleset:p5b:v1",),
        schema_pins=(
            P5SchemaPin(
                schema_ref="schema:p5:social:relationship-recorded",
                schema_version=1,
                schema_digest=_digest("4"),
            ),
            P5SchemaPin(
                schema_ref="schema:p5:social:knowledge-observed",
                schema_version=1,
                schema_digest=_digest("5"),
            ),
            P5SchemaPin(
                schema_ref="schema:p5:social:visibility-revoked",
                schema_version=1,
                schema_digest=_digest("6"),
            ),
        ),
        event_namespaces=(
            P5EventNamespace(
                namespace_ref="namespace:p5:social",
                event_name_prefix="gameplay.social.",
                allowed_event_names=(
                    "gameplay.social.relationship_fact_recorded",
                    "gameplay.social.knowledge_observed",
                    "gameplay.social.visibility_revoked",
                ),
            ),
        ),
        event_catalog=(
            P5EventCatalogEntry(
                event_name="gameplay.social.relationship_fact_recorded",
                namespace_ref="namespace:p5:social",
                schema_ref="schema:p5:social:relationship-recorded",
                schema_version=1,
                stream_grammar_ref="grammar:p5:relationship",
            ),
            P5EventCatalogEntry(
                event_name="gameplay.social.knowledge_observed",
                namespace_ref="namespace:p5:social",
                schema_ref="schema:p5:social:knowledge-observed",
                schema_version=1,
                stream_grammar_ref="grammar:p5:knowledge",
            ),
            P5EventCatalogEntry(
                event_name="gameplay.social.visibility_revoked",
                namespace_ref="namespace:p5:social",
                schema_ref="schema:p5:social:visibility-revoked",
                schema_version=1,
                stream_grammar_ref="grammar:p5:knowledge",
            ),
        ),
        stream_grammars=(
            P5StreamGrammar(
                grammar_ref="grammar:p5:relationship",
                pattern=r"^gameplay:relationship:[0-9a-f]{64}$",
            ),
            P5StreamGrammar(
                grammar_ref="grammar:p5:knowledge",
                pattern=r"^gameplay:knowledge:.+$",
            ),
        ),
    )


def _relationship_payload(
    *,
    source_ref: str = "character:guard:alpha",
    target_ref: str = "character:baker:beta",
    relation_kind: str = "suspects",
    visibility: str = "public",
    confidence: float = 0.9,
    decay_rate_per_day: float = 0.05,
    evidence_ref: str = "evidence:social:public:1",
    provenance_source_ref: str = "source:evidence:public-observer-1",
    observed_at: str = "2026-08-11T00:00:00Z",
) -> dict[str, object]:
    return {
        "relationship_ref": _relationship_ref(
            source_ref=source_ref,
            target_ref=target_ref,
            relation_kind=relation_kind,
        ),
        "source_ref": source_ref,
        "target_ref": target_ref,
        "relation_kind": relation_kind,
        "visibility": visibility,
        "confidence": confidence,
        "decay_rate_per_day": decay_rate_per_day,
        "evidence_ref": evidence_ref,
        "provenance_source_ref": provenance_source_ref,
        "observed_at": observed_at,
    }


def _knowledge_payload(
    *,
    fact_ref: str = "fact:bakery:bread-theft",
    knower_ref: str = "character:baker:beta",
    subject_ref: str = "character:baker:beta",
    visibility: str = "actor:character:baker:beta",
    confidence: float = 0.7,
    decay_rate_per_day: float = 0.02,
    evidence_ref: str = "evidence:social:private:1",
    provenance_source_ref: str = "source:evidence:private-clue-1",
    observed_at: str = "2026-08-11T00:00:00Z",
    observation_ref: str = "observation:private-ledger",
    knowledge_kind: str = "observed_fact",
) -> dict[str, object]:
    return {
        "fact_ref": fact_ref,
        "knower_ref": knower_ref,
        "subject_ref": subject_ref,
        "visibility": visibility,
        "confidence": confidence,
        "decay_rate_per_day": decay_rate_per_day,
        "evidence_ref": evidence_ref,
        "provenance_source_ref": provenance_source_ref,
        "observed_at": observed_at,
        "observation_ref": observation_ref,
        "knowledge_kind": knowledge_kind,
    }


def _record_command(
    *,
    request_id: str = "request:p5:social:1",
    relationship_fact: dict[str, object] | None = None,
    knowledge_fact: dict[str, object] | None = None,
    expected_revisions: dict[str, int] | None = None,
    read_revisions: dict[str, int] | None = None,
    payload_updates: dict[str, object] | None = None,
) -> GameplayCommandEnvelope:
    payload: dict[str, object] = {
        "relationship_fact": relationship_fact,
        "knowledge_fact": knowledge_fact,
        "provider_ref": "provider:evidence:social-observer",
        "owner_adapter_ref": "owner:social-authority",
        "package_ref": "package:social:facts",
        "package_revision": "package:social:facts:v1",
        "package_digest": _digest("3"),
        "ruleset_revision": "ruleset:p5b:v1",
    }
    if payload_updates:
        payload.update(payload_updates)
    return GameplayCommandEnvelope.model_validate(
        {
            "command_id": f"command:{request_id}",
            "command_type": "gameplay.social.record_facts",
            "command_version": 1,
            "principal_ref": "principal:p5:social",
            "actor_ref": "character:guard:alpha",
            "project_ref": "project:p5",
            "transaction_id": f"tx:{request_id}",
            "idempotency_key": f"idempotency:{request_id}",
            "expected_revisions": expected_revisions or {},
            "read_set_revisions": read_revisions or {},
            "causation_id": f"cause:{request_id}",
            "correlation_id": f"corr:{request_id}",
            "source_ref": "source:godot",
            "submitted_at": "2026-08-11T00:00:00Z",
            "pinned_revisions": {
                "schema:p5:social:relationship-recorded": 1,
                "schema:p5:social:knowledge-observed": 1,
                "schema:p5:social:visibility-revoked": 1,
            },
            "payload": payload,
        }
    )


def _revoke_command(
    *,
    request_id: str,
    fact_ref: str,
    knower_ref: str,
    recipient_ref: str,
    prior_visibility: str,
    expected_revisions: dict[str, int],
    read_revisions: dict[str, int],
) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope.model_validate(
        {
            "command_id": f"command:{request_id}",
            "command_type": "gameplay.social.revoke_visibility",
            "command_version": 1,
            "principal_ref": "principal:p5:social",
            "actor_ref": "character:guard:alpha",
            "project_ref": "project:p5",
            "transaction_id": f"tx:{request_id}",
            "idempotency_key": f"idempotency:{request_id}",
            "expected_revisions": expected_revisions,
            "read_set_revisions": read_revisions,
            "causation_id": f"cause:{request_id}",
            "correlation_id": f"corr:{request_id}",
            "source_ref": "source:godot",
            "submitted_at": "2026-08-11T00:00:00Z",
            "pinned_revisions": {
                "schema:p5:social:relationship-recorded": 1,
                "schema:p5:social:knowledge-observed": 1,
                "schema:p5:social:visibility-revoked": 1,
            },
            "payload": {
                "revocation": {
                    "fact_ref": fact_ref,
                    "knower_ref": knower_ref,
                    "recipient_ref": recipient_ref,
                    "prior_visibility": prior_visibility,
                    "reason_code": "source_recanted",
                    "evidence_ref": "evidence:social:revocation:1",
                    "provenance_source_ref": "source:evidence:revocation-1",
                    "observed_at": "2026-08-11T01:00:00Z",
                    "visibility": "authority_only",
                },
                "provider_ref": "provider:evidence:social-observer",
                "owner_adapter_ref": "owner:social-authority",
                "package_ref": "package:social:facts",
                "package_revision": "package:social:facts:v1",
                "package_digest": _digest("3"),
                "ruleset_revision": "ruleset:p5b:v1",
            },
        }
    )


def _request(
    registry: P5PolicyRegistry,
    *,
    request_id: str = "request:p5:social:1",
    relationship_fact: dict[str, object] | None = None,
    relationship_ref: str | None = None,
    knowledge_fact: dict[str, object] | None = None,
    revocation: dict[str, object] | None = None,
    expected_revisions: dict[str, int] | None = None,
    read_revisions: dict[str, int] | None = None,
    request_updates: dict[str, object] | None = None,
) -> P5ResolutionRequest:
    proposed_events: list[dict[str, object]] = []
    if relationship_fact is not None:
        proposed_events.append(
            {
                "event_name": "gameplay.social.relationship_fact_recorded",
                "schema_version": 1,
                "stream_ref": str(relationship_fact["relationship_ref"]),
                "visibility": str(relationship_fact["visibility"]),
            }
        )
    if knowledge_fact is not None:
        proposed_events.append(
            {
                "event_name": "gameplay.social.knowledge_observed",
                "schema_version": 1,
                "stream_ref": _knowledge_stream_ref(
                    knower_ref=str(knowledge_fact["knower_ref"]),
                    fact_ref=str(knowledge_fact["fact_ref"]),
                ),
                "visibility": str(knowledge_fact["visibility"]),
            }
        )
    if revocation is not None:
        proposed_events.append(
            {
                "event_name": "gameplay.social.visibility_revoked",
                "schema_version": 1,
                "stream_ref": _knowledge_stream_ref(
                    knower_ref=str(revocation["knower_ref"]),
                    fact_ref=str(revocation["fact_ref"]),
                ),
                "visibility": "authority_only",
            }
        )
    payload: dict[str, object] = {
        "request_ref": request_id,
        "registry_ref": registry.registry_ref,
        "registry_revision": registry.registry_revision,
        "registry_digest": registry.registry_digest,
        "package_ref": "package:social:facts",
        "package_revision": "package:social:facts:v1",
        "ruleset_revision": "ruleset:p5b:v1",
        "evidence_provider_ref": "provider:evidence:social-observer",
        "owner_adapter_ref": "owner:social-authority",
        "provenance_source_ref": "source:evidence:social",
        "subject_scope_ref": "character:guard:alpha",
        "expected_revisions": P5RevisionVector(entries=expected_revisions or {}),
        "read_set_revisions": P5RevisionVector(entries=read_revisions or {}),
        "required_schema_pins": (
            P5SchemaPin(
                schema_ref="schema:p5:social:relationship-recorded",
                schema_version=1,
                schema_digest=_digest("4"),
            ),
            P5SchemaPin(
                schema_ref="schema:p5:social:knowledge-observed",
                schema_version=1,
                schema_digest=_digest("5"),
            ),
            P5SchemaPin(
                schema_ref="schema:p5:social:visibility-revoked",
                schema_version=1,
                schema_digest=_digest("6"),
            ),
        ),
        "relationship_ref": str(
            relationship_ref
            or (relationship_fact or _relationship_payload())["relationship_ref"]
        ),
        "proposed_events": tuple(proposed_events),
    }
    if request_updates:
        payload.update(request_updates)
    return P5ResolutionRequest.model_validate(payload)


@pytest.fixture
def registry() -> P5PolicyRegistry:
    return _registry()


@pytest.fixture
def store() -> GameplayEventStore:
    return GameplayEventStore()


@pytest.fixture
def authority(registry: P5PolicyRegistry, store: GameplayEventStore):
    return _load_authority()(registry=registry, store=store)


def test_import_guard_loads_social_fact_authority() -> None:
    authority_type = _load_authority()
    assert authority_type.__name__ == "SocialFactAuthority"


def test_public_relationship_and_private_knowledge_commit_in_one_batch_with_recipient_redaction(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    relationship_fact = _relationship_payload()
    knowledge_fact = _knowledge_payload()
    expected_revisions = {
        str(relationship_fact["relationship_ref"]): 0,
        _knowledge_stream_ref(
            knower_ref=str(knowledge_fact["knower_ref"]),
            fact_ref=str(knowledge_fact["fact_ref"]),
        ): 0,
    }
    result = authority.resolve(
        command=_record_command(
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=expected_revisions,
            read_revisions=expected_revisions,
        ),
        request=_request(
            registry,
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=expected_revisions,
            read_revisions=expected_revisions,
        ),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "committed_success"
    assert result.receipt is not None and result.receipt.committed is True
    assert result.receipt.idempotency_status == "new_commit"
    assert result.settlement_plan is not None
    assert result.settlement_plan.expected_revision_vector == expected_revisions
    assert len(store.read_transactions()) == 1
    events = store.read_events()
    assert [event.event_type for event in events] == [
        "gameplay.social.relationship_fact_recorded",
        "gameplay.social.knowledge_observed",
    ]
    assert [event.stream_id for event in events] == [
        str(relationship_fact["relationship_ref"]),
        _knowledge_stream_ref(
            knower_ref=str(knowledge_fact["knower_ref"]),
            fact_ref=str(knowledge_fact["fact_ref"]),
        ),
    ]
    for event in events:
        assert event.payload["registry_ref"] == registry.registry_ref
        assert event.payload["registry_revision"] == registry.registry_revision
        assert event.payload["registry_digest"] == registry.registry_digest
        assert event.payload["read_stream_revisions"] == expected_revisions
        assert event.payload["expected_stream_revisions"] == expected_revisions
        assert event.payload["visibility"] == event.visibility_policy
        assert event.payload["provenance_source_ref"]
        assert event.payload["evidence_ref"]
    assert all(
        event.stream_id.startswith("gameplay:relationship:") or event.stream_id.startswith("gameplay:knowledge:")
        for event in events
    )

    public_view = authority.view_for(recipient_ref="character:outsider", now="2026-08-11T00:00:00Z")
    private_view = authority.view_for(recipient_ref="character:baker:beta", now="2026-08-11T00:00:00Z")

    assert len(public_view.relationship_facts) == 1
    assert public_view.relationship_facts[0]["relationship_ref"] == relationship_fact["relationship_ref"]
    assert "evidence_ref" not in public_view.relationship_facts[0]
    assert public_view.knowledge_facts == ()

    assert len(private_view.relationship_facts) == 1
    assert len(private_view.knowledge_facts) == 1
    assert private_view.knowledge_facts[0]["fact_ref"] == knowledge_fact["fact_ref"]
    assert private_view.knowledge_facts[0]["observation_ref"] == knowledge_fact["observation_ref"]


def test_relationship_ref_mismatch_returns_typed_zero_write_and_keeps_store_unchanged(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    relationship_fact = _relationship_payload()
    knowledge_fact = _knowledge_payload()
    expected_revisions = {
        str(relationship_fact["relationship_ref"]): 0,
        _knowledge_stream_ref(
            knower_ref=str(knowledge_fact["knower_ref"]),
            fact_ref=str(knowledge_fact["fact_ref"]),
        ): 0,
    }
    before = len(store.read_events())

    result = authority.resolve(
        command=_record_command(
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=expected_revisions,
            read_revisions=expected_revisions,
        ),
        request=_request(
            registry,
            relationship_ref="gameplay:relationship:" + "f" * 64,
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=expected_revisions,
            read_revisions=expected_revisions,
        ),
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_canonical_stream_mismatch"
    assert len(store.read_events()) == before


def test_knowledge_stream_ref_avoids_raw_colon_collision_and_keeps_revocation_isolated(
    authority,
    registry: P5PolicyRegistry,
) -> None:
    knower_a = "character:guard:a"
    fact_a = "b:c"
    knower_b = "character:guard:a:b"
    fact_b = "c"
    raw_a = _raw_knowledge_stream_ref(knower_ref=knower_a, fact_ref=fact_a)
    raw_b = _raw_knowledge_stream_ref(knower_ref=knower_b, fact_ref=fact_b)
    canonical_a = _knowledge_stream_ref(knower_ref=knower_a, fact_ref=fact_a)
    canonical_b = _knowledge_stream_ref(knower_ref=knower_b, fact_ref=fact_b)
    fact_payload_a = _knowledge_payload(
        fact_ref=fact_a,
        knower_ref=knower_a,
        subject_ref="character:baker:beta",
        visibility="public",
        observation_ref="observation:collision-a",
    )
    fact_payload_b = _knowledge_payload(
        fact_ref=fact_b,
        knower_ref=knower_b,
        subject_ref="character:baker:beta",
        visibility="public",
        observation_ref="observation:collision-b",
    )
    revisions_first = {canonical_a: 0, canonical_b: 0}

    assert raw_a == raw_b
    assert canonical_a != canonical_b

    first = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:collision:1",
            knowledge_fact=fact_payload_a,
            expected_revisions=revisions_first,
            read_revisions=revisions_first,
        ),
        request=_request(
            registry,
            request_id="request:p5:social:collision:1",
            knowledge_fact=fact_payload_a,
            expected_revisions=revisions_first,
            read_revisions=revisions_first,
        ),
        now="2026-08-11T00:00:00Z",
    )
    assert first.receipt is not None and first.receipt.committed

    second = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:collision:2",
            knowledge_fact=fact_payload_b,
            expected_revisions={canonical_b: 0},
            read_revisions={canonical_b: 0},
        ),
        request=_request(
            registry,
            request_id="request:p5:social:collision:2",
            knowledge_fact=fact_payload_b,
            expected_revisions={canonical_b: 0},
            read_revisions={canonical_b: 0},
        ),
        now="2026-08-11T00:00:00Z",
    )
    assert second.receipt is not None and second.receipt.committed

    before_revocation = authority.view_for(recipient_ref="character:baker:beta", now="2026-08-11T00:00:00Z")
    assert {fact["observation_ref"] for fact in before_revocation.knowledge_facts} == {
        "observation:collision-a",
        "observation:collision-b",
    }

    revoke = authority.resolve(
        command=_revoke_command(
            request_id="request:p5:social:collision:3",
            fact_ref=fact_a,
            knower_ref=knower_a,
            recipient_ref="character:baker:beta",
            prior_visibility="public",
            expected_revisions={canonical_a: 1},
            read_revisions={canonical_a: 1},
        ),
        request=_request(
            registry,
            request_id="request:p5:social:collision:3",
            revocation={
                "fact_ref": fact_a,
                "knower_ref": knower_a,
                "recipient_ref": "character:baker:beta",
                "prior_visibility": "public",
            },
            expected_revisions={canonical_a: 1},
            read_revisions={canonical_a: 1},
        ),
        now="2026-08-11T01:00:00Z",
    )
    assert revoke.receipt is not None and revoke.receipt.committed

    recipient_view = authority.view_for(recipient_ref="character:baker:beta", now="2026-08-11T01:00:00Z")
    outsider_view = authority.view_for(recipient_ref="character:outsider", now="2026-08-11T01:00:00Z")
    assert [fact["observation_ref"] for fact in recipient_view.knowledge_facts] == ["observation:collision-b"]
    assert {fact["observation_ref"] for fact in outsider_view.knowledge_facts} == {
        "observation:collision-a",
        "observation:collision-b",
    }


def test_conflicting_observations_are_retained_with_deterministic_decay_and_reputation_projection(
    authority,
    registry: P5PolicyRegistry,
) -> None:
    relationship_fact = _relationship_payload(
        confidence=0.9,
        decay_rate_per_day=0.05,
        observed_at="2026-08-11T00:00:00Z",
    )
    knowledge_a = _knowledge_payload(
        fact_ref="fact:bakery:alibi",
        knower_ref="character:guard:alpha",
        subject_ref="character:baker:beta",
        visibility="public",
        confidence=0.9,
        decay_rate_per_day=0.1,
        observed_at="2026-08-11T00:00:00Z",
        observation_ref="observation:saw-baker-near-register",
    )
    revisions_first = {
        str(relationship_fact["relationship_ref"]): 0,
        _knowledge_stream_ref(knower_ref="character:guard:alpha", fact_ref="fact:bakery:alibi"): 0,
    }
    first = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:conflict:1",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_a,
            expected_revisions=revisions_first,
            read_revisions=revisions_first,
        ),
        request=_request(
            registry,
            request_id="request:p5:social:conflict:1",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_a,
            expected_revisions=revisions_first,
            read_revisions=revisions_first,
        ),
        now="2026-08-11T00:00:00Z",
    )
    assert first.receipt is not None and first.receipt.committed

    knowledge_b = _knowledge_payload(
        fact_ref="fact:bakery:alibi",
        knower_ref="character:guard:alpha",
        subject_ref="character:baker:beta",
        visibility="public",
        confidence=0.8,
        decay_rate_per_day=0.05,
        observed_at="2026-08-12T00:00:00Z",
        observation_ref="observation:did-not-see-baker-near-register",
    )
    revisions_second = {
        _knowledge_stream_ref(knower_ref="character:guard:alpha", fact_ref="fact:bakery:alibi"): 1,
    }
    second = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:conflict:2",
            relationship_fact=None,
            knowledge_fact=knowledge_b,
            expected_revisions=revisions_second,
            read_revisions=revisions_second,
        ),
        request=_request(
            registry,
            request_id="request:p5:social:conflict:2",
            relationship_ref=str(relationship_fact["relationship_ref"]),
            knowledge_fact=knowledge_b,
            expected_revisions=revisions_second,
            read_revisions=revisions_second,
        ),
        now="2026-08-12T00:00:00Z",
    )
    assert second.receipt is not None and second.receipt.committed

    public_view = authority.view_for(recipient_ref="character:outsider", now="2026-08-13T00:00:00Z")
    assert len(public_view.knowledge_facts) == 2
    assert [fact["observation_ref"] for fact in public_view.knowledge_facts] == [
        "observation:did-not-see-baker-near-register",
        "observation:saw-baker-near-register",
    ]
    assert [fact["projected_confidence"] for fact in public_view.knowledge_facts] == [0.75, 0.7]
    assert public_view.reputation["character:baker:beta"]["suspects"] == 0.8


def test_visibility_revocation_invalidates_recipient_view_and_requests_mirror_resync(
    authority,
    registry: P5PolicyRegistry,
) -> None:
    relationship_fact = _relationship_payload()
    knowledge_fact = _knowledge_payload()
    knowledge_stream = _knowledge_stream_ref(
        knower_ref=str(knowledge_fact["knower_ref"]),
        fact_ref=str(knowledge_fact["fact_ref"]),
    )
    initial_revisions = {
        str(relationship_fact["relationship_ref"]): 0,
        knowledge_stream: 0,
    }
    first = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:revocation:1",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=initial_revisions,
            read_revisions=initial_revisions,
        ),
        request=_request(
            registry,
            request_id="request:p5:social:revocation:1",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=initial_revisions,
            read_revisions=initial_revisions,
        ),
        now="2026-08-11T00:00:00Z",
    )
    assert first.receipt is not None and first.receipt.committed
    assert len(authority.view_for(recipient_ref="character:baker:beta", now="2026-08-11T00:00:00Z").knowledge_facts) == 1

    revocation = {
        "fact_ref": str(knowledge_fact["fact_ref"]),
        "knower_ref": str(knowledge_fact["knower_ref"]),
        "recipient_ref": "character:baker:beta",
        "prior_visibility": str(knowledge_fact["visibility"]),
    }
    revoke = authority.resolve(
        command=_revoke_command(
            request_id="request:p5:social:revocation:2",
            fact_ref=str(knowledge_fact["fact_ref"]),
            knower_ref=str(knowledge_fact["knower_ref"]),
            recipient_ref="character:baker:beta",
            prior_visibility=str(knowledge_fact["visibility"]),
            expected_revisions={knowledge_stream: 1},
            read_revisions={knowledge_stream: 1},
        ),
        request=_request(
            registry,
            request_id="request:p5:social:revocation:2",
            relationship_ref=str(relationship_fact["relationship_ref"]),
            revocation=revocation,
            expected_revisions={knowledge_stream: 1},
            read_revisions={knowledge_stream: 1},
        ),
        now="2026-08-11T01:00:00Z",
    )

    assert revoke.resolution.result_kind == "committed_success"
    assert revoke.receipt is not None and revoke.receipt.committed
    assert [hint.projection_id for hint in revoke.receipt.projection_refresh_hints] == ["godot_mirror"]
    assert revoke.receipt.projection_refresh_hints[0].actor_refs == ("character:baker:beta",)
    assert revoke.receipt.projection_refresh_hints[0].reason == "visibility_revoked"
    assert authority.view_for(recipient_ref="character:baker:beta", now="2026-08-11T01:00:00Z").knowledge_facts == ()


def test_stale_policy_or_revisions_return_typed_zero_write_without_new_events(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
) -> None:
    relationship_fact = _relationship_payload()
    knowledge_fact = _knowledge_payload()
    revisions = {
        str(relationship_fact["relationship_ref"]): 0,
        _knowledge_stream_ref(
            knower_ref=str(knowledge_fact["knower_ref"]),
            fact_ref=str(knowledge_fact["fact_ref"]),
        ): 0,
    }
    before = len(store.read_events())

    bad_policy = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:policy-mismatch",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=revisions,
            read_revisions=revisions,
        ),
        request=_request(
            registry,
            request_id="request:p5:social:policy-mismatch",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=revisions,
            read_revisions=revisions,
            request_updates={"registry_revision": "registry:p5:social:v999"},
        ),
        now="2026-08-11T00:00:00Z",
    )
    assert bad_policy.resolution.result_kind == "rejected_zero_write"
    assert bad_policy.resolution.failure_code == "p5_policy_registry_pin_mismatch"
    assert len(store.read_events()) == before

    committed = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:stale-1",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=revisions,
            read_revisions=revisions,
        ),
        request=_request(
            registry,
            request_id="request:p5:social:stale-1",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=revisions,
            read_revisions=revisions,
        ),
        now="2026-08-11T00:00:00Z",
    )
    assert committed.receipt is not None and committed.receipt.committed
    after_commit = len(store.read_events())

    stale = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:stale-2",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=revisions,
            read_revisions=revisions,
        ),
        request=_request(
            registry,
            request_id="request:p5:social:stale-2",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=revisions,
            read_revisions=revisions,
        ),
        now="2026-08-11T00:05:00Z",
    )
    assert stale.resolution.result_kind == "rejected_zero_write"
    assert stale.resolution.failure_code == "p5_revision_stale"
    assert len(store.read_events()) == after_commit


def test_malformed_observed_at_rejects_write_and_does_not_crash_replay(
    authority,
    registry: P5PolicyRegistry,
    store: GameplayEventStore,
    tmp_path,
) -> None:
    bad_fact = _knowledge_payload(
        observed_at="not-a-timestamp",
        observation_ref="observation:malformed",
    )
    bad_stream = _knowledge_stream_ref(
        knower_ref=str(bad_fact["knower_ref"]),
        fact_ref=str(bad_fact["fact_ref"]),
    )
    before = len(store.read_events())

    rejected = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:bad-time",
            knowledge_fact=bad_fact,
            expected_revisions={bad_stream: 0},
            read_revisions={bad_stream: 0},
        ),
        request=_request(
            registry,
            request_id="request:p5:social:bad-time",
            knowledge_fact=bad_fact,
            expected_revisions={bad_stream: 0},
            read_revisions={bad_stream: 0},
        ),
        now="2026-08-11T00:00:00Z",
    )

    assert rejected.resolution.result_kind == "rejected_zero_write"
    assert rejected.resolution.failure_code == "p5_observed_at_invalid"
    assert len(store.read_events()) == before

    good_fact = _knowledge_payload(
        fact_ref="fact:bakery:valid",
        knower_ref="character:guard:alpha",
        subject_ref="character:baker:beta",
        visibility="public",
        observation_ref="observation:valid",
    )
    good_stream = _knowledge_stream_ref(
        knower_ref=str(good_fact["knower_ref"]),
        fact_ref=str(good_fact["fact_ref"]),
    )
    committed = authority.resolve(
        command=_record_command(
            request_id="request:p5:social:good-time",
            knowledge_fact=good_fact,
            expected_revisions={good_stream: 0},
            read_revisions={good_stream: 0},
        ),
        request=_request(
            registry,
            request_id="request:p5:social:good-time",
            knowledge_fact=good_fact,
            expected_revisions={good_stream: 0},
            read_revisions={good_stream: 0},
        ),
        now="2026-08-11T00:00:00Z",
    )
    assert committed.receipt is not None and committed.receipt.committed

    store._events[0].payload["observed_at"] = "not-a-timestamp"  # type: ignore[index]
    mutated_snapshot = tmp_path / "p5-social-malformed.json"
    store.save_snapshot(mutated_snapshot)
    restored_store = GameplayEventStore.load_snapshot(mutated_snapshot)
    restored_authority = _load_authority()(registry=registry, store=restored_store)

    view = restored_authority.view_for(recipient_ref="character:outsider", now="2026-08-11T00:00:00Z")
    assert view.knowledge_facts == ()
    assert isinstance(view.projection_hash, str)


def test_full_checkpoint_tail_and_live_replay_preserve_recipient_authorized_projection_hash(
    registry: P5PolicyRegistry,
    tmp_path,
) -> None:
    SocialFactAuthority = _load_authority()
    original_store = GameplayEventStore()
    original_authority = SocialFactAuthority(registry=registry, store=original_store)

    relationship_fact = _relationship_payload()
    knowledge_fact = _knowledge_payload(
        visibility="public",
        knower_ref="character:guard:alpha",
        subject_ref="character:baker:beta",
        observation_ref="observation:public-ledger",
    )
    initial_revisions = {
        str(relationship_fact["relationship_ref"]): 0,
        _knowledge_stream_ref(knower_ref="character:guard:alpha", fact_ref=str(knowledge_fact["fact_ref"])): 0,
    }
    first = original_authority.resolve(
        command=_record_command(
            request_id="request:p5:social:reload:1",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=initial_revisions,
            read_revisions=initial_revisions,
        ),
        request=_request(
            registry,
            request_id="request:p5:social:reload:1",
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=initial_revisions,
            read_revisions=initial_revisions,
        ),
        now="2026-08-11T00:00:00Z",
    )
    assert first.receipt is not None and first.receipt.committed
    checkpoint_path = tmp_path / "p5-social-checkpoint.json"
    original_store.save_snapshot(checkpoint_path)

    second_knowledge = _knowledge_payload(
        fact_ref="fact:bakery:alibi",
        knower_ref="character:guard:alpha",
        subject_ref="character:baker:beta",
        visibility="public",
        confidence=0.8,
        decay_rate_per_day=0.05,
        observed_at="2026-08-12T00:00:00Z",
        observation_ref="observation:checkpoint-tail",
    )
    second_revisions = {
        _knowledge_stream_ref(knower_ref="character:guard:alpha", fact_ref="fact:bakery:alibi"): 0,
    }
    command_two = _record_command(
        request_id="request:p5:social:reload:2",
        relationship_fact=None,
        knowledge_fact=second_knowledge,
        expected_revisions=second_revisions,
        read_revisions=second_revisions,
    )
    request_two = _request(
        registry,
        request_id="request:p5:social:reload:2",
        relationship_ref=str(relationship_fact["relationship_ref"]),
        knowledge_fact=second_knowledge,
        expected_revisions=second_revisions,
        read_revisions=second_revisions,
    )

    live_second = original_authority.resolve(
        command=command_two,
        request=request_two,
        now="2026-08-12T00:00:00Z",
    )
    assert live_second.receipt is not None and live_second.receipt.committed

    checkpoint_store = GameplayEventStore.load_snapshot(checkpoint_path)
    checkpoint_authority = SocialFactAuthority(registry=registry, store=checkpoint_store)
    checkpoint_tail_second = checkpoint_authority.resolve(
        command=command_two,
        request=request_two,
        now="2026-08-12T00:00:00Z",
    )
    assert checkpoint_tail_second.receipt is not None and checkpoint_tail_second.receipt.committed

    full_path = tmp_path / "p5-social-full.json"
    original_store.save_snapshot(full_path)
    full_store = GameplayEventStore.load_snapshot(full_path)
    full_authority = SocialFactAuthority(registry=registry, store=full_store)

    live_view = original_authority.view_for(recipient_ref="character:outsider", now="2026-08-13T00:00:00Z")
    checkpoint_tail_view = checkpoint_authority.view_for(recipient_ref="character:outsider", now="2026-08-13T00:00:00Z")
    full_view = full_authority.view_for(recipient_ref="character:outsider", now="2026-08-13T00:00:00Z")

    assert _snapshot_hash(original_store) == _snapshot_hash(checkpoint_store) == _snapshot_hash(full_store)
    assert live_view.projection_hash == checkpoint_tail_view.projection_hash == full_view.projection_hash
    assert live_view.relationship_facts == checkpoint_tail_view.relationship_facts == full_view.relationship_facts
    assert live_view.knowledge_facts == checkpoint_tail_view.knowledge_facts == full_view.knowledge_facts
    assert live_view.reputation == checkpoint_tail_view.reputation == full_view.reputation
