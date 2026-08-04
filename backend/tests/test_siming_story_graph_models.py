import pytest
from pydantic import ValidationError

from app.models.siming_story_graph import (
    RuntimeStoryNode,
    StoryNodeBlueprint,
    StoryNodeTransitionCommand,
    StoryOutcomePort,
)


def test_terminal_player_closure_requires_never_reopen() -> None:
    with pytest.raises(ValidationError, match="reopen_policy"):
        RuntimeStoryNode(
            node_id="runtime:N4:main",
            blueprint_id="N4",
            lifecycle="aborted",
            closure_reason="closed_by_player_choice",
            terminal=True,
            reopen_policy="new_causal_basis",
            reachability="unreachable",
        )


def test_outcome_port_requires_authority_predicate() -> None:
    with pytest.raises(ValidationError, match="required_result_type"):
        StoryOutcomePort(
            port_id="player_destroyed_evidence",
            required_result_type="",
            target_ref="obj_letter",
            required_state="removed_from_surface",
            outcome_semantic="resolved_with_divergence",
        )


def test_blueprint_rejects_duplicate_outcome_port_ids() -> None:
    port = StoryOutcomePort(
        port_id="player_destroyed_evidence",
        required_result_type="object_state_result",
        target_ref="obj_letter",
        required_state="removed_from_surface",
        outcome_semantic="resolved_with_divergence",
    )

    with pytest.raises(ValidationError, match="unique"):
        StoryNodeBlueprint(
            blueprint_id="N3",
            title="Repair the record",
            outcome_ports=[port, port],
        )


def test_new_causal_basis_requires_reference() -> None:
    with pytest.raises(ValidationError, match="causal_basis_refs"):
        RuntimeStoryNode(
            node_id="runtime:N4:aftermath",
            blueprint_id="N4",
            lifecycle="latent",
            reopen_policy="new_causal_basis",
        )


def test_transition_command_rejects_skipped_lifecycle() -> None:
    with pytest.raises(ValidationError, match="invalid story lifecycle transition"):
        StoryNodeTransitionCommand(
            node_id="runtime:N3:main",
            expected="eligible",
            target="active",
            reason="skip staging",
            recorded_at=10,
        )
