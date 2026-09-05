from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.p5.scripted_mystery_content import (
    CaseContentAdmissionResult,
    PrivateKnowledgeSet,
    ScriptedMysteryCaseContent,
    stormnight_case_content,
)


def test_stormnight_fixture_meets_case_shape_and_provenance() -> None:
    content = stormnight_case_content()
    assert len(content.actor_refs) == 4
    assert len(content.clue_definitions) == 10
    assert len(content.private_knowledge_sets) == 4
    assert [phase.ordinal for phase in content.phase_definitions] == [0, 1, 2]
    assert {outcome.outcome_kind for outcome in content.outcome_definitions} == {
        "case_solved", "false_accusation", "culprit_escaped", "investigator_captured"
    }
    assert "source text" in content.provenance_note


def test_content_admission_requires_registered_graph_and_predicates() -> None:
    content = stormnight_case_content()
    rejected = CaseContentAdmissionResult.admit(
        content,
        admitted_action_graph_refs=(),
        admitted_predicate_refs=(),
    )
    assert not rejected.accepted
    assert rejected.error_code == "mystery_case_action_graph_unknown"
    accepted = CaseContentAdmissionResult.admit(
        content,
        admitted_action_graph_refs=content.action_graph_refs,
        admitted_predicate_refs=(
            "predicate:stormnight:inspect@1",
            "predicate:stormnight:phase-transition@1",
        ),
    )
    assert accepted.accepted
    assert accepted.content_digest and accepted.content_digest.startswith("sha256:")


def test_content_rejects_private_knowledge_for_unknown_actor_or_fact() -> None:
    payload = stormnight_case_content().model_dump(mode="python")
    payload["private_knowledge_sets"] = [
        PrivateKnowledgeSet(
            knowledge_ref="knowledge:stormnight:bad@1",
            actor_ref="character:unknown@1",
            fact_refs=("fact:stormnight:01@1",),
            permitted_statement_refs=("statement:stormnight:01@1",),
        ).model_dump(mode="python")
    ]
    with pytest.raises(ValidationError, match="mystery_case_private_truth_invalid"):
        ScriptedMysteryCaseContent.model_validate(payload)


def test_content_rejects_extra_fields_and_noncanonical_arrays() -> None:
    payload = stormnight_case_content().model_dump(mode="python")
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        ScriptedMysteryCaseContent.model_validate(payload)

    payload = stormnight_case_content().model_dump(mode="python")
    payload["actor_refs"] = tuple(reversed(payload["actor_refs"]))
    with pytest.raises(ValidationError, match="mystery_case_array_not_canonical"):
        ScriptedMysteryCaseContent.model_validate(payload)


def test_private_knowledge_arrays_are_canonical_and_frozen() -> None:
    with pytest.raises(ValidationError, match="mystery_private_knowledge_order_invalid"):
        PrivateKnowledgeSet(
            knowledge_ref="knowledge:stormnight:actor@1",
            actor_ref="character:stormnight@1",
            fact_refs=("fact:z@1", "fact:a@1"),
        )
    knowledge = PrivateKnowledgeSet(
        knowledge_ref="knowledge:stormnight:actor@1",
        actor_ref="character:stormnight@1",
        fact_refs=("fact:a@1",),
    )
    with pytest.raises(ValidationError):
        knowledge.knowledge_ref = "changed"  # type: ignore[misc]
