from __future__ import annotations

from test_embodied_interaction_session import _propose, _service
from test_p5_social_knowledge import _digest, _registry

from app.gameplay.governed_contract_catalog import (
    GovernedAuthorityContract,
    GovernedAuthorityContractCatalog,
    OwnerOperationDescriptor,
)
from app.gameplay.event_schema_registry import EventSchemaRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent, IdempotencyRecord
from app.gameplay.p5.registry import (
    OwnerAdapterAllowance,
    P5EventCatalogEntry,
    P5EventNamespace,
    P5PolicyRegistry,
    P5SchemaPin,
    P5StreamGrammar,
)
from app.gameplay.p5.social_knowledge import SocialFactAuthority


EVENT = "gameplay.social.handshake_shared_experience_recorded"
SCHEMA = "schema:p5:social:handshake-shared-experience-recorded"
GRAMMAR = "grammar:p5:shared-experience"


def _handshake_registry() -> P5PolicyRegistry:
    base = _registry()
    namespace = base.event_namespaces[0].model_copy(
        update={"allowed_event_names": (*base.event_namespaces[0].allowed_event_names, EVENT)},
        deep=True,
    )
    owner = base.owner_adapter_allowlist[0].model_copy(
        update={
            "allowed_event_names": (*base.owner_adapter_allowlist[0].allowed_event_names, EVENT),
            "allowed_stream_grammar_refs": (*base.owner_adapter_allowlist[0].allowed_stream_grammar_refs, GRAMMAR),
        },
        deep=True,
    )
    return P5PolicyRegistry.build(
        registry_ref=base.registry_ref,
        registry_revision="registry:p5:social:v2",
        trusted_evidence_providers=base.trusted_evidence_providers,
        owner_adapter_allowlist=(owner,),
        quest_packages=base.quest_packages,
        ruleset_revisions=base.ruleset_revisions,
        schema_pins=(
            *base.schema_pins,
            P5SchemaPin(
                schema_ref=SCHEMA,
                schema_version=1,
                schema_digest="sha256:963801afdb239c431578691d933c51e120dd02dd36f0c2c460f894ecec5b1810",
            ),
        ),
        event_namespaces=(namespace,),
        event_catalog=(
            *base.event_catalog,
            P5EventCatalogEntry(
                event_name=EVENT,
                namespace_ref=namespace.namespace_ref,
                schema_ref=SCHEMA,
                schema_version=1,
                stream_grammar_ref=GRAMMAR,
            ),
        ),
        stream_grammars=(
            *base.stream_grammars,
            P5StreamGrammar(
                grammar_ref=GRAMMAR,
                pattern=r"^gameplay:social:shared-experience:character:[^:]+$",
            ),
        ),
    )


def _completed_handshake():
    service, store, _bus, _ledger = _service()
    _propose(service, session_id="session:handshake:inf4ai")
    service.accept(
        session_id="session:handshake:inf4ai",
        participant_ref="character:maya",
        causation_id="cmd:inf4ai:accept",
        payload_digest="digest:inf4ai:accept",
    )
    service.start_realizing(
        session_id="session:handshake:inf4ai",
        causation_id="cmd:inf4ai:realize",
    )
    service.record_terminal_observation(
        session_id="session:handshake:inf4ai",
        participant_ref="character:siming",
        attempt_ref="attempt:inf4ai:siming",
        terminal_status="completed",
        payload_digest="digest:inf4ai:siming",
    )
    result = service.record_terminal_observation(
        session_id="session:handshake:inf4ai",
        participant_ref="character:maya",
        attempt_ref="attempt:inf4ai:maya",
        terminal_status="completed",
        payload_digest="digest:inf4ai:maya",
    )
    committed = store.read_stream("session:session:handshake:inf4ai")[-1]
    return store, committed, result


def test_existing_p5_registry_rejects_handshake_event_before_expression_amendment() -> None:
    registry = _registry()
    try:
        registry.require_event(EVENT, 1)
    except ValueError as error:
        assert str(error) == "p5_event_unregistered"
    else:  # pragma: no cover - RED guard
        raise AssertionError("handshake event unexpectedly registered")


