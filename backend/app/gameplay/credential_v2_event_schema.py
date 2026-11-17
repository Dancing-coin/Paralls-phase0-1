"""Schema identity and strict validation for credential link v2 events."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass

from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry


class CredentialV2EventSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class CredentialV2EventSchema:
    event_type: str
    schema_version: int
    schema_digest: str
    required_payload_fields: frozenset[str]
    transition: tuple[str, str]


_ISSUED_FIELDS = frozenset({
    "credential_id", "credential_item_ref", "issued_holder_ref",
    "issued_holder_inventory_revision", "right_id", "credential_kind", "proves",
    "issuer_ref", "from_state", "to_state", "condition_ref", "condition_revision",
})
_REVOKED_FIELDS = frozenset({
    "credential_id", "issuer_ref", "reason", "from_state", "to_state",
    "condition_ref", "condition_revision",
})
_SUPERSEDED_FIELDS = frozenset({
    "credential_id", "replacement_credential_id", "issuer_ref", "from_state",
    "to_state", "condition_ref", "condition_revision",
})
_HOLDER_EVENT_FIELDS = frozenset({
    "credential_id", "item_ref", "from_state", "to_state",
    "condition_ref", "condition_revision",
})

CREDENTIAL_V2_EVENT_SCHEMAS = (
    CredentialV2EventSchema(
        "gameplay.credential.link_issued", 2,
        "sha256:g3:credential-link-issued:v2:m3",
        _ISSUED_FIELDS, ("absent", "issued"),
    ),
    CredentialV2EventSchema(
        "gameplay.credential.link_revoked", 2,
        "sha256:g3:credential-link-revoked:v2:m3",
        _REVOKED_FIELDS, ("issued", "revoked"),
    ),
    CredentialV2EventSchema(
        "gameplay.credential.link_superseded", 2,
        "sha256:g3:credential-link-superseded:v2:m3",
        _SUPERSEDED_FIELDS, ("issued", "superseded"),
    ),
)
_SCHEMAS = {schema.event_type: schema for schema in CREDENTIAL_V2_EVENT_SCHEMAS}
_HOLDER_TRANSITIONS = {
    "gameplay.credential.item_claimed": ("absent", "occupied"),
    "gameplay.credential.item_released": ("occupied", "absent"),
}


def credential_link_stream_id(credential_id: str) -> str:
    if (type(credential_id) is not str or not credential_id
            or any(ord(char) < 32 or ord(char) == 127 for char in credential_id)):
        raise CredentialV2EventSchemaError("credential_fact_scope_invalid")
    encoded = base64.urlsafe_b64encode(credential_id.encode("utf-8", errors="strict")).decode("ascii").rstrip("=")
    scope = f"c-{encoded}"
    stream_id = f"fact:credential:{scope}:link"
    if len(stream_id) > 128:
        raise CredentialV2EventSchemaError("credential_fact_scope_too_long")
    return stream_id


def credential_holder_stream_id(item_ref: str) -> str:
    return credential_link_stream_id(item_ref).removesuffix(":link") + ":holder"


def register_credential_v2_event_schemas(registry: EventSchemaRegistry) -> None:
    for schema in CREDENTIAL_V2_EVENT_SCHEMAS:
        registry.register(EventSchemaRegistration(
            schema.event_type, schema.schema_version, schema.schema_digest
        ))


def validate_credential_v2_event(event: Mapping[str, object]) -> None:
    if not isinstance(event, Mapping):
        raise CredentialV2EventSchemaError("credential_v2_event_invalid")
    event_type = event.get("event_type")
    schema = _SCHEMAS.get(event_type) if type(event_type) is str else None
    if schema is None or event.get("schema_version") != 2:
        raise CredentialV2EventSchemaError("credential_v2_event_unregistered")
    payload = event.get("payload")
    if not isinstance(payload, Mapping) or set(payload) != schema.required_payload_fields:
        raise CredentialV2EventSchemaError("credential_v2_payload_invalid")
    for field in schema.required_payload_fields - {"issued_holder_inventory_revision", "condition_revision"}:
        value = payload[field]
        if type(value) is not str or not value:
            code = "credential_v2_condition_invalid" if field == "condition_ref" else "credential_v2_payload_invalid"
            raise CredentialV2EventSchemaError(code)
    for field in ("issued_holder_inventory_revision",):
        if field in payload and (type(payload[field]) is not int or payload[field] < 0):
            raise CredentialV2EventSchemaError("credential_v2_payload_invalid")
    if type(payload["condition_revision"]) is not int or payload["condition_revision"] < 1:
        raise CredentialV2EventSchemaError("credential_v2_condition_invalid")
    if (payload["from_state"], payload["to_state"]) != schema.transition:
        raise CredentialV2EventSchemaError("credential_v2_transition_invalid")
    if event.get("stream_id") != credential_link_stream_id(payload["credential_id"]):
        raise CredentialV2EventSchemaError("credential_v2_stream_mismatch")


def validate_credential_v2_holder_event(event: Mapping[str, object]) -> None:
    if not isinstance(event, Mapping):
        raise CredentialV2EventSchemaError("credential_v2_event_invalid")
    event_type = event.get("event_type")
    transition = _HOLDER_TRANSITIONS.get(event_type) if type(event_type) is str else None
    if transition is None or event.get("schema_version") != 2:
        raise CredentialV2EventSchemaError("credential_v2_event_unregistered")
    payload = event.get("payload")
    if not isinstance(payload, Mapping) or set(payload) != _HOLDER_EVENT_FIELDS:
        raise CredentialV2EventSchemaError("credential_v2_payload_invalid")
    for field in _HOLDER_EVENT_FIELDS - {"condition_revision"}:
        if type(payload[field]) is not str or not payload[field]:
            raise CredentialV2EventSchemaError("credential_v2_payload_invalid")
    if type(payload["condition_revision"]) is not int or payload["condition_revision"] < 1:
        raise CredentialV2EventSchemaError("credential_v2_condition_invalid")
    if (payload["from_state"], payload["to_state"]) != transition:
        raise CredentialV2EventSchemaError("credential_v2_transition_invalid")
    if event.get("stream_id") != credential_holder_stream_id(payload["item_ref"]):
        raise CredentialV2EventSchemaError("credential_v2_stream_mismatch")
