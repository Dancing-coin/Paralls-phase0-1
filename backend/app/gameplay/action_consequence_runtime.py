"""Owner-bound consequence and two-level death contracts for action outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel


ConsequenceOwner = Literal["body", "inventory", "quest", "social", "economy", "character"]


class ActionConsequenceIntent(StrictGameplayModel):
    source_event_id: str
    source_event_type: Literal["gameplay.conflict.terminal_outcome_recorded"]
    target_actor_ref: str
    owner_kind: ConsequenceOwner
    expected_source_revision: int
    policy_revision: str
    evidence_refs: tuple[str, ...]
    owner_principal_ref: str = ""
    target_stream_ref: str = ""
    target_event_type: str = ""


class WorldDeathConfirmationIntent(StrictGameplayModel):
    source_event_id: str
    target_actor_ref: str
    expected_source_revision: int
    confirmation_ref: str
    confirmed: bool
    policy_revision: str


class ActionConsequenceValidationResult(StrictGameplayModel):
    accepted: bool
    error_code: str | None = None
    source_event_id: str | None = None
    source_revision: int | None = None


@dataclass(frozen=True)
class ActionConsequenceBoundary:
    """Read-only source validator; target owners perform all durable writes."""

    store: GameplayEventStore

    def validate(self, intent: ActionConsequenceIntent) -> ActionConsequenceValidationResult:
        if not intent.evidence_refs:
            return ActionConsequenceValidationResult(accepted=False, error_code="action_consequence_evidence_missing")
        expected_owner = {
            "body": "authority:body",
            "inventory": "authority:inventory",
            "quest": "authority:quest",
            "social": "authority:social",
            "economy": "authority:economy",
            "character": "authority:character",
        }[intent.owner_kind]
        if intent.owner_principal_ref and intent.owner_principal_ref != expected_owner:
            return ActionConsequenceValidationResult(accepted=False, error_code="action_consequence_owner_fragment_invalid")
        try:
            source = self.store.get_event(intent.source_event_id)
        except KeyError:
            return ActionConsequenceValidationResult(accepted=False, error_code="action_consequence_source_missing")
        if (
            source.event_type != intent.source_event_type
            or source.visibility_policy != "project"
            or source.stream_revision != intent.expected_source_revision
            or source.payload.get("actor_ref") != intent.target_actor_ref
        ):
            return ActionConsequenceValidationResult(accepted=False, error_code="action_consequence_source_conflict")
        return ActionConsequenceValidationResult(
            accepted=True,
            source_event_id=source.event_id,
            source_revision=source.stream_revision,
        )

    def validate_world_death(self, intent: WorldDeathConfirmationIntent) -> ActionConsequenceValidationResult:
        if not intent.confirmation_ref or not intent.policy_revision:
            return ActionConsequenceValidationResult(accepted=False, error_code="world_death_confirmation_invalid")
        try:
            source = self.store.get_event(intent.source_event_id)
        except KeyError:
            return ActionConsequenceValidationResult(accepted=False, error_code="world_death_source_missing")
        if (
            source.event_type != "gameplay.conflict.terminal_outcome_recorded"
            or source.visibility_policy != "project"
            or source.stream_revision != intent.expected_source_revision
            or source.payload.get("actor_ref") != intent.target_actor_ref
            or source.payload.get("terminal_kind") != "case_death"
        ):
            return ActionConsequenceValidationResult(accepted=False, error_code="world_death_source_conflict")
        return ActionConsequenceValidationResult(accepted=True, source_event_id=source.event_id, source_revision=source.stream_revision)


__all__ = [
    "ActionConsequenceBoundary",
    "ActionConsequenceIntent",
    "ActionConsequenceValidationResult",
    "ConsequenceOwner",
    "WorldDeathConfirmationIntent",
]
