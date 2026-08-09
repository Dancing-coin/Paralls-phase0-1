"""Explicit event-type/version allowlist for opt-in Gameplay store writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class EventSchemaRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class EventSchemaRegistration:
    event_type: str
    schema_version: int
    schema_digest: str


PHASE2A_WORK_INTENT_EVENT_SCHEMAS = (
    EventSchemaRegistration("gameplay.work.respond_shift", 1, "sha256:phase2a:respond_shift:v1"),
    EventSchemaRegistration("gameplay.work.start_work", 1, "sha256:phase2a:start_work:v1"),
    EventSchemaRegistration("gameplay.work.finish_work", 1, "sha256:phase2a:finish_work:v1"),
    EventSchemaRegistration("gameplay.work.report_absence", 1, "sha256:phase2a:report_absence:v1"),
    EventSchemaRegistration("gameplay.work.request_break", 1, "sha256:phase2a:request_break:v1"),
)


class EventSchemaRegistry:
    def __init__(self) -> None:
        self._registrations: dict[tuple[str, int], EventSchemaRegistration] = {}

    def register(self, registration: EventSchemaRegistration) -> None:
        key = (registration.event_type, registration.schema_version)
        if not registration.event_type or registration.schema_version < 1 or not registration.schema_digest:
            raise EventSchemaRegistryError("event_schema_registration_invalid")
        existing = self._registrations.get(key)
        if existing is not None:
            if existing.schema_digest != registration.schema_digest:
                raise EventSchemaRegistryError("event_schema_digest_conflict")
            raise EventSchemaRegistryError("event_schema_registration_duplicate")
        self._registrations[key] = registration

    def require(self, event_type: str, schema_version: int) -> None:
        if (event_type, schema_version) not in self._registrations:
            raise EventSchemaRegistryError("event_schema_unregistered")

    def get(self, event_type: str, schema_version: int) -> EventSchemaRegistration:
        try:
            return self._registrations[(event_type, schema_version)]
        except KeyError as exc:
            raise EventSchemaRegistryError("event_schema_unregistered") from exc

    def export_snapshot(self) -> dict[str, Any]:
        """Return the immutable schema identities required to reopen a store."""
        return {
            "registry_schema_version": 1,
            "registrations": [
                {
                    "event_type": registration.event_type,
                    "schema_version": registration.schema_version,
                    "schema_digest": registration.schema_digest,
                }
                for _, registration in sorted(self._registrations.items())
            ],
        }

    @classmethod
    def from_snapshot(cls, snapshot: object) -> "EventSchemaRegistry":
        if not isinstance(snapshot, dict) or snapshot.get("registry_schema_version") != 1:
            raise EventSchemaRegistryError("event_schema_registry_snapshot_unsupported")
        values = snapshot.get("registrations")
        if not isinstance(values, list):
            raise EventSchemaRegistryError("event_schema_registry_snapshot_invalid")
        registry = cls()
        try:
            for value in values:
                if not isinstance(value, dict):
                    raise EventSchemaRegistryError("event_schema_registry_snapshot_invalid")
                registry.register(
                    EventSchemaRegistration(
                        event_type=str(value["event_type"]),
                        schema_version=int(value["schema_version"]),
                        schema_digest=str(value["schema_digest"]),
                    )
                )
        except (KeyError, TypeError, ValueError, EventSchemaRegistryError) as exc:
            if isinstance(exc, EventSchemaRegistryError) and exc.args and exc.args[0] in {
                "event_schema_registration_duplicate",
                "event_schema_digest_conflict",
            }:
                raise EventSchemaRegistryError("event_schema_registry_snapshot_invalid") from exc
            if isinstance(exc, EventSchemaRegistryError):
                raise
            raise EventSchemaRegistryError("event_schema_registry_snapshot_invalid") from exc
        return registry


def register_phase2a_work_intent_event_schemas(registry: EventSchemaRegistry) -> None:
    for registration in PHASE2A_WORK_INTENT_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc
