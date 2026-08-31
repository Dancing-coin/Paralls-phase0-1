from __future__ import annotations

import pytest

from app.gameplay.event_schema_registry import EventSchemaRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, OwnerOperationDescriptor
from app.gameplay.p5.registry import (
    P5EventCatalogEntry,
    P5EventNamespace,
    P5PolicyRegistry,
    P5SchemaPin,
    P5StreamGrammar,
)
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from test_inf4am_public_milling_notice import _activity
from test_inf2al_public_milling_session import _economy_setup
from test_p5_social_knowledge import _registry


EVENT = "gameplay.social.public_milling_notice_acknowledged"
SCHEMA = "schema:p5:social:public-milling-notice-acknowledged"
GRAMMAR = "grammar:p5:public-milling-notice-acknowledgment"
CATALOG = "inf:social-public-milling-notice-acknowledgment@1"
PROVIDER = "organization:district-milling-cooperative"


def _social_registry() -> P5PolicyRegistry:
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
        registry_revision="registry:p5:social:v3",
        trusted_evidence_providers=base.trusted_evidence_providers,
        owner_adapter_allowlist=(owner,),
        quest_packages=base.quest_packages,
        ruleset_revisions=base.ruleset_revisions,
        schema_pins=(
            *base.schema_pins,
            P5SchemaPin(
                schema_ref=SCHEMA,
                schema_version=1,
                schema_digest="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
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
                pattern=r"^gameplay:social:public-milling-notice-acknowledgment:.+$",
            ),
        ),
    )


def _notice() -> tuple[GameplayEventStore, object]:
    store, _economy, fulfilled = _economy_setup()
    activity = _activity(store)
    from app.gameplay.organization_government_runtime import GovernmentAuthority

    result = GovernmentAuthority(store=store).record_public_milling_notice(
        activity_event_id=activity.event_id,
        expected_activity_revision=activity.stream_revision,
        expected_government_revision=0,
        command_id="inf4ao:notice",
        idempotency_key=f"government:public-milling-notice:{activity.event_id}:{activity.stream_revision}:0:v1",
        causation_id=activity.event_id,
        correlation_id="corr:inf4ao:notice",
        submitted_at="2026-08-28T00:30:00Z",
    )
    assert result.committed
    return store, store.get_event(result.committed_event_ids[0])


def _request(store: GameplayEventStore, notice: object, **updates: object) -> dict[str, object]:
    receiver = "org:mill:1"
    target_revisions = updates.pop("expected_target_revisions", (0, 0))
    explicit_idempotency_key = updates.pop("idempotency_key", None)
    values: dict[str, object] = {
        "notice_event_id": notice.event_id,
        "expected_notice_revision": notice.stream_revision,
        "expected_target_revisions": target_revisions,
        "command_id": "inf4ao:ack",
        "idempotency_key": explicit_idempotency_key or "pending",
        "causation_id": notice.event_id,
        "correlation_id": "corr:inf4ao:ack",
    }
    values.update(updates)
    if explicit_idempotency_key is None:
        values["idempotency_key"] = (
            f"social:public-milling-notice-ack:{notice.event_id}:{notice.stream_revision}:"
            f"{target_revisions[0]}:{target_revisions[1]}:v1"
        )
    return values


def test_inf4ao_registers_one_exact_actor_private_schema_and_catalog_row() -> None:
    registry = _social_registry()
    entry = registry.require_event(EVENT, 1)
    assert entry.schema_ref == SCHEMA
    assert entry.stream_grammar_ref == GRAMMAR
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref=CATALOG,
        contract_kind="contract_admission",
    )
    assert contract.owner_ref == "authority:p5:social"
    assert contract.projection_scope == "actor_private"
    assert contract.event_types == (EVENT,)
    descriptor = next(item for item in GovernedAuthorityContractCatalog.descriptors() if item.descriptor_ref == "descriptor:social-public-milling-notice-acknowledgment@1")
    assert descriptor == OwnerOperationDescriptor(
        descriptor_ref="descriptor:social-public-milling-notice-acknowledgment@1",
        descriptor_revision="descriptor:social-public-milling-notice-acknowledgment@1",
        capability_ref="capability:social-public-milling-notice-acknowledgment@1",
        outcome_family_ref="outcome:social-public-milling-notice-acknowledged@1",
        allowed_predicate_family_refs=("predicate:government-public-milling-notice-recorded@1",),
        allowed_proposal_effect_types=("effect:social-public-milling-notice-acknowledged@1",),
    )


