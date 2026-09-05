from __future__ import annotations

from app.gameplay.p5.scripted_mystery_case_runtime import CaseOpenIntent, ScriptedMysteryCaseAuthority
from app.gameplay.models import ProjectionCheckpoint
from app.gameplay.p5.scripted_mystery_case_package import load_stormnight_case_package
from app.gameplay.event_store import GameplayEventStore
import pytest


def test_all_four_terminal_outcomes_are_package_admitted() -> None:
    package = load_stormnight_case_package()
    assert {item.outcome_kind for item in package.content.outcome_definitions} == {"case_solved", "false_accusation", "culprit_escaped", "investigator_captured"}


def test_case_full_replay_rejects_tampered_package_pin() -> None:
    authority = ScriptedMysteryCaseAuthority.create(GameplayEventStore())
    result = authority.open_case(CaseOpenIntent(case_ref=authority.package.content.case_ref, case_revision=authority.package.content.case_revision, command_id="open", idempotency_key="open", causation_id="cause", correlation_id="corr", submitted_at="now"))
    assert result.committed
    checkpoint = authority.create_checkpoint(authority.store.read_events())
    checkpoint = checkpoint.model_copy(update={"projection_hash": "sha256:" + "f" * 64}, deep=True)
    result = authority.replay_checkpoint_tail(checkpoint)
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_code == "case_checkpoint_mismatch"
