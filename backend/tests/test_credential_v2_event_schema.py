from __future__ import annotations

import pytest

from app.gameplay.credential_v2_event_schema import (
    CREDENTIAL_V2_EVENT_SCHEMAS,
    CREDENTIAL_V3_EVENT_SCHEMAS,
    CredentialV2EventSchemaError,
    register_credential_v2_event_schemas,
    validate_credential_v2_event,
)
from app.gameplay.event_schema_registry import EventSchemaRegistry


def _event(event_type: str, payload: dict[str, object], stream_id: str, schema_version: int = 2) -> dict[str, object]:
    return {"event_type": event_type, "schema_version": schema_version, "stream_id": stream_id, "payload": payload}


def test_v2_event_types_are_distinct_from_legacy_types_and_define_machine_evidence():
    assert {schema.event_type for schema in CREDENTIAL_V2_EVENT_SCHEMAS} == {
        "gameplay.credential.link_issued",
        "gameplay.credential.link_revoked",
        "gameplay.credential.link_superseded",
    }
    assert all(schema.schema_version == 2 for schema in CREDENTIAL_V2_EVENT_SCHEMAS)


def test_v2_event_schema_identities_register_and_export_from_the_shared_registry():
    registry = EventSchemaRegistry()
    register_credential_v2_event_schemas(registry)
    snapshot = registry.export_snapshot()
    assert {(row["event_type"], row["schema_version"]) for row in snapshot["registrations"]} == {
        (schema.event_type, schema.schema_version) for schema in CREDENTIAL_V2_EVENT_SCHEMAS
    } | {(schema.event_type, schema.schema_version) for schema in CREDENTIAL_V3_EVENT_SCHEMAS}


def test_valid_v2_issued_event_must_use_the_encoded_instance_stream():
    credential_id = "credential:g3:1"
    payload = {
        "credential_id": credential_id,
        "credential_item_ref": "item:g3:1",
        "issued_holder_ref": "actor:g3",
        "issued_holder_inventory_revision": 5,
        "right_id": "right:g3",
        "credential_kind": "deed",
        "proves": "evidence_only",
        "issuer_ref": "authority:g3",
        "from_state": "absent",
        "to_state": "issued",
        "condition_ref": "credential_issue_rule",
        "condition_revision": 1,
    }
    assert validate_credential_v2_event(_event(
        "gameplay.credential.link_issued", payload,
        "fact:credential:c-Y3JlZGVudGlhbDpnMzox:link",
    )) is None
    bond_payload = payload | {"bond_ref": "bond:g3"}
    del bond_payload["right_id"]
    assert validate_credential_v2_event(_event(
        "gameplay.credential.link_issued", bond_payload,
        "fact:credential:c-Y3JlZGVudGlhbDpnMzox:link", schema_version=3,
    )) is None
    with pytest.raises(CredentialV2EventSchemaError, match="^credential_v2_payload_invalid$"):
        validate_credential_v2_event(_event(
            "gameplay.credential.link_issued", payload,
            "fact:credential:c-Y3JlZGVudGlhbDpnMzox:link", schema_version=3,
        ))


@pytest.mark.parametrize("changed,code", [
    ({"condition_ref": ""}, "credential_v2_condition_invalid"),
    ({"condition_revision": 0}, "credential_v2_condition_invalid"),
    ({"from_state": "issued"}, "credential_v2_transition_invalid"),
    ({"to_state": "revoked"}, "credential_v2_transition_invalid"),
])
def test_v2_machine_evidence_and_transition_are_mandatory(changed, code):
    payload = {
        "credential_id": "credential:g3:1",
        "credential_item_ref": "item:g3:1",
        "issued_holder_ref": "actor:g3",
        "issued_holder_inventory_revision": 5,
        "right_id": "right:g3",
        "credential_kind": "deed",
        "proves": "evidence_only",
        "issuer_ref": "authority:g3",
        "from_state": "absent",
        "to_state": "issued",
        "condition_ref": "credential_issue_rule",
        "condition_revision": 1,
    } | changed
    with pytest.raises(CredentialV2EventSchemaError, match=f"^{code}$"):
        validate_credential_v2_event(_event(
            "gameplay.credential.link_issued", payload,
            "fact:credential:c-Y3JlZGVudGlhbDpnMzox:link",
        ))


def test_v2_event_with_wrong_instance_stream_is_rejected():
    payload = {
        "credential_id": "credential:g3:1",
        "credential_item_ref": "item:g3:1",
        "issued_holder_ref": "actor:g3",
        "issued_holder_inventory_revision": 5,
        "right_id": "right:g3",
        "credential_kind": "deed",
        "proves": "evidence_only",
        "issuer_ref": "authority:g3",
        "from_state": "absent",
        "to_state": "issued",
        "condition_ref": "credential_issue_rule",
        "condition_revision": 1,
    }
    with pytest.raises(CredentialV2EventSchemaError, match="^credential_v2_stream_mismatch$"):
        validate_credential_v2_event(_event(
            "gameplay.credential.link_issued", payload, "gameplay:credentials"
        ))
