from dataclasses import FrozenInstanceError

import pytest
from app.gameplay.l5_reaction import ReactionRejected, compile_reactions


def test_reactions_resolve_registered_commands_and_remain_async():
    declarations = [{
        "reaction_id": "casualty_to_morale",
        "on": {
            "fact_type_pattern": "fact:character:*:lifestate",
            "transition_to": "dead",
        },
        "emit": {
            "command_type": "recompute_morale",
            "target": {"scope": "group_of(subject)"},
            "payload": {"cause_ref": "$event.event_id"},
        },
        "cooldown_world_ticks": 0,
        "priority": 100,
    }]

    reactions = compile_reactions(declarations, command_fact_outputs={
        "recompute_morale": {"fact:character:morale:level"},
    })

    assert len(reactions) == 1
    assert reactions[0].reaction_id == "casualty_to_morale"
    assert reactions[0].command_type == "recompute_morale"
    assert reactions[0].trigger_pattern == "fact:character:*:lifestate"
    assert reactions[0].async_dispatch is True
    assert reactions[0].priority == 100
    with pytest.raises(FrozenInstanceError):
        reactions[0].priority = 1


@pytest.mark.parametrize(("declaration", "outputs", "code"), [
    (
        {"reaction_id": "bad", "on": {"fact_type_pattern": "fact:character:*:life", "transition_to": "dead"},
         "emit": {"writes": ["fact:character:morale:level"]}},
        {},
        "reaction_emit_command_required",
    ),
    (
        {"reaction_id": "bad", "on": {"fact_type_pattern": "fact:character:*:life", "transition_to": "dead"},
         "emit": {"command_type": "unknown.command"}},
        {},
        "reaction_command_unknown",
    ),
    (
        {"reaction_id": "bad", "on": {"fact_type_pattern": "fact:character:*:life"},
         "emit": {"command_type": "known.command"}},
        {"known.command": set()},
        "reaction_schema_invalid",
    ),
    (
        {"reaction_id": "bad", "on": {"fact_type_pattern": "fact:character:*:life", "transition_to": "dead"},
         "emit": {"command_type": "known.command", "writes": ["fact:character:life:state"]}},
        {"known.command": set()},
        "reaction_emit_command_required",
    ),
])
def test_reactions_reject_invalid_emit_or_trigger(declaration, outputs, code):
    with pytest.raises(ReactionRejected) as error:
        compile_reactions([declaration], command_fact_outputs=outputs)

    assert error.value.code == code


def test_reactions_reject_a_cycle_from_trusted_command_outputs():
    declarations = [
        {
            "reaction_id": "casualty_to_morale",
            "on": {
                "fact_type_pattern": "fact:character:*:lifestate",
                "transition_to": "dead",
            },
            "emit": {"command_type": "recompute_morale"},
        },
        {
            "reaction_id": "morale_to_life",
            "on": {
                "fact_type_pattern": "fact:character:*:morale",
                "event_type": "gameplay.morale.updated",
            },
            "emit": {"command_type": "restore_life"},
        },
    ]

    with pytest.raises(ReactionRejected) as error:
        compile_reactions(declarations, command_fact_outputs={
            "recompute_morale": {"fact:character:team:morale"},
            "restore_life": {"fact:character:alice:lifestate"},
        })

    assert error.value.code == "reaction_cycle_detected"


def test_reactions_reject_a_self_triggering_command():
    declaration = {
        "reaction_id": "life_to_life",
        "on": {"fact_type_pattern": "fact:character:*:lifestate", "transition_to": "dead"},
        "emit": {"command_type": "restore_life"},
    }

    with pytest.raises(ReactionRejected, match="reaction_cycle_detected"):
        compile_reactions([declaration], command_fact_outputs={
            "restore_life": {"fact:character:alice:lifestate"},
        })


@pytest.mark.parametrize("priorities", [(100, 100), (100, 102)])
def test_reactions_reject_non_dense_or_duplicate_priorities(priorities):
    declarations = [
        {
            "reaction_id": reaction_id,
            "on": {"fact_type_pattern": "fact:character:*:lifestate", "transition_to": "dead"},
            "emit": {"command_type": "recompute_morale"},
            "priority": priority,
        }
        for reaction_id, priority in zip(("morale_a", "morale_b"), priorities)
    ]

    with pytest.raises(ReactionRejected, match="reaction_priority_invalid"):
        compile_reactions(declarations, command_fact_outputs={"recompute_morale": set()})


def test_reactions_reject_duplicate_ids_and_malformed_command_outputs():
    declaration = {
        "reaction_id": "casualty_to_morale",
        "on": {"fact_type_pattern": "fact:character:*:lifestate", "transition_to": "dead"},
        "emit": {"command_type": "recompute_morale"},
    }

    with pytest.raises(ReactionRejected, match="reaction_command_outputs_invalid"):
        compile_reactions([declaration], command_fact_outputs={
            "recompute_morale": {"fact:character:morale:level"},
            "unknown.command": {"not-a-fact-type"},
        })

    with pytest.raises(ReactionRejected, match="reaction_id_duplicate"):
        compile_reactions([declaration, declaration], command_fact_outputs={
            "recompute_morale": {"fact:character:morale:level"},
        })
