import os
import pickle
from threading import RLock

from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingAuditRecord, SimingTickResult
from app.services.authority_event_bus import (
    AuthorityEventBusPort,
    AuthorityRecoveryLedger,
    authority_events_equal,
    _prepared_delivery_snapshot,
)
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_character_dispatch_adapter import (
    SUPPORTED_SIMING_EVENT_TYPES,
    SimingCharacterDispatchAdapter,
)
from app.services.siming_event_consumer import SimingEventConsumer
from app.services import siming_event_consumer
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime
from app.services.siming_heavenly_runtime_support import SimingHeavenlyRuntimeSupport
from app.services.siming_population_capability import default_population_read_set_builder
from app.population_continuity.prepared_frame import native_method, population_frame_scope, unadjusted_population_event, take_population_ingress_snapshot
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle


class SimingEventPipeline:
    _INGRESS_DEDUP_LIMIT = 2

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
        self._ingress_lock = RLock()
        self._handled_events: dict[str, bytes] = {}

    def _handle_prepared_population(self, event, frame) -> None:
        runtime = self._runtime
        support = runtime._heavenly_support if type(runtime) is SimingRuntime else None
        support_native = support is None or (type(support) is SimingHeavenlyRuntimeSupport
            and all(native_method(support, name, function) for name, function in _NATIVE_SUPPORT_METHODS)
            and support._scope_for is _NATIVE_SUPPORT_SCOPE
            and support._is_authority_destruction is _NATIVE_SUPPORT_DESTRUCTION)
        if (type(self) is not SimingEventPipeline or type(runtime) is not SimingRuntime
                or type(self._consumer) is not SimingEventConsumer
                or not all(native_method(self, name, function) for name, function in _NATIVE_PIPELINE_METHODS)
                or not native_method(self._consumer, "handle_event", _NATIVE_CONSUMER)
                or siming_event_consumer.SimingInput is not _NATIVE_SIMING_INPUT
                or _NATIVE_SIMING_INPUT.__init__ is not _NATIVE_SIMING_INPUT_INIT
                or _NATIVE_SIMING_INPUT.__pydantic_validator__ is not _NATIVE_SIMING_INPUT_VALIDATOR
                or not all(native_method(runtime, name, function) for name, function in _NATIVE_RUNTIME_METHODS)
                or runtime._population_read_set_builder is not _NATIVE_POPULATION_BUILDER
                or not support_native or event.event_id in self._handled_events
                or not unadjusted_population_event(event)):
            return self.handle_event(event)
        snapshot = (_prepared_delivery_snapshot(event, self._handle_prepared_population,
            _NATIVE_PREPARED_HANDLER_CODE) if SimingEventPipeline.handle_event.__code__ is _NATIVE_INGRESS_HANDLER_CODE else None)
        with population_frame_scope(event, frame, ingress_snapshot=snapshot):
            return self.handle_event(event)

    def handle_event(self, event: AuthorityEvent) -> None:
        if (
            event.event_type != "population_cadence_event"
            or event.durability != "realtime"
        ):
            self._handle_event(event)
            return
        with self._ingress_lock:
            previous_snapshot = self._handled_events.get(event.event_id)
            if previous_snapshot is not None:
                if not authority_events_equal(
                    pickle.loads(previous_snapshot), event
                ):
                    raise ValueError("siming_event_id_conflict")
                return
            snapshot = take_population_ingress_snapshot(event)
            if snapshot is None:
                snapshot = pickle.dumps(event, protocol=pickle.HIGHEST_PROTOCOL)
            self._handle_event(event)
            self._handled_events[event.event_id] = snapshot
            while len(self._handled_events) > self._INGRESS_DEDUP_LIMIT:
                self._handled_events.pop(next(iter(self._handled_events)))

    def _handle_event(self, event: AuthorityEvent) -> None:
        record_authority_outcome = getattr(
            self._runtime, "record_authority_outcome", None
        )
        if record_authority_outcome is not None:
            record_authority_outcome(event)
        if (
            os.environ.get("SIMING_HEAVENLY_AUTOTEST_SETUP") == "1"
            and not self._setup_event_requires_siming(event)
        ):
            return
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
        self.finish_result(event, result)
        # 冻结域请求必须得到真实 accepted cycle；失败不可进入入口去重缓存，否则 outbox 永远重试空操作。
        if "population_owner_requests" in event.payload and not any(
            audit.audit_id == f"audit_{event.event_id}_population_cycle" and audit.status == "recorded"
            for audit in result.audit_records
        ):
            raise ValueError("population_domain_cycle_unconfirmed")

    def finish_result(self, event: AuthorityEvent, result: SimingTickResult) -> None:
        """完成已接受的结果；不重放 consumer 或 tick 的前置领域写。"""
        for audit in result.audit_records:
            self._audit_writer.record(audit)
        for checkpoint in result.checkpoints:
            self._audit_writer.record_checkpoint(checkpoint)
        if result.read_model is not None:
            self._audit_writer.record_read_model(result.read_model)
        materialized_events = (
            self._producer.materialize_outputs(result.outputs)
            if result.outputs
            else []
        )
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

    @staticmethod
    def _setup_event_requires_siming(event: AuthorityEvent) -> bool:
        payload = event.payload
        if event.event_type == "siming_staging_ack":
            return True
        if event.event_type == "visual_fact_event":
            return payload.get("relation_type") == "actor_observes_object_removal"
        return (
            event.event_type == "esm_result_event"
            and payload.get("result_type") == "object_state_result"
            and payload.get("current_state") == "removed_from_surface"
        )

    def drain_observatory_messages(self) -> list[dict[str, object]]:
        return self._runtime.drain_observatory_messages()

    def ingest_canonical_percept_bundle(self, bundle: CanonicalPerceptBundle):
        result = self._runtime.ingest_canonical_percept_bundle(bundle)
        if result.read_model is not None:
            self._audit_writer.record_read_model(result.read_model)
        return result

    def list_read_models(self, *, room_id: str):
        return self._audit_writer.list_read_models(room_id=room_id)


_NATIVE_PREPARED_HANDLER_CODE = SimingEventPipeline._handle_prepared_population.__code__
_NATIVE_INGRESS_HANDLER_CODE = SimingEventPipeline.handle_event.__code__
_NATIVE_PIPELINE_METHODS = tuple((name, getattr(SimingEventPipeline, name))
    for name in ("handle_event", "_handle_event", "finish_result"))
_NATIVE_CONSUMER = SimingEventConsumer.handle_event
_NATIVE_SIMING_INPUT = siming_event_consumer.SimingInput
_NATIVE_SIMING_INPUT_INIT = _NATIVE_SIMING_INPUT.__init__
_NATIVE_SIMING_INPUT_VALIDATOR = _NATIVE_SIMING_INPUT.__pydantic_validator__
_NATIVE_RUNTIME_METHODS = tuple((name, getattr(SimingRuntime, name))
    for name in ("tick", "_start_tick", "_new_frame", "record_authority_outcome", "reconcile_pending_dispatch"))
_NATIVE_POPULATION_BUILDER = default_population_read_set_builder
_NATIVE_SUPPORT_METHODS = tuple((name, getattr(SimingHeavenlyRuntimeSupport, name))
    for name in ("record_authority_outcome", "plan_authority_outcome", "reconcile_dispatch"))
_NATIVE_SUPPORT_SCOPE = SimingHeavenlyRuntimeSupport._scope_for
_NATIVE_SUPPORT_DESTRUCTION = SimingHeavenlyRuntimeSupport._is_authority_destruction