def test_inf4ao_event_requires_static_schema_registration() -> None:
    registry = EventSchemaRegistry()
    store = GameplayEventStore(event_schema_registry=registry)
    from app.gameplay.models import GameplayEvent, IdempotencyRecord

    result = store.append_batch(
        {
            "transaction_id": "tx:inf4ao:schema",
            "command_id": "cmd:inf4ao:schema",
            "expected_stream_revisions": {"gameplay:social:public-milling-notice-acknowledgment:org:mill:1": 0},
            "events": [
                GameplayEvent(
                    event_id="event:inf4ao:schema",
                    event_type=EVENT,
                    schema_version=1,
                    stream_id="gameplay:social:public-milling-notice-acknowledgment:org:mill:1",
                    stream_revision=0,
                    global_sequence=0,
                    transaction_id="tx:inf4ao:schema",
                    command_id="cmd:inf4ao:schema",
                    causation_id="cause:inf4ao:schema",
                    correlation_id="corr:inf4ao:schema",
                    visibility_policy="actor:org:mill:1",
                    payload={},
                )
            ],
            "idempotency_record": IdempotencyRecord(
                principal_ref="authority:p5:social",
                idempotency_key="idempotency:inf4ao:schema",
                payload_digest="sha256:inf4ao",
            ),
            "result_digest": "sha256:inf4ao",
        }
    )
    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "event_schema_unregistered"


def test_inf4ao_records_exactly_two_actor_private_acknowledgments() -> None:
    store, notice = _notice()
    authority = SocialFactAuthority(registry=_social_registry(), store=store)
    result = authority.record_public_milling_notice_social_acknowledgment(**_request(store, notice))
    assert result.resolution.result_kind == "committed_success"
    assert result.receipt is not None and result.receipt.zero_write is False
    events = [event for event in store.read_events() if event.event_type == EVENT]
    assert len(events) == 2
    assert {event.payload["participant_ref"] for event in events} == {
        PROVIDER,
        "org:mill:1",
    }
    assert {event.visibility_policy for event in events} == {
        f"actor:{PROVIDER}",
        "actor:org:mill:1",
    }
    assert all(event.payload["source_notice_event_id"] == notice.event_id for event in events)
    assert all(event.payload["status"] == "acknowledged" for event in events)
    assert all("party_refs" not in event.payload for event in events)


def test_inf4ao_duplicate_and_changed_duplicate_do_not_write() -> None:
    store, notice = _notice()
    authority = SocialFactAuthority(registry=_social_registry(), store=store)
    request = _request(store, notice)
    first = authority.record_public_milling_notice_social_acknowledgment(**request)
    assert first.resolution.result_kind == "committed_success"
    before = store.export_snapshot()
    duplicate = authority.record_public_milling_notice_social_acknowledgment(**request)
    changed = authority.record_public_milling_notice_social_acknowledgment(
        **_request(store, notice, correlation_id="corr:inf4ao:changed")
    )
    assert duplicate.resolution.result_kind == "committed_success"
    assert duplicate.receipt is not None and duplicate.receipt.idempotency_status == "duplicate_replayed"
    assert changed.resolution.result_kind == "rejected_zero_write"
    assert changed.resolution.failure_code == "public_milling_notice_social_acknowledgment_idempotency_key_reused"
    assert store.export_snapshot() == before


