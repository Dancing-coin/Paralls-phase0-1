"""Allowlisted same Resource owner conversion contracts."""
from dataclasses import replace

import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.services.resource_conversion_service import (ConversionWorldScope, ResourceConversionCommand,
    ResourceConversionService, load_conversion_rules)
from test_equipment_command_service import _admit_presence, _auth


CONNECTION = "connection:equipment"
STREAM = "gameplay:resources:char_a"


def _setup(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "conversion.sqlite")
    _admit_presence(store)
    batch = build_multi_stream_atomic_event_batch(command_id="prepare:mana-cost", principal_ref="resource_reservation_authority",
        expected_revisions={STREAM: store.get_stream_head(STREAM)},
        event_specs={STREAM: [("gameplay.resource.adjusted", {"actor_ref": "char_a", "resource_id": "core.mana", "delta": -20})]},
        idempotency_key="prepare:mana-cost", causation_id="c", correlation_id="c",
        event_visibility_policies={STREAM: ["authority_only"]})
    assert store.append_batch(batch).committed
    auth = _auth()
    service = _service(store, auth)
    projection = ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_stream(STREAM))
    return store, auth, service, projection


def _service(store, auth, **kwargs):
    return ResourceConversionService(store=store, controller_auth=auth,
        scope_resolver=kwargs.pop("scope_resolver", lambda: ConversionWorldScope("world:bakery", "timeline:main")),
        capability_resolver=kwargs.pop("capability_resolver", lambda principal, actor, revision: principal == "principal:trusted_local:char_a" and actor == "char_a"),
        policy_source=kwargs.pop("policy_source", load_conversion_rules), **kwargs)


def _command(projection, **changes):
    rule = load_conversion_rules()[0]
    data = dict(command_id="conversion:one", actor_ref="char_a", world_ref="world:bakery", timeline_ref="timeline:main",
        policy_revision=rule.revision, policy_digest=rule.policy_digest, rule_id=rule.rule_id, units=2,
        expected_projection_revision=projection.projection_revision, idempotency_key="conversion:one", causation_id="cause:conversion", correlation_id="corr:conversion")
    return ResourceConversionCommand(**{**data, **changes})


def test_conversion_commits_both_sides_and_durable_duplicate_checkpoint_tail(tmp_path):
    store, _, service, before = _setup(tmp_path)
    command = _command(before)
    result = service.submit(command, connection_ref=CONNECTION, resources=before)
    assert result.committed
    events = store.read_stream(STREAM)
    full = ResourceBodyRuntimeProjector().rebuild_resources("char_a", events)
    tail = ResourceBodyRuntimeProjector().rebuild_resources("char_a", events[-1:], checkpoint=before)
    assert full == tail
    assert (full.entries["core.stamina"].current, full.entries["core.mana"].current) == (90, 64)
    count = len(store.read_events())
    store.close()
    reopened = DurableGameplayEventStore(tmp_path / "conversion.sqlite")
    duplicate = _service(reopened, _auth()).submit(command, connection_ref=CONNECTION, resources=full)
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == result.committed_event_ids
    assert len(reopened.read_events()) == count
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        _service(reopened, _auth()).submit(command.model_copy(update={"units": 3}), connection_ref=CONNECTION, resources=full)
    reopened.close()


def test_conversion_rejects_forged_projection_without_writes(tmp_path):
    store, _, service, before = _setup(tmp_path)
    forged = replace(before, entries={**before.entries, "core.stamina": replace(before.entries["core.stamina"], current=100000)})
    count = len(store.read_events())
    with pytest.raises(ValueError, match="projection"):
        service.submit(_command(before), connection_ref=CONNECTION, resources=forged)
    assert len(store.read_events()) == count
    store.close()


@pytest.mark.parametrize("changes,error", [({"units": 100}, "insufficient"),
    ({"policy_digest": "sha256:" + "0"*64}, "policy_pin"), ({"world_ref": "wrong"}, "scope")])
def test_conversion_rejects_invalid_input_without_writes(tmp_path, changes, error):
    store, _, service, before = _setup(tmp_path)
    count = len(store.read_events())
    with pytest.raises(ValueError, match=error):
        service.submit(_command(before, **changes), connection_ref=CONNECTION, resources=before)
    assert len(store.read_events()) == count
    store.close()


def test_conversion_revalidates_controller_before_append(tmp_path):
    store, auth, _, before = _setup(tmp_path)
    reads = 0
    def policy():
        nonlocal reads
        reads += 1
        if reads == 3:
            auth.revoke_controller_epoch(controller_instance_id="controller:equipment", connection_epoch=1)
        return load_conversion_rules()
    service = _service(store, auth, policy_source=policy)
    count = len(store.read_events())
    with pytest.raises(ValueError, match="controller"):
        service.submit(_command(before), connection_ref=CONNECTION, resources=before)
    assert len(store.read_events()) == count
    store.close()


def test_conversion_capability_is_required_and_revoked_before_commit(tmp_path):
    store, auth, _, before = _setup(tmp_path)
    count = len(store.read_events())
    service = _service(store, auth, capability_resolver=None)
    with pytest.raises(ValueError, match="capability_required"):
        service.submit(_command(before), connection_ref=CONNECTION, resources=before)
    calls = 0
    def capability(*args):
        nonlocal calls
        calls += 1
        return calls == 1
    service = _service(store, auth, capability_resolver=capability)
    with pytest.raises(ValueError, match="capability_revoked"):
        service.submit(_command(before), connection_ref=CONNECTION, resources=before)
    assert len(store.read_events()) == count
    store.close()


def test_conversion_output_capacity_rejects_whole_transaction(tmp_path):
    store, auth, _, before = _setup(tmp_path)
    rule = load_conversion_rules()[1]
    command = _command(before, rule_id=rule.rule_id, units=1)
    count = len(store.read_events())
    with pytest.raises(ValueError, match="output_capacity"):
        _service(store, auth).submit(command, connection_ref=CONNECTION, resources=before)
    assert len(store.read_events()) == count
    assert ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_stream(STREAM)) == before
    store.close()


def test_conversion_rejects_changed_policy_after_admission(tmp_path):
    store, auth, _, before = _setup(tmp_path)
    rules = list(load_conversion_rules())
    service = _service(store, auth, policy_source=lambda: tuple(rules))
    rules[0] = replace(rules[0], output_amount=99)
    count = len(store.read_events())
    with pytest.raises(ValueError, match="policy_source_changed"):
        service.submit(_command(before), connection_ref=CONNECTION, resources=before)
    assert len(store.read_events()) == count
    store.close()


def test_conversion_duplicate_rejects_tampered_event_receipt(tmp_path, monkeypatch):
    store, auth, service, before = _setup(tmp_path)
    command = _command(before)
    first = service.submit(command, connection_ref=CONNECTION, resources=before)
    assert first.committed
    original_get_event = store.get_event
    def tampered(event_id):
        event = original_get_event(event_id)
        if event is not None and event.event_id in first.committed_event_ids:
            return event.model_copy(update={"payload": {**event.payload, "output_delta": 999}})
        return event
    monkeypatch.setattr(store, "get_event", tampered)
    with pytest.raises(ValueError, match="receipt_invalid"):
        service.submit(command, connection_ref=CONNECTION, resources=ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_stream(STREAM)))
    store.close()
