from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import AuthorityEventBusPort
from app.services.siming_audit_writer import SimingAuditWriter
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
    ) -> None:
        self._bus = bus
        self._consumer = consumer
        self._runtime = runtime
        self._producer = producer
        self._audit_writer = audit_writer

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
        self._producer.publish_outputs(result.outputs)
