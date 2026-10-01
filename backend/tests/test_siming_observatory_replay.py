from types import SimpleNamespace

from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_admission import SimingAdmissionService
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_coordinator import SimingCoordinator
from app.services.siming_runtime import SimingRuntime


def _coordinator():
    graph = InMemoryHeavenlyGraphAdapter()
    runtime = SimingRuntime()
    pipeline = SimpleNamespace(_audit_writer=SimingAuditWriter())
    return SimingCoordinator(
        runtime=runtime,
        admissions=SimingAdmissionService(SimingHeavenlyMemoryService(graph)),
        graph=graph,
        invalidation_reader=lambda _: None,
        output_pipeline=pipeline,
    )


def test_durable_observatory_bundle_is_restored_once_after_apply():
    coordinator = _coordinator()
    message = {
        "message_type": "siming_debug_event",
        "payload": {"stage": "intervention_decision", "summary": "restored"},
    }
    payload = {"audits": [], "checkpoints": [], "read_model": None, "observatory": [message]}

    coordinator._apply_audits(payload)
    assert coordinator.runtime.drain_observatory_messages() == [message]

    coordinator._apply_audits(payload)
    assert coordinator.runtime.drain_observatory_messages() == []


def test_generated_observatory_message_can_repeat_after_previous_delivery():
    runtime = SimingRuntime()
    message = {
        "message_type": "siming_debug_event",
        "payload": {"stage": "intervention_decision", "summary": "generated"},
    }

    runtime._queue_observatory_message(message)
    assert runtime.drain_observatory_messages() == [message]

    runtime._queue_observatory_message(message)
    assert runtime.drain_observatory_messages() == [message]