def test_actor_private_handshake_event_requires_static_event_schema_registration() -> None:
    from app.gameplay.event_schema_registry import register_inf4ai_p5_actor_private_event_schemas

    registry = EventSchemaRegistry()
    store = GameplayEventStore(event_schema_registry=registry)
    unregistered = store.append_batch(
        {
            "transaction_id": "transaction:inf4ai:schema:unregistered",
            "command_id": "command:inf4ai:schema:unregistered",
            "expected_stream_revisions": {"gameplay:social:shared-experience:character:siming": 0},
            "events": [
                GameplayEvent(
                    event_id="event:inf4ai:schema:unregistered",
                    event_type=EVENT,
                    schema_version=1,
                    stream_id="gameplay:social:shared-experience:character:siming",
                    stream_revision=0,
                    global_sequence=0,
                    transaction_id="transaction:inf4ai:schema:unregistered",
                    command_id="command:inf4ai:schema:unregistered",
                    causation_id="cause:inf4ai:schema",
                    correlation_id="correlation:inf4ai:schema",
                    visibility_policy="actor:character:siming",
                    payload={"event": "schema-only"},
                )
            ],
            "idempotency_record": IdempotencyRecord(
                principal_ref="authority:p5:social",
                idempotency_key="schema:inf4ai:unregistered",
                payload_digest="sha256:schema-unregistered",
            ),
            "result_digest": "sha256:schema-unregistered",
        }
    )
    assert not unregistered.committed
    assert unregistered.failure is not None
    assert unregistered.failure.error_code == "event_schema_unregistered"

    register_inf4ai_p5_actor_private_event_schemas(registry)
    registered = store.append_batch(
        {
            "transaction_id": "transaction:inf4ai:schema:registered",
            "command_id": "command:inf4ai:schema:registered",
            "expected_stream_revisions": {"gameplay:social:shared-experience:character:siming": 0},
            "events": [
                GameplayEvent(
                    event_id="event:inf4ai:schema:registered",
                    event_type=EVENT,
                    schema_version=1,
                    stream_id="gameplay:social:shared-experience:character:siming",
                    stream_revision=0,
                    global_sequence=0,
                    transaction_id="transaction:inf4ai:schema:registered",
                    command_id="command:inf4ai:schema:registered",
                    causation_id="cause:inf4ai:schema",
                    correlation_id="correlation:inf4ai:schema",
                    visibility_policy="actor:character:siming",
                    payload={"event": "schema-only"},
                )
            ],
            "idempotency_record": IdempotencyRecord(
                principal_ref="authority:p5:social",
                idempotency_key="schema:inf4ai:registered",
                payload_digest="sha256:schema-registered",
            ),
            "result_digest": "sha256:schema-registered",
        }
    )
    assert registered.committed


def test_catalog_exposes_only_the_exact_actor_private_handshake_operation() -> None:
    descriptor = next(
        item
        for item in GovernedAuthorityContractCatalog.descriptors()
        if item.descriptor_ref == "descriptor:social-handshake-shared-experience@1"
    )
    assert descriptor == OwnerOperationDescriptor(
        descriptor_ref="descriptor:social-handshake-shared-experience@1",
        descriptor_revision="descriptor:social-handshake-shared-experience@1",
        capability_ref="capability:social-handshake-shared-experience@1",
        outcome_family_ref="outcome:social-handshake-shared-experience-recorded@1",
        allowed_predicate_family_refs=("predicate:embodied-completed-two-party-handshake@1",),
        allowed_proposal_effect_types=("effect:social-handshake-shared-experience-recorded@1",),
    )
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:social-handshake-shared-experience@1",
        contract_kind="contract_admission",
    )
    assert contract.projection_scope == "actor_private"
    assert contract.owner_ref == "authority:p5:social"
    assert contract.event_types == (EVENT,)


def test_actor_private_scope_cannot_be_used_by_another_catalog_operation() -> None:
    try:
        GovernedAuthorityContract(
            contract_ref="inf:other-actor-private@1",
            contract_kind="contract_admission",
            owner_ref="authority:other",
            stream_patterns=("gameplay:other:{character_ref}",),
            event_types=("gameplay.other.recorded",),
            projection_scope="actor_private",
            receipt_reader_ref="GameplayEventStore.append_batch",
            replay_reader_ref="OtherAuthority.view_for",
        )
    except ValueError as error:
        assert "governed_actor_private_scope_unadmitted" in str(error)
    else:  # pragma: no cover - RED guard
        raise AssertionError("actor_private scope was accepted outside INF-4AI")


