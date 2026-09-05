from __future__ import annotations

from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.scripted_mystery_case_runtime import CaseOpenIntent, ScriptedMysteryCaseAuthority


def _authority() -> ScriptedMysteryCaseAuthority:
    return ScriptedMysteryCaseAuthority.create(GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry()))


def test_open_advance_and_outcome_are_projected() -> None:
    authority = _authority()
    opened = authority.open_case(CaseOpenIntent(case_ref=authority.package.content.case_ref, case_revision=authority.package.content.case_revision, command_id="open", idempotency_key="open", causation_id="cause", correlation_id="corr", submitted_at="now"))
    assert opened.committed
    advanced = authority.advance_phase(command_id="advance", idempotency_key="advance", phase_ref="phase:stormnight:investigation@1", expected_revision=1, causation_id="cause", correlation_id="corr")
    assert advanced.committed
    outcome = authority.resolve_outcome(command_id="outcome", idempotency_key="outcome", outcome_kind="case_solved", expected_revision=2, causation_id="cause", correlation_id="corr")
    assert not outcome.committed
    assert outcome.error_code == "case_outcome_prerequisite_missing"
    projection = authority.project()
    assert projection.opened
    assert projection.phase_ref == "phase:stormnight:investigation@1"
    assert projection.terminal_outcome is None


def test_duplicate_and_changed_duplicate_are_fail_closed() -> None:
    authority = _authority()
    intent = CaseOpenIntent(case_ref=authority.package.content.case_ref, case_revision=authority.package.content.case_revision, command_id="open", idempotency_key="open", causation_id="cause", correlation_id="corr", submitted_at="now")
    first = authority.open_case(intent)
    duplicate = authority.open_case(intent)
    assert first.committed and duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    changed = authority.open_case(intent.model_copy(update={"case_revision": "case:changed@1"}))
    assert not changed.committed
    assert changed.error_code == "case_identity_mismatch"
    assert len(authority.store.read_events()) == 1


def test_stale_phase_and_unknown_outcome_are_zero_write() -> None:
    authority = _authority()
    intent = CaseOpenIntent(case_ref=authority.package.content.case_ref, case_revision=authority.package.content.case_revision, command_id="open", idempotency_key="open", causation_id="cause", correlation_id="corr", submitted_at="now")
    authority.open_case(intent)
    stale = authority.advance_phase(command_id="stale", idempotency_key="stale", phase_ref="phase:stormnight:investigation@1", expected_revision=0, causation_id="cause", correlation_id="corr")
    unknown = authority.resolve_outcome(command_id="unknown", idempotency_key="unknown", outcome_kind="not-a-case-outcome", expected_revision=1, causation_id="cause", correlation_id="corr")  # type: ignore[arg-type]
    assert not stale.committed and stale.error_code == "case_revision_stale"
    assert not unknown.committed and unknown.error_code == "case_outcome_unknown"
    assert len(authority.store.read_events()) == 1


def test_full_and_checkpoint_tail_replay_match() -> None:
    authority = _authority()
    intent = CaseOpenIntent(case_ref=authority.package.content.case_ref, case_revision=authority.package.content.case_revision, command_id="open", idempotency_key="open", causation_id="cause", correlation_id="corr", submitted_at="now")
    authority.open_case(intent)
    authority.advance_phase(command_id="advance", idempotency_key="advance", phase_ref="phase:stormnight:investigation@1", expected_revision=1, causation_id="cause", correlation_id="corr")
    checkpoint = authority.create_checkpoint(authority.store.read_events())
    authority.advance_phase(command_id="advance-2", idempotency_key="advance-2", phase_ref="phase:stormnight:storm-night@1", expected_revision=2, causation_id="cause", correlation_id="corr")
    full = authority.replay_full()
    tail = authority.replay_checkpoint_tail(checkpoint)
    assert full.succeeded and tail.succeeded
    assert full.projection_hash == tail.projection_hash


def test_statement_and_accusation_use_case_owner_boundary() -> None:
    authority = _authority()
    content = authority.package.content
    opened = authority.open_case(CaseOpenIntent(case_ref=content.case_ref, case_revision=content.case_revision, command_id="open", idempotency_key="open", causation_id="cause", correlation_id="corr", submitted_at="now"))
    assert opened.committed
    statement = content.statement_definitions[0]
    recorded = authority.record_statement(statement_ref=statement.statement_ref, speaker_ref=statement.speaker_ref, target_ref=statement.target_ref, mode=statement.allowed_modes[0], command_id="statement", idempotency_key="statement", expected_revision=1, causation_id="cause", correlation_id="corr")
    assert recorded.committed
    context = __import__("app.gameplay.p5.scripted_mystery_evidence", fromlist=["ScriptedMysteryEvidenceAdapter"]).ScriptedMysteryEvidenceAdapter(content=content).build_turn_context(authority.project(), statement.speaker_ref)
    evidence = tuple(sorted((context.public_fact_refs[1], context.private_fact_refs[0])))
    accusation = authority.submit_accusation(accuser_ref=statement.speaker_ref, target_ref=statement.target_ref, evidence_refs=evidence, command_id="accusation", idempotency_key="accusation", expected_revision=2, causation_id="cause", correlation_id="corr")
    assert accusation.committed
    projection = authority.project()
    assert statement.statement_ref in projection.statement_refs
    assert accusation.event_id in projection.accusation_refs
