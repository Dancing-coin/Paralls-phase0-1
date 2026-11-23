"""Dispatch committed L5 reactions through explicitly trusted command handlers."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Set
from dataclasses import dataclass
from fnmatch import fnmatchcase
from types import MappingProxyType

from app.gameplay.l5_reaction import Reaction
from app.gameplay.models import AtomicEventBatch, GameplayEvent


CommandHandler = Callable[["TriggeredGameplayCommand"], object]
ReactionCondition = Callable[[GameplayEvent], bool]


@dataclass(frozen=True, slots=True)
class TriggeredGameplayCommand:
    command_id: str
    idempotency_key: str
    command_type: str
    trigger_event: GameplayEvent
    target: Mapping[str, object]
    payload: Mapping[str, object]
    causation_id: str
    correlation_id: str


class TrustedGameplayCommandGateway:
    """Route commands only to handlers whose fact outputs were explicitly declared."""

    def __init__(
        self,
        *,
        handlers: Mapping[str, CommandHandler],
        command_fact_outputs: Mapping[str, Set[str]],
    ) -> None:
        if not handlers or handlers.keys() != command_fact_outputs.keys():
            raise ValueError("l5_command_registration_invalid")
        outputs: dict[str, frozenset[str]] = {}
        for command_type, fact_types in command_fact_outputs.items():
            if (
                not isinstance(command_type, str)
                or not command_type
                or not isinstance(fact_types, (set, frozenset))
                or not fact_types
                or any(
                    not isinstance(fact_type, str)
                    or not fact_type.startswith("fact:")
                    or any(char.isspace() for char in fact_type)
                    for fact_type in fact_types
                )
            ):
                raise ValueError("l5_command_outputs_invalid")
            outputs[command_type] = frozenset(fact_types)
        if any(not callable(handler) for handler in handlers.values()):
            raise ValueError("l5_command_handler_invalid")
        self._handlers = dict(handlers)
        self.command_fact_outputs = MappingProxyType(outputs)

    def submit(self, command: TriggeredGameplayCommand) -> object:
        try:
            handler = self._handlers[command.command_type]
        except KeyError as error:
            raise ValueError("l5_command_unknown") from error
        return handler(command)


class L5ReactionDispatcher:
    """Run compiled reactions against a committed transaction and submit commands."""

    def __init__(
        self,
        *,
        reactions: tuple[Reaction, ...],
        gateway: TrustedGameplayCommandGateway,
        fact_type_for: Callable[[GameplayEvent], str | None],
        conditions: Mapping[str, ReactionCondition] | None = None,
    ) -> None:
        condition_map = dict(conditions or {})
        unknown_conditions = {
            reaction.condition_ref
            for reaction in reactions
            if reaction.condition_ref is not None and reaction.condition_ref not in condition_map
        }
        if unknown_conditions:
            raise ValueError("l5_condition_unknown")
        self._reactions = tuple(sorted(reactions, key=lambda reaction: reaction.priority))
        self._gateway = gateway
        self._fact_type_for = fact_type_for
        self._conditions = condition_map

    def after_transaction_dispatched(self, transaction: AtomicEventBatch) -> tuple[object, ...]:
        results = []
        for event in transaction.events:
            fact_type = self._fact_type_for(event)
            if not isinstance(fact_type, str):
                continue
            for reaction in self._reactions:
                if not self._matches(reaction, event, fact_type):
                    continue
                if reaction.condition_ref is not None and not self._conditions[reaction.condition_ref](event):
                    continue
                command_id = f"l5:{reaction.reaction_id}:{event.event_id}"
                command = TriggeredGameplayCommand(
                    command_id=command_id,
                    idempotency_key=command_id,
                    command_type=reaction.command_type,
                    trigger_event=event,
                    target=reaction.target,
                    payload=reaction.payload,
                    causation_id=event.event_id,
                    correlation_id=event.correlation_id or event.event_id,
                )
                results.append(self._gateway.submit(command))
        return tuple(results)

    @staticmethod
    def _matches(reaction: Reaction, event: GameplayEvent, fact_type: str) -> bool:
        if not fnmatchcase(fact_type, reaction.trigger_pattern):
            return False
        if reaction.trigger_kind == "event_type":
            return event.event_type == reaction.trigger_value
        return event.payload.get("to_state") == reaction.trigger_value
