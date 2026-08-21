from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingAuditRecord
from app.services.authority_event_bus import (
    AuthorityEventBusPort,
    AuthorityRecoveryLedger,
)
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_character_dispatch_adapter import (
    SUPPORTED_SIMING_EVENT_TYPES,
    SimingCharacterDispatchAdapter,
)
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle


class SimingEventPipeline:
    def __init__(
        self,
        *,
        bus: AuthorityEventBusPort,
        consumer: SimingEventConsumer,
        runtime: SimingRuntime,
        producer: SimingEventProducer,
        audit_writer: SimingAuditWriter,
        character_dispatch_adapter: SimingCharacterDispatchAdapter | None = None,
    ) -> None:
        self._bus = bus
        self._consumer = consumer
        self._runtime = runtime
        self._producer = producer
        self._audit_writer = audit_writer
        self._character_dispatch_adapter = character_dispatch_adapter

    def handle_event(self, event: AuthorityEvent) -> None:
        record_authority_outcome = getattr(
            self._runtime, "record_authority_outcome", None
        )
        if record_authority_outcome is not None:
            record_authority_outcome(event)
        reconcile_pending_dispatch = getattr(
            self._runtime, "reconcile_pending_dispatch", None
        )
        if reconcile_pending_dispatch is not None:
            try:
                authority_ledger: AuthorityRecoveryLedger | None = (
                    self._bus.authority_recovery_ledger()
                )
            except Exception:
                authority_ledger = None
            recovery_state = reconcile_pending_dispatch(
                event, authority_ledger=authority_ledger
            )
            if recovery_state == "authority_unknown":
                self._audit_writer.record(
                    SimingAuditRecord(
                        audit_id=f"audit_{event.event_id}_dispatch_recovery_unknown",
                        room_id=event.room_id,
                        correlation_id=event.correlation_id,
                        causation_id=event.event_id,
                        source_event_id=event.event_id,
                        status="no_action",
                        reason="dispatch_recovery_authority_unknown",
                    )
                )
                return
        inputs = self._consumer.handle_event(event)
        if not inputs:
            return
        result = self._runtime.tick(inputs)
        for audit in result.audit_records:
            self._audit_writer.record(audit)
        for checkpoint in result.checkpoints:
            self._audit_writer.record_checkpoint(checkpoint)
        if result.read_model is not None:
            self._audit_writer.record_read_model(result.read_model)
        materialized_events = self._producer.materialize_outputs(result.outputs)
        graph_dispatches = [
            published_event
            for output, published_event in zip(result.outputs, materialized_events)
            if (
                output.output_type == "dispatch_intent"
                and output.payload.get("siming_graph_owned") is True
            )
        ]
        record_dispatches_unconfirmed = getattr(
            self._runtime, "record_dispatches_unconfirmed", None
        )
        if record_dispatches_unconfirmed is not None and graph_dispatches:
            record_dispatches_unconfirmed(event, graph_dispatches)
        elif record_dispatches_unconfirmed is None:
            ensure_dispatches_unpublished = getattr(
                self._runtime, "ensure_dispatches_unpublished", None
            )
            if ensure_dispatches_unpublished is not None:
                ensure_dispatches_unpublished(event, result.outputs)
        published_events = self._producer.publish_events(materialized_events)
        published_dispatches = [
            published_event
            for output, published_event in zip(result.outputs, published_events)
            if output.output_type == "dispatch_intent"
        ]
        record_published_dispatches = getattr(
            self._runtime, "record_published_dispatches", None
        )
        if record_published_dispatches is not None:
            record_published_dispatches(event, published_dispatches)
        if self._character_dispatch_adapter is None:
            return
        for published_event in published_events:
            if published_event.correlation_id != event.correlation_id:
                continue
            if published_event.event_type not in SUPPORTED_SIMING_EVENT_TYPES:
                continue
            self._character_dispatch_adapter.dispatch(published_event)

    def drain_observatory_messages(self) -> list[dict[str, object]]:
        return self._runtime.drain_observatory_messages()

    def ingest_canonical_percept_bundle(self, bundle: CanonicalPerceptBundle):
        result = self._runtime.ingest_canonical_percept_bundle(bundle)
        if result.read_model is not None:
            self._audit_writer.record_read_model(result.read_model)
        return result

    def list_read_models(self, *, room_id: str):
        return self._audit_writer.list_read_models(room_id=room_id)
