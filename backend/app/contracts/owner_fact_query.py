from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from app.models.fact_type import FactType, FactTypeRef


FactTypeValue = FactType | FactTypeRef


@dataclass(frozen=True)
class OwnerProjection:
    fact_type: FactTypeValue
    actor_ref: str
    revision: int
    source_owner: str
    source_event_ref: str
    event_type: str
    captured_at: int
    freshness: str
    payload: Mapping[str, object]
    causation_id: str = ""
    correlation_id: str = ""


class OwnerFactQuery(Protocol):
    def query_facts(
        self,
        fact_types: Iterable[FactTypeValue],
        *,
        actor_refs: Iterable[str] | None = None,
        at_revision: int | None = None,
        source_event_ref: str | None = None,
        audience: str = "siming_internal",
    ) -> list[OwnerProjection]: ...

    def get_owner_for_fact_type(self, fact_type: FactTypeValue) -> str: ...

    def subscribe(
        self,
        fact_types: Iterable[FactTypeValue],
        callback: Callable[[OwnerProjection], None],
        *,
        audience: str = "siming_internal",
    ) -> str: ...
