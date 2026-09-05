"""Strict content contracts for the Stormnight scripted-mystery case."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable, Literal, Mapping

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel


def _versioned(value: str) -> bool:
    return ":" in value and "@" in value and not value.endswith("@")


def _ordered(values: Iterable[str]) -> bool:
    values = tuple(values)
    return len(set(values)) == len(values) and values == tuple(sorted(values))


class CaseTruthFact(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_ref: str = Field(min_length=1)
    fact_kind: Literal["scene", "identity", "causal", "possession", "timeline", "relationship"]
    subject_refs: tuple[str, ...] = Field(min_length=1)
    value_ref: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    visibility: Literal["project", "authority_only"] = "project"

    @model_validator(mode="after")
    def validate_refs(self) -> "CaseTruthFact":
        if not _versioned(self.fact_ref) or not _ordered(self.subject_refs) or not _versioned(self.source_ref):
            raise ValueError("mystery_truth_ref_or_order_invalid")
        return self


class PrivateKnowledgeSet(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    knowledge_ref: str = Field(min_length=1)
    actor_ref: str = Field(pattern=r"^character:")
    fact_refs: tuple[str, ...] = ()
    belief_refs: tuple[str, ...] = ()
    permitted_statement_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_refs(self) -> "PrivateKnowledgeSet":
        if not _versioned(self.knowledge_ref) or not _ordered(self.fact_refs) or not _ordered(self.belief_refs) or not _ordered(self.permitted_statement_refs):
            raise ValueError("mystery_private_knowledge_order_invalid")
        return self


class ClueDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    clue_ref: str = Field(min_length=1)
    location_ref: str = Field(min_length=1)
    evidence_kind_ref: str = Field(min_length=1)
    reveals_fact_refs: tuple[str, ...] = ()
    discovery_predicate_refs: tuple[str, ...] = Field(min_length=1)
    custody_required: bool = True

    @model_validator(mode="after")
    def validate_refs(self) -> "ClueDefinition":
        if not _versioned(self.clue_ref) or not _versioned(self.location_ref) or not _versioned(self.evidence_kind_ref):
            raise ValueError("mystery_clue_ref_invalid")
        if not _ordered(self.reveals_fact_refs) or not _ordered(self.discovery_predicate_refs):
            raise ValueError("mystery_clue_order_invalid")
        return self


class StatementDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    statement_ref: str = Field(min_length=1)
    speaker_ref: str = Field(pattern=r"^character:")
    target_ref: str = Field(min_length=1)
    truth_fact_refs: tuple[str, ...] = ()
    visibility: Literal["project", "actor_private"]
    allowed_modes: tuple[Literal["reveal", "withhold", "mislead", "deny"], ...] = Field(min_length=1)
    policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_refs(self) -> "StatementDefinition":
        if not _versioned(self.statement_ref) or not _ordered(self.truth_fact_refs) or not _versioned(self.policy_ref):
            raise ValueError("mystery_statement_ref_invalid")
        if tuple(self.allowed_modes) != tuple(sorted(self.allowed_modes)):
            raise ValueError("mystery_statement_modes_not_canonical")
        return self


class CasePhaseDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    phase_ref: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    action_graph_refs: tuple[str, ...] = ()
    objective_refs: tuple[str, ...] = ()
    transition_predicate_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_refs(self) -> "CasePhaseDefinition":
        if not _versioned(self.phase_ref) or not _ordered(self.action_graph_refs) or not _ordered(self.objective_refs) or not _ordered(self.transition_predicate_refs):
            raise ValueError("mystery_phase_ref_or_order_invalid")
        return self


class CaseOutcomeDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome_ref: str = Field(min_length=1)
    outcome_kind: Literal["case_solved", "false_accusation", "culprit_escaped", "investigator_captured"]
    required_fact_refs: tuple[str, ...] = ()
    terminal: bool = True
    policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_refs(self) -> "CaseOutcomeDefinition":
        if not _versioned(self.outcome_ref) or not _ordered(self.required_fact_refs) or not _versioned(self.policy_ref):
            raise ValueError("mystery_outcome_ref_invalid")
        if not self.terminal:
            raise ValueError("mystery_outcome_must_be_terminal")
        return self


class ScriptedMysteryCaseContent(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_ref: str = Field(min_length=1)
    case_revision: str = Field(min_length=1)
    package_ref: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    location_ref: str = Field(min_length=1)
    actor_refs: tuple[str, ...] = Field(min_length=1)
    culprit_actor_ref: str = Field(pattern=r"^character:")
    role_assignments: Mapping[str, str]
    truth_facts: tuple[CaseTruthFact, ...] = Field(min_length=1)
    private_knowledge_sets: tuple[PrivateKnowledgeSet, ...] = Field(min_length=1)
    clue_definitions: tuple[ClueDefinition, ...] = Field(min_length=1)
    statement_definitions: tuple[StatementDefinition, ...] = Field(min_length=1)
    phase_definitions: tuple[CasePhaseDefinition, ...] = Field(min_length=1)
    outcome_definitions: tuple[CaseOutcomeDefinition, ...] = Field(min_length=1)
    action_graph_refs: tuple[str, ...] = Field(min_length=1)
    presentation_refs: tuple[str, ...] = Field(min_length=1)
    policy_refs: tuple[str, ...] = Field(min_length=1)
    provenance_source_ref: str = Field(min_length=1)
    provenance_note: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_case(self) -> "ScriptedMysteryCaseContent":
        scalar_refs = (self.case_ref, self.package_ref, self.package_revision, self.location_ref, self.provenance_source_ref)
        if not all(_versioned(ref) for ref in scalar_refs):
            raise ValueError("mystery_case_ref_invalid")
        if not _ordered(self.actor_refs) or not _ordered(self.action_graph_refs) or not _ordered(self.presentation_refs) or not _ordered(self.policy_refs):
            raise ValueError("mystery_case_array_not_canonical")
        if set(self.role_assignments) != set(self.actor_refs) or any(not _versioned(value) for value in self.role_assignments.values()):
            raise ValueError("mystery_case_role_assignment_invalid")
        if len({fact.fact_ref for fact in self.truth_facts}) != len(self.truth_facts):
            raise ValueError("mystery_case_truth_duplicate")
        actor_set = set(self.actor_refs)
        if self.culprit_actor_ref not in actor_set:
            raise ValueError("mystery_case_culprit_unknown")
        truth_set = {fact.fact_ref for fact in self.truth_facts}
        for knowledge in self.private_knowledge_sets:
            if knowledge.actor_ref not in actor_set or not set(knowledge.fact_refs).issubset(truth_set):
                raise ValueError("mystery_case_private_truth_invalid")
        if len({knowledge.actor_ref for knowledge in self.private_knowledge_sets}) != len(self.private_knowledge_sets):
            raise ValueError("mystery_case_private_knowledge_duplicate")
        if len(self.phase_definitions) != 3 or tuple(phase.ordinal for phase in self.phase_definitions) != tuple(range(3)):
            raise ValueError("mystery_case_phase_sequence_invalid")
        if len(self.outcome_definitions) != 4 or len({outcome.outcome_kind for outcome in self.outcome_definitions}) != 4:
            raise ValueError("mystery_case_outcome_set_invalid")
        if len(self.clue_definitions) < 10 or len(self.clue_definitions) > 15:
            raise ValueError("mystery_case_clue_count_invalid")
        return self


class CaseContentAdmissionResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    content_digest: str | None = None
    error_code: str | None = None

    @classmethod
    def admit(
        cls,
        content: ScriptedMysteryCaseContent,
        *,
        admitted_action_graph_refs: Iterable[str],
        admitted_predicate_refs: Iterable[str],
    ) -> "CaseContentAdmissionResult":
        action_refs = set(admitted_action_graph_refs)
        predicate_refs = set(admitted_predicate_refs)
        if not set(content.action_graph_refs).issubset(action_refs):
            return cls(accepted=False, error_code="mystery_case_action_graph_unknown")
        all_predicates = {
            predicate
            for phase in content.phase_definitions
            for predicate in phase.transition_predicate_refs
        } | {
            predicate
            for clue in content.clue_definitions
            for predicate in clue.discovery_predicate_refs
        }
        if not all_predicates.issubset(predicate_refs):
            return cls(accepted=False, error_code="mystery_case_predicate_unknown")
        digest = "sha256:" + sha256(
            json.dumps(content.model_dump(mode="json"), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(accepted=True, content_digest=digest)


def stormnight_case_content() -> ScriptedMysteryCaseContent:
    actors = (
        "character:stormnight-guardian@1",
        "character:stormnight-heir@1",
        "character:stormnight-investigator@1",
        "character:stormnight-physician@1",
    )
    truth = tuple(
        CaseTruthFact(
            fact_ref=f"fact:stormnight:{index:02d}@1",
            fact_kind=kind,
            subject_refs=(f"subject:stormnight:{index:02d}@1",),
            value_ref=f"value:stormnight:{index:02d}@1",
            source_ref="source:stormnight-authoring@1",
        )
        for index, kind in enumerate(("scene", "identity", "causal", "possession", "timeline", "relationship"), start=1)
    )
    clues = tuple(
        ClueDefinition(
            clue_ref=f"clue:stormnight:{index:02d}@1",
            location_ref=f"location:stormnight:room-{(index % 4) + 1}@1",
            evidence_kind_ref="evidence:stormnight:physical@1",
            reveals_fact_refs=(truth[(index - 1) % len(truth)].fact_ref,),
            discovery_predicate_refs=("predicate:stormnight:inspect@1",),
        )
        for index in range(1, 11)
    )
    knowledge = tuple(
        PrivateKnowledgeSet(
            knowledge_ref=f"knowledge:stormnight:actor-{index}@1",
            actor_ref=actor,
            fact_refs=(truth[(index - 1) % len(truth)].fact_ref,),
            permitted_statement_refs=(f"statement:stormnight:{index:02d}@1",),
        )
        for index, actor in enumerate(actors, start=1)
    )
    statements = tuple(
        StatementDefinition(
            statement_ref=f"statement:stormnight:{index:02d}@1",
            speaker_ref=actors[(index - 1) % len(actors)],
            target_ref=actors[index % len(actors)],
            truth_fact_refs=(truth[(index - 1) % len(truth)].fact_ref,),
            visibility="project" if index % 2 else "actor_private",
            allowed_modes=("deny", "mislead", "reveal", "withhold"),
            policy_ref="policy:stormnight:statement@1",
        )
        for index in range(1, 5)
    )
    phases = tuple(
        CasePhaseDefinition(
            phase_ref=f"phase:stormnight:{name}@1",
            ordinal=ordinal,
            action_graph_refs=("graph:stormnight-investigation@1",),
            objective_refs=(f"objective:stormnight:{ordinal}@1",),
            transition_predicate_refs=("predicate:stormnight:phase-transition@1",),
        )
        for ordinal, name in enumerate(("arrival", "investigation", "storm-night"))
    )
    outcomes = tuple(
        CaseOutcomeDefinition(
            outcome_ref=f"outcome:stormnight:{kind}@1",
            outcome_kind=kind,
            required_fact_refs=(truth[index].fact_ref,),
            policy_ref="policy:stormnight:terminal@1",
        )
        for index, kind in enumerate(("case_solved", "false_accusation", "culprit_escaped", "investigator_captured"))
    )
    return ScriptedMysteryCaseContent(
        case_ref="case:stormnight-copper-sanatorium@1",
        case_revision="case:stormnight-copper-sanatorium@1",
        package_ref="package:stormnight-copper-sanatorium@1",
        package_revision="package:stormnight-copper-sanatorium:v1@1",
        location_ref="location:stormnight-copper-sanatorium@1",
        actor_refs=actors,
        culprit_actor_ref="character:stormnight-guardian@1",
        role_assignments={actor: role for actor, role in zip(actors, ("role:threatened-heir@1", "role:guardian@1", "role:investigator@1", "role:physician@1"), strict=True)},
        truth_facts=truth,
        private_knowledge_sets=knowledge,
        clue_definitions=clues,
        statement_definitions=statements,
        phase_definitions=phases,
        outcome_definitions=outcomes,
        action_graph_refs=("graph:stormnight-investigation@1",),
        presentation_refs=("presentation:stormnight:godot@1",),
        policy_refs=("policy:stormnight:statement@1", "policy:stormnight:terminal@1"),
        provenance_source_ref="source:project-gutenberg-1661@1",
        provenance_note="Original case content; public-domain structural inspiration only; no source text or names copied.",
    )


__all__ = [
    "CaseContentAdmissionResult",
    "CaseOutcomeDefinition",
    "CasePhaseDefinition",
    "CaseTruthFact",
    "ClueDefinition",
    "PrivateKnowledgeSet",
    "ScriptedMysteryCaseContent",
    "StatementDefinition",
    "stormnight_case_content",
]
