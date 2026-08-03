"""Trusted, deterministic one-version event upcasters for Gameplay replay."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Any, Callable

from app.gameplay.event_schema_registry import EventSchemaRegistry, EventSchemaRegistryError
from app.gameplay.models import GameplayEvent


class EventUpcasterRegistryError(ValueError):
    pass


EventUpcasterTransform = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class EventUpcasterRegistration:
    event_type: str
    from_version: int
    to_version: int
    input_schema_digest: str
    output_schema_digest: str
    upcaster_version: str
    transform: EventUpcasterTransform


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class EventUpcasterRegistry:
    """Registry for only continuous ``vN -> vN+1`` trusted transform steps."""

    def __init__(self, *, event_schema_registry: EventSchemaRegistry) -> None:
        self._event_schema_registry = event_schema_registry
        self._registrations: dict[tuple[str, int], EventUpcasterRegistration] = {}

    def register(self, registration: EventUpcasterRegistration) -> None:
        key = (registration.event_type, registration.from_version)
        if (
            not registration.event_type
            or registration.from_version < 1
            or registration.to_version != registration.from_version + 1
            or not registration.input_schema_digest
            or not registration.output_schema_digest
            or not registration.upcaster_version
            or not callable(registration.transform)
        ):
            raise EventUpcasterRegistryError("event_upcaster_registration_invalid")
        if key in self._registrations:
            raise EventUpcasterRegistryError("event_upcaster_registration_duplicate")
        try:
            input_schema = self._event_schema_registry.get(registration.event_type, registration.from_version)
            output_schema = self._event_schema_registry.get(registration.event_type, registration.to_version)
        except EventSchemaRegistryError as exc:
            raise EventUpcasterRegistryError("event_upcaster_schema_unregistered") from exc
        if (
            input_schema.schema_digest != registration.input_schema_digest
            or output_schema.schema_digest != registration.output_schema_digest
        ):
            raise EventUpcasterRegistryError("event_upcaster_schema_digest_mismatch")
        self._registrations[key] = registration

    def upcast(self, event: GameplayEvent, *, target_version: int) -> GameplayEvent:
        if target_version < event.schema_version:
            raise EventUpcasterRegistryError("event_upcaster_target_version_invalid")
        current = event.model_copy(deep=True)
        while current.schema_version < target_version:
            registration = self._registrations.get((current.event_type, current.schema_version))
            if registration is None:
                raise EventUpcasterRegistryError("upcaster_chain_missing")
            current = self._apply_step(current, registration)
        return current

    def _apply_step(self, event: GameplayEvent, registration: EventUpcasterRegistration) -> GameplayEvent:
        if event.event_type != registration.event_type or event.schema_version != registration.from_version:
            raise EventUpcasterRegistryError("event_upcaster_input_mismatch")
        try:
            schema = self._event_schema_registry.get(event.event_type, event.schema_version)
        except EventSchemaRegistryError as exc:
            raise EventUpcasterRegistryError("event_upcaster_schema_unregistered") from exc
        if schema.schema_digest != registration.input_schema_digest:
            raise EventUpcasterRegistryError("upcaster_digest_mismatch")
        metadata = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "schema_version": event.schema_version,
            "stream_id": event.stream_id,
            "stream_revision": event.stream_revision,
            "global_sequence": event.global_sequence,
            "transaction_id": event.transaction_id,
            "command_id": event.command_id,
            "causation_id": event.causation_id,
            "correlation_id": event.correlation_id,
            "visibility_policy": event.visibility_policy,
        }
        first_payload = registration.transform(deepcopy(event.payload), deepcopy(metadata))
        second_payload = registration.transform(deepcopy(event.payload), deepcopy(metadata))
        if not isinstance(first_payload, dict) or not isinstance(second_payload, dict):
            raise EventUpcasterRegistryError("event_upcaster_output_invalid")
        if _canonical_json(first_payload) != _canonical_json(second_payload):
            raise EventUpcasterRegistryError("event_upcaster_nondeterministic")
        try:
            target_schema = self._event_schema_registry.get(event.event_type, registration.to_version)
        except EventSchemaRegistryError as exc:
            raise EventUpcasterRegistryError("event_upcaster_schema_unregistered") from exc
        if target_schema.schema_digest != registration.output_schema_digest:
            raise EventUpcasterRegistryError("upcaster_digest_mismatch")
        return event.model_copy(
            update={"schema_version": registration.to_version, "payload": first_payload},
            deep=True,
        )
