from importlib import import_module


def test_backend_layer_packages_exist() -> None:
    assert import_module("app.l1") is not None
    assert import_module("app.l1.esm") is not None
    assert import_module("app.l2") is not None
    assert import_module("app.l2.character_agent") is not None
    assert import_module("app.l2.siming") is not None
    assert import_module("app.l3") is not None
    assert import_module("app.l4") is not None
    assert import_module("app.l5") is not None
    assert import_module("app.l6") is not None
    assert import_module("app.l6.authority_bus") is not None
    assert import_module("app.l6.perception_chain") is not None
    assert import_module("app.l6.replay_audit") is not None


def test_contract_entrypoints_exist() -> None:
    from app.contracts.l1.action_request import ActionRequest
    from app.contracts.l1.execution_ack import ExecutionAck
    from app.contracts.l1.presentation_command import PresentationCommand
    from app.contracts.l1.world_execution_result import WorldExecutionResult
    from app.contracts.l6.envelope import EnvelopeContract
    from app.contracts.l6.raw_fact import RawFactContract
    from app.contracts.l6.candidate_percept import CandidatePerceptContract
    from app.contracts.l6.character_perceived import CharacterPerceivedContract

    assert ActionRequest.__name__ == "ActionRequest"
    assert ExecutionAck.__name__ == "ExecutionAck"
    assert PresentationCommand.__name__ == "PresentationCommand"
    assert WorldExecutionResult.__name__ == "WorldExecutionResult"
    assert EnvelopeContract.__name__ == "EnvelopeContract"
    assert RawFactContract.__name__ == "RawFactContract"
    assert CandidatePerceptContract.__name__ == "CandidatePerceptContract"
    assert CharacterPerceivedContract.__name__ == "CharacterPerceivedContract"


def test_merge_ready_service_entrypoints_resolve_current_implementations() -> None:
    from app.l1.esm.service import ESMServiceEntry
    from app.l2.character_agent.service import CharacterServiceEntry
    from app.l2.siming.service import SimingServiceEntry
    from app.l6.authority_bus.router import handle_envelope_entry
    from app.l6.perception_chain.candidate_compiler import compile_candidate_percepts_entry
    from app.l6.perception_chain.per_character_filter import filter_candidate_for_actor_entry

    assert ESMServiceEntry.__name__ == "ESMService"
    assert CharacterServiceEntry.__name__ == "CharacterService"
    assert SimingServiceEntry.__name__ == "SimingService"
    assert callable(handle_envelope_entry)
    assert callable(compile_candidate_percepts_entry)
    assert callable(filter_candidate_for_actor_entry)


def test_replay_audit_entrypoints_resolve_current_implementations() -> None:
    from app.l6.replay_audit.debug_stream import debug_stream_entry
    from app.l6.replay_audit.event_trace import EventTraceServiceEntry
    from app.l6.replay_audit.verification_audit import VerificationAuditEntry

    assert hasattr(debug_stream_entry, "publish")
    assert EventTraceServiceEntry.__name__ == "EventTraceService"
    assert callable(VerificationAuditEntry.evaluate_phase0_audit)
    assert callable(VerificationAuditEntry.evaluate_phase1_slice_audit)