def test_inf4ao_unknown_private_stale_and_caller_selected_fields_are_zero_write() -> None:
    store, notice = _notice()
    authority = SocialFactAuthority(registry=_social_registry(), store=store)
    before = store.export_snapshot()
    unknown = authority.record_public_milling_notice_social_acknowledgment(
        **_request(store, notice, notice_event_id="event:missing")
    )
    assert unknown.resolution.failure_code == "public_milling_notice_social_acknowledgment_source_missing"
    assert store.export_snapshot() == before

    private = notice.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    store._events_by_id[notice.event_id] = private
    private_result = authority.record_public_milling_notice_social_acknowledgment(**_request(store, private))
    assert private_result.resolution.failure_code == "public_milling_notice_social_acknowledgment_source_private"
    store._events_by_id[notice.event_id] = notice
    assert store.export_snapshot() == before

    store._stream_heads[notice.stream_id] = notice.stream_revision + 1
    stale = authority.record_public_milling_notice_social_acknowledgment(
        **_request(store, notice, expected_notice_revision=notice.stream_revision)
    )
    assert stale.resolution.failure_code == "public_milling_notice_social_acknowledgment_source_stale"
    store._stream_heads[notice.stream_id] = notice.stream_revision
    selected = authority.record_public_milling_notice_social_acknowledgment(
        **_request(store, notice, idempotency_key="caller-selected")
    )
    assert selected.resolution.failure_code == "public_milling_notice_social_acknowledgment_idempotency_key_invalid"
    assert store.export_snapshot() == before


def test_inf4ao_multiple_or_conflicting_source_party_bindings_are_zero_write() -> None:
    store, notice = _notice()
    authority = SocialFactAuthority(registry=_social_registry(), store=store)
    created_id = notice.payload["source_contract_created_event_id"]
    created = store.get_event(created_id)
    before = store.export_snapshot()

    multiple = created.model_copy(
        update={"payload": {**created.payload, "party_refs": [PROVIDER, "org:mill:1", "org:third-party"]}},
        deep=True,
    )
    store._events_by_id[created.event_id] = multiple
    rejected = authority.record_public_milling_notice_social_acknowledgment(**_request(store, notice))
    assert rejected.resolution.failure_code == "public_milling_notice_social_acknowledgment_party_binding_invalid"
    store._events_by_id[created.event_id] = created

    conflict = created.model_copy(
        update={"payload": {**created.payload, "party_refs": [PROVIDER, "org:wrong"]}},
        deep=True,
    )
    store._events_by_id[created.event_id] = conflict
    rejected = authority.record_public_milling_notice_social_acknowledgment(**_request(store, notice))
    assert rejected.resolution.failure_code == "public_milling_notice_social_acknowledgment_binding_conflict"
    store._events_by_id[created.event_id] = created
    assert store.export_snapshot() == before


def test_inf4ao_full_and_checkpoint_tail_replay_match_and_outsider_is_empty() -> None:
    store, notice = _notice()
    authority = SocialFactAuthority(registry=_social_registry(), store=store)
    result = authority.record_public_milling_notice_social_acknowledgment(**_request(store, notice))
    assert result.resolution.result_kind == "committed_success"
    for participant in (PROVIDER, "org:mill:1"):
        full = authority.public_milling_notice_social_acknowledgment_view_for(participant_ref=participant)
        tail = authority.public_milling_notice_social_acknowledgment_view_for(
            participant_ref=participant,
            checkpoint_at=notice.global_sequence,
        )
        assert full == tail
        assert len(full.acknowledgments) == 1
    assert authority.public_milling_notice_social_acknowledgment_view_for(
        participant_ref="org:outsider"
    ).acknowledgments == ()


def test_inf4ao_replay_rejects_forged_source_provenance() -> None:
    store, notice = _notice()
    authority = SocialFactAuthority(registry=_social_registry(), store=store)
    result = authority.record_public_milling_notice_social_acknowledgment(**_request(store, notice))
    assert result.resolution.result_kind == "committed_success"
    ack = next(event for event in store.read_events() if event.event_type == EVENT)
    forged = ack.model_copy(
        update={"payload": {**ack.payload, "source_notice_event_id": "event:forged"}},
        deep=True,
    )
    store._events_by_id[ack.event_id] = forged
    store._events = [forged if event.event_id == ack.event_id else event for event in store._events]
    with pytest.raises(ValueError, match="public_milling_notice_social_acknowledgment_replay_invalid"):
        authority.public_milling_notice_social_acknowledgment_view_for(
            participant_ref=str(ack.payload["participant_ref"])
        )
