from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import AuthorityEventBusPort
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_character_dispatch_adapter import (
    SUPPORTED_SIMING_EVENT_TYPES,
    SimingCharacterDispatchAdapter,
)
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime


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
        published_events = self._producer.publish_outputs(result.outputs)
        if self._character_dispatch_adapter is None:
            return
        for published_event in published_events:
            if published_event.correlation_id != event.correlation_id:
                continue
            if published_event.event_type not in SUPPORTED_SIMING_EVENT_TYPES:
                continue
            self._character_dispatch_adapter.dispatch(published_event)
