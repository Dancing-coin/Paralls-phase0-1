"""Compile L5 reactions against trusted command output declarations."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Set
from dataclasses import dataclass
from fnmatch import fnmatchcase
from app.gameplay.fact_type_registry import ResolverInputError, freeze


@dataclass(frozen=True, slots=True)
class Reaction:
    reaction_id: str
    trigger_pattern: str
    trigger_kind: str
    trigger_value: str
    condition_ref: str | None
    command_type: str
    target: Mapping[str, object]
    payload: Mapping[str, object]
    priority: int
    cooldown_world_ticks: int
    async_dispatch: bool = True


class ReactionRejected(ValueError):
    def __init__(self, code: str, field: str):
        super().__init__(f"{code}: {field}")
        self.code = code
        self.field = field


def compile_reactions(
    declarations: object,
    *,
    command_fact_outputs: Mapping[str, Set[str]],
) -> tuple[Reaction, ...]:
    if not isinstance(declarations, list):
        raise ReactionRejected("reaction_schema_invalid", "reactions")

    for command_type, fact_types in command_fact_outputs.items():
        if (not isinstance(command_type, str) or not command_type
                or not isinstance(fact_types, (set, frozenset))
                or any(not _is_fact_type(fact_type) for fact_type in fact_types)):
            raise ReactionRejected("reaction_command_outputs_invalid", "command_fact_outputs")

    reactions = []
    reaction_ids = set()
    priorities_by_trigger = {}
    for declaration in declarations:
        if not isinstance(declaration, Mapping):
            raise ReactionRejected("reaction_schema_invalid", "reaction")
        if declaration.keys() - {
            "reaction_id", "on", "when", "emit", "cooldown_world_ticks", "priority",
        }:
            raise ReactionRejected("reaction_schema_invalid", "reaction")

        reaction_id = declaration.get("reaction_id")
        trigger = declaration.get("on")
        emit = declaration.get("emit")
        if (not isinstance(reaction_id, str) or not reaction_id
                or not isinstance(trigger, Mapping) or not isinstance(emit, Mapping)):
            raise ReactionRejected("reaction_schema_invalid", "reaction")
        if reaction_id in reaction_ids:
            raise ReactionRejected("reaction_id_duplicate", "reaction_id")
        reaction_ids.add(reaction_id)

        pattern = trigger.get("fact_type_pattern")
        trigger_keys = {"fact_type_pattern", "event_type", "transition_to"}
        if (trigger.keys() - trigger_keys or not isinstance(pattern, str)
                or not pattern.startswith("fact:") or any(char.isspace() for char in pattern)
                or ("event_type" in trigger) == ("transition_to" in trigger)):
            raise ReactionRejected("reaction_schema_invalid", "on")
        trigger_kind = "event_type" if "event_type" in trigger else "transition_to"
        trigger_value = trigger[trigger_kind]
        if not isinstance(trigger_value, str) or not trigger_value:
            raise ReactionRejected("reaction_schema_invalid", "on")

        if "writes" in emit:
            raise ReactionRejected("pattern_declares_writes", "emit.writes")
        command_type = emit.get("command_type")
        if (emit.keys() - {"command_type", "target", "payload"}
                or not isinstance(command_type, str) or not command_type):
            raise ReactionRejected("reaction_emit_command_required", "emit")
        if command_type not in command_fact_outputs:
            raise ReactionRejected("pattern_command_unknown", "emit.command_type")

        condition = declaration.get("when")
        if condition is not None and (
            not isinstance(condition, Mapping) or condition.keys() != {"condition_ref"}
            or not isinstance(condition.get("condition_ref"), str) or not condition["condition_ref"]
        ):
            raise ReactionRejected("reaction_schema_invalid", "when")
        target = emit.get("target", {})
        payload = emit.get("payload", {})
        if not isinstance(target, Mapping) or not isinstance(payload, Mapping):
            raise ReactionRejected("reaction_schema_invalid", "emit")
        try:
            frozen_target = freeze(target)
            frozen_payload = freeze(payload)
        except ResolverInputError as error:
            raise ReactionRejected("reaction_schema_invalid", "emit") from error

        priority = declaration.get("priority", 0)
        cooldown = declaration.get("cooldown_world_ticks", 0)
        if type(priority) is not int or priority < 0 or type(cooldown) is not int or cooldown < 0:
            raise ReactionRejected("reaction_schema_invalid", "priority")

        reactions.append(Reaction(
            reaction_id=reaction_id,
            trigger_pattern=pattern,
            trigger_kind=trigger_kind,
            trigger_value=trigger_value,
            condition_ref=condition["condition_ref"] if condition is not None else None,
            command_type=command_type,
            target=frozen_target,
            payload=frozen_payload,
            priority=priority,
            cooldown_world_ticks=cooldown,
        ))
        trigger_key = pattern, trigger_kind, trigger_value
        priorities_by_trigger.setdefault(trigger_key, []).append(priority)

    for priorities in priorities_by_trigger.values():
        ordered = sorted(priorities)
        if ordered != list(range(ordered[0], ordered[0] + len(ordered))):
            raise ReactionRejected("reaction_priority_invalid", "priority")

    _reject_cycles(reactions, command_fact_outputs)
    return tuple(reactions)


def _reject_cycles(
    reactions: list[Reaction],
    command_fact_outputs: Mapping[str, Set[str]],
) -> None:
    edges = {reaction.reaction_id: set() for reaction in reactions}
    incoming = dict.fromkeys(edges, 0)
    for source in reactions:
        output_facts = command_fact_outputs[source.command_type]
        for target in reactions:
            if any(
                fnmatchcase(fact_type, target.trigger_pattern) for fact_type in output_facts
            ):
                edges[source.reaction_id].add(target.reaction_id)

    for targets in edges.values():
        for target in targets:
            incoming[target] += 1

    ready = deque(reaction_id for reaction_id, degree in incoming.items() if degree == 0)
    visited = 0
    while ready:
        reaction_id = ready.popleft()
        visited += 1
        for target in edges[reaction_id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)

    if visited != len(reactions):
        raise ReactionRejected("reaction_cycle_detected", "reactions")


def _is_fact_type(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("fact:")
        and not any(char.isspace() or char in "*?[" for char in value)
    )
