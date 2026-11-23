from dataclasses import FrozenInstanceError
from pathlib import Path
import shutil

import pytest

from app.gameplay.fact_type_registry import RegistrationRejected
from app.gameplay.l5_reaction import ReactionRejected, compile_reactions
from app.gameplay.rule_pack_validator import load_pack


def test_reactions_resolve_registered_commands_and_remain_async():
    declarations = [{
        "reaction_id": "casualty_to_morale",
        "on": {
            "fact_type_pattern": "fact:character:*:lifestate",
            "transition_to": "dead",
        },
        "when": {"condition_ref": "morale_relevant@1"},
        "emit": {
            "command_type": "recompute_morale",
            "target": {"scope": "group_of(subject)"},
            "payload": {"cause_ref": "$event.event_id", "tags": ["casualty"]},
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
    assert reactions[0].trigger_kind == "transition_to"
    assert reactions[0].trigger_value == "dead"
    assert reactions[0].condition_ref == "morale_relevant@1"
    declarations[0]["emit"]["payload"]["tags"].append("changed")
    assert reactions[0].payload["tags"] == ("casualty",)
    assert reactions[0].async_dispatch is True
    assert reactions[0].priority == 100
    with pytest.raises(FrozenInstanceError):
        reactions[0].priority = 1


@pytest.mark.parametrize(("declaration", "outputs", "code"), [
    (
        {"reaction_id": "bad", "on": {"fact_type_pattern": "fact:character:*:life", "transition_to": "dead"},
         "emit": {"writes": ["fact:character:morale:level"]}},
        {},
        "pattern_declares_writes",
    ),
    (
        {"reaction_id": "bad", "on": {"fact_type_pattern": "fact:character:*:life", "transition_to": "dead"},
         "emit": {"command_type": "unknown.command"}},
        {},
        "pattern_command_unknown",
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
        "pattern_declares_writes",
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


def test_reactions_accept_exact_place_machine_output_type():
    reactions = compile_reactions([{
        "reaction_id": "gate_breach_to_presence_reeval",
        "on": {
            "fact_type_pattern": "fact:facility:gate-*:integrity",
            "event_type": "gameplay.pool.threshold_crossed",
        },
        "emit": {"command_type": "presence.reevaluate"},
    }], command_fact_outputs={
        "presence.reevaluate": {"place:gate-03:passability"},
    })

    assert len(reactions) == 1


@pytest.fixture
def composition_pack(tmp_path):
    source = Path(__file__).resolve().parents[2] / "packs" / "credential_reference"
    pack = shutil.copytree(source, tmp_path / "composition")
    manifest = pack / "pack.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "contents:\n",
        'contents:\n  command_catalog: ["issue"]\n  reactions: ["issue"]\n'
        '  workflows: ["issue"]\n  play_patterns: ["issue"]\n',
    ), encoding="utf-8")
    for category in ("command_catalog", "reactions", "workflows", "play_patterns"):
        (pack / category).mkdir()
    (pack / "command_catalog" / "issue.yaml").write_text(
        'ownership.issue:\n  handled_by: "Ownership"\n  payload_schema: "issue@1"\n'
        '  requires_authority: true\n  idempotency_shape: "command_id"\n  version: 1\n', encoding="utf-8",
    )
    (pack / "reactions" / "issue.yaml").write_text(
        'issue_after_record:\n  "on":\n    fact_type_pattern: "fact:credential:*:record"\n'
        '    event_type: "gameplay.credential.recorded"\n'
        '  emit:\n    command_type: "ownership.issue"\n', encoding="utf-8",
    )
    (pack / "workflows" / "issue.yaml").write_text(
        'manual_issuance:\n  steps:\n    - id: "issue"\n      command: "ownership.issue"\n', encoding="utf-8",
    )
    (pack / "play_patterns" / "issue.yaml").write_text(
        'issuance:\n  reactions: ["issue_after_record"]\n  workflows: ["manual_issuance"]\n', encoding="utf-8",
    )
    return pack


def test_pack_loads_reaction_and_links_play_pattern_to_registered_composition(composition_pack):
    loaded = load_pack(
        composition_pack, handlers={"credential_command@1": lambda inputs, params: True},
        owner_domains={"Ownership": "ownership"},
        command_fact_outputs={"ownership.issue": {"fact:credential:deed:link"}},
    )
    assert loaded.reactions["issue_after_record"].trigger_value == "gameplay.credential.recorded"
    assert loaded.play_patterns["issuance"].reactions == ("issue_after_record",)
    assert loaded.play_patterns["issuance"].workflows == ("manual_issuance",)


@pytest.mark.parametrize(("outputs", "code"), [
    ({}, "pattern_command_unknown"),
    ({"ownership.issue": {"fact:credential:deed:record"}}, "reaction_cycle_detected"),
])
def test_pack_rejects_reaction_without_trusted_outputs_or_with_a_cycle(composition_pack, outputs, code):
    with pytest.raises(RegistrationRejected, match=code):
        load_pack(
            composition_pack, handlers={"credential_command@1": lambda inputs, params: True},
            owner_domains={"Ownership": "ownership"}, command_fact_outputs=outputs,
        )


def test_pack_rejects_unknown_reaction_reference_in_play_pattern(composition_pack):
    (composition_pack / "play_patterns" / "issue.yaml").write_text(
        'issuance:\n  reactions: ["missing"]\n', encoding="utf-8",
    )
    with pytest.raises(RegistrationRejected, match="pattern_reference_unknown"):
        load_pack(
            composition_pack, handlers={"credential_command@1": lambda inputs, params: True},
            owner_domains={"Ownership": "ownership"},
            command_fact_outputs={"ownership.issue": {"fact:credential:deed:link"}},
        )