def test_completed_handshake_writes_two_actor_private_history_events_with_append_receipt() -> None:
    store, committed_event, _result = _completed_handshake()
    authority = SocialFactAuthority(registry=_handshake_registry(), store=store)
    result = authority.record_completed_handshake_shared_experience(
        session_event_id=committed_event.event_id,
        expected_session_revision=committed_event.stream_revision,
        expected_target_revisions=(0, 0),
        command_id="command:inf4ai:shared-experience",
        idempotency_key=(
            f"social:handshake-shared-experience:{committed_event.event_id}:"
            f"{committed_event.stream_revision}:0:0:v1"
        ),
        causation_id=committed_event.event_id,
        correlation_id="correlation:inf4ai",
    )
    assert result.resolution.result_kind == "committed_success"
    assert result.receipt is not None and result.receipt.zero_write is False
    events = [event for event in store.read_events() if event.event_type == EVENT]
    assert len(events) == 2
    assert {event.visibility_policy for event in events} == {
        "actor:character:siming",
        "actor:character:maya",
    }
    assert all(event.payload["session_event_id"] == committed_event.event_id for event in events)
    assert all(event.payload["interaction_kind"] == "handshake" for event in events)
    assert all("confidence" not in event.payload and "observed_at" not in event.payload for event in events)


def test_handshake_shared_experience_rejects_incomplete_source_and_preserves_zero_write() -> None:
    service, store, _bus, _ledger = _service()
    _propose(service, session_id="session:handshake:incomplete")
    source = store.read_stream("session:session:handshake:incomplete")[0]
    authority = SocialFactAuthority(registry=_handshake_registry(), store=store)
    before = store.export_snapshot()
    result = authority.record_completed_handshake_shared_experience(
        session_event_id=source.event_id,
        expected_session_revision=source.stream_revision,
        expected_target_revisions=(0, 0),
        command_id="command:inf4ai:incomplete",
        idempotency_key=f"social:handshake-shared-experience:{source.event_id}:1:0:0:v1",
        causation_id=source.event_id,
        correlation_id="correlation:inf4ai:incomplete",
    )
    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "handshake_shared_experience_source_invalid"
    assert store.export_snapshot() == before


def test_handshake_shared_experience_replays_duplicate_and_rejects_changed_duplicate() -> None:
    store, committed_event, _result = _completed_handshake()
    authority = SocialFactAuthority(registry=_handshake_registry(), store=store)
    request = {
        "session_event_id": committed_event.event_id,
        "expected_session_revision": committed_event.stream_revision,
        "expected_target_revisions": (0, 0),
        "command_id": "command:inf4ai:duplicate",
        "idempotency_key": f"social:handshake-shared-experience:{committed_event.event_id}:7:0:0:v1",
        "causation_id": committed_event.event_id,
        "correlation_id": "correlation:inf4ai:duplicate",
    }
    first = authority.record_completed_handshake_shared_experience(**request)
    before = store.export_snapshot()
    duplicate = authority.record_completed_handshake_shared_experience(**request)
    changed = authority.record_completed_handshake_shared_experience(
        **{**request, "correlation_id": "correlation:inf4ai:changed"}
    )
    assert first.resolution.result_kind == "committed_success"
    assert duplicate.resolution.result_kind == "committed_success"
    assert duplicate.receipt is not None
    assert duplicate.receipt.idempotency_status == "duplicate_replayed"
    assert changed.resolution.result_kind == "rejected_zero_write"
    assert changed.resolution.failure_code == "handshake_shared_experience_idempotency_key_reused"
    assert store.export_snapshot() == before


def test_handshake_shared_experience_is_private_and_checkpoint_tail_replay_is_equal() -> None:
    store, committed_event, _result = _completed_handshake()
    authority = SocialFactAuthority(registry=_handshake_registry(), store=store)
    result = authority.record_completed_handshake_shared_experience(
        session_event_id=committed_event.event_id,
        expected_session_revision=committed_event.stream_revision,
        expected_target_revisions=(0, 0),
        command_id="command:inf4ai:replay",
        idempotency_key=f"social:handshake-shared-experience:{committed_event.event_id}:7:0:0:v1",
        causation_id=committed_event.event_id,
        correlation_id="correlation:inf4ai:replay",
    )
    assert result.resolution.result_kind == "committed_success"
    for participant_ref in ("character:siming", "character:maya"):
        full = authority.handshake_shared_experience_view_for(participant_ref=participant_ref)
        tail = authority.handshake_shared_experience_view_for(
            participant_ref=participant_ref,
            checkpoint_at=committed_event.global_sequence,
        )
        assert full.shared_experience_refs == tail.shared_experience_refs
        assert full.experiences == tail.experiences
        assert full.source_revision_vector == tail.source_revision_vector
        assert full.projection_hash == tail.projection_hash
    assert authority.handshake_shared_experience_view_for(
        participant_ref="character:outsider"
    ).experiences == ()
