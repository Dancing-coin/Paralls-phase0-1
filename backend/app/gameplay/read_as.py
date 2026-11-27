from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from app.gameplay.fact_type_registry import FactTypeRegistry
from app.gameplay.information_runtime import (
    INFORMATION_KNOWLEDGE_FACT_TYPE,
    INFORMATION_KNOWLEDGE_EVENT_TYPE,
    INFORMATION_REPORT_EVENT,
    INFORMATION_REPORT_FACT_TYPE,
    InformationAuthority,
)


_RECIPIENT_SELECTOR = "recipient_of(subject)"
_INFORMATION_READS = {
    INFORMATION_REPORT_FACT_TYPE: (INFORMATION_REPORT_EVENT, "report_ref"),
    INFORMATION_KNOWLEDGE_FACT_TYPE: (INFORMATION_KNOWLEDGE_EVENT_TYPE, "report_event_id"),
}


class GameplayReadAsError(ValueError):
    pass


@dataclass(frozen=True)
class ScopedFact:
    fact_type_ref: str
    value: Mapping[str, object]
    source_owner_ref: str
    source_revision: int
    event_time: int
    known_time: int
    freshness: int
    confidence: str


@dataclass(frozen=True)
class ScopedProjection:
    principal_ref: str
    as_of_tick: int
    facts: tuple[ScopedFact, ...]


class GameplayReadAs:
    """Principal-facing gameplay reads for FactTypes with verified readers."""

    def __init__(self, *, authority: InformationAuthority, registry: FactTypeRegistry) -> None:
        self._authority = authority
        self._registry = registry

    def read_as(
        self,
        *,
        principal: str,
        scope: Mapping[str, str],
        as_of_tick: int,
        fact_types: Sequence[str],
    ) -> ScopedProjection:
        if (not isinstance(principal, str) or not principal.startswith("character:")
                or len(principal) > 160 or type(as_of_tick) is not int or as_of_tick < 0
                or not isinstance(scope, Mapping)
                or not isinstance(fact_types, (list, tuple)) or not fact_types
                or any(not isinstance(fact_type, str) for fact_type in fact_types)
                or len(set(fact_types)) != len(fact_types)):
            raise GameplayReadAsError("read_as_input_invalid")

        required_scope = set()
        facts = []
        for fact_type_ref in fact_types:
            declaration = self._registry.facts.get(fact_type_ref)
            if declaration is None:
                raise GameplayReadAsError("read_as_fact_type_unknown")
            if any(declaration.visibility.get(key) is not None for key in (
                "delay", "delay_model", "distortion", "distortion_model",
            )):
                raise GameplayReadAsError("read_as_visibility_model_unavailable")
            if declaration.visibility.get("class") in {"secret", "debug_only"}:
                raise GameplayReadAsError("read_as_visibility_forbidden")
            event_type, scope_key = _INFORMATION_READS.get(fact_type_ref, (None, None))
            if event_type is None:
                raise GameplayReadAsError("read_as_fact_type_reader_unavailable")
            if (declaration.owner_ref != "Information"
                    or declaration.visibility.get("class") != "private"
                    or tuple(declaration.visibility.get("learnable_by", ())) != (_RECIPIENT_SELECTOR,)):
                raise GameplayReadAsError("read_as_qualification_unavailable")
            if declaration not in self._registry.fact_types_for_event(event_type, 1):
                raise GameplayReadAsError("read_as_fact_type_mapping_invalid")
            required_scope.add(scope_key)

        if (set(scope) != required_scope
                or any(not isinstance(value, str) or not value for value in scope.values())):
            raise GameplayReadAsError("read_as_scope_invalid")

        for fact_type_ref in fact_types:
            if fact_type_ref == INFORMATION_REPORT_FACT_TYPE:
                view = self._authority.read_report_for_recipient(
                    recipient_ref=principal,
                    report_ref=scope["report_ref"],
                    as_of_tick=as_of_tick,
                )
            else:
                view = self._authority.read_knowledge_for_recipient(
                    recipient_ref=principal,
                    report_event_id=scope["report_event_id"],
                    as_of_tick=as_of_tick,
                )
            if view is not None:
                facts.append(ScopedFact(
                    fact_type_ref=fact_type_ref,
                    value=asdict(view),
                    source_owner_ref=view.source_owner_ref,
                    source_revision=view.source_revision,
                    event_time=view.event_time,
                    known_time=view.known_time,
                    freshness=view.freshness,
                    confidence="full",
                ))

        return ScopedProjection(principal_ref=principal, as_of_tick=as_of_tick, facts=tuple(facts))
