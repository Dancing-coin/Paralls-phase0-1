"""Run against A's L5 code with B's Information code and pack overlaid."""

from pathlib import Path

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.information_runtime import InformationAuthority
from app.gameplay.l5_dispatch_runtime import (
    L5ReactionDispatcher,
    TrustedGameplayCommandGateway,
)
from app.gameplay.rule_pack_validator import load_pack
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from test_siege_information_runtime import _store


COMMAND = "information.update_knowledge"
REPORT_INPUT = "fact:information:siege:report"
KNOWLEDGE_OUTPUT = "fact:information:siege:report_knowledge"
DELIVERED = "gameplay.social.delivery_recorded@2"
UPDATED = "gameplay.information.knowledge_updated@1"


def test_committed_delivery_dispatches_information_reaction():
    store, delivery_id = _store()
    authority = InformationAuthority(store=store)
    delivery = store.get_event(delivery_id)
    outputs = {COMMAND: {KNOWLEDGE_OUTPUT}}
    pack = load_pack(
        Path.cwd() / "packs" / "county_siege_information",
        handlers={},
        owner_domains={"Information": "information"},
        command_fact_outputs=outputs,
    )
    assert pack.registry.facts[KNOWLEDGE_OUTPUT].owner_ref == "Information"
    assert pack.registry.facts[KNOWLEDGE_OUTPUT].visibility["class"] == "private"

    report_id = delivery.payload["source_event_id"]

    def fact_type_for(event):
        # The probe admits one fixture report. Production must resolve its own report source.
        if event.event_type == DELIVERED and event.payload.get("source_event_id") == report_id:
            return REPORT_INPUT
        return None

    def update_from_committed_delivery(command):
        return authority.update_from_delivery(
            delivery=command.trigger_event,
            world_now=16,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )

    gateway = TrustedGameplayCommandGateway(
        handlers={COMMAND: update_from_committed_delivery},
        command_fact_outputs=outputs,
    )
    l5 = L5ReactionDispatcher(
        reactions=tuple(pack.reactions.values()),
        gateway=gateway,
        fact_type_for=fact_type_for,
    )
    bus = InMemoryAuthorityEventBus()
    publications = []
    bus.subscribe(UPDATED, publications.append)
    outbox = GameplayOutboxDispatcher(
        store=store, bus=bus, after_transaction_dispatched=l5.after_transaction_dispatched
    )

    assert not store.read_events(event_type=UPDATED)
    assert outbox.dispatch_pending().failed_count == 0
    output, = store.read_events(event_type=UPDATED)
    assert output.causation_id == delivery_id
    assert output.payload["known_at_world_tick"] == 15
    assert output.visibility_policy == "actor:character:recipient"

    assert outbox.dispatch_pending().failed_count == 0
    publication, = publications
    assert publication.routing.audience_mode == "actor:character:recipient"

    receipt, = l5.after_transaction_dispatched(store.get_transaction(delivery.transaction_id))
    assert receipt.append_result.idempotency_status == "duplicate_replayed"
    assert receipt.append_result.committed_event_ids == [output.event_id]
