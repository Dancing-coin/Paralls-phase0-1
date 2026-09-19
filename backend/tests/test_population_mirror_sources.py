from dataclasses import replace

import pytest

from app.gameplay.godot_mirror_delivery import (
    GameplayGodotMirrorSyncAdapter, GameplayGodotProjectionPublisher, GameplayGodotProjectionRepository,
    GameplayMirrorAfterCommitDelivery, GameplayMirrorDeliveryError, GameplayMirrorSubscriptionRegistry,
)
from app.gameplay.state_group_views import combine_godot_views
from app.population_continuity.presentation import PopulationMirrorSource, build_population_actor_view
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.gameplay_mirror_session_access_service import GameplayMirrorSessionAccessService, GameplayMirrorSubscriptionRequest
from test_population_durable_cadence_recovery import _runtime, _publisher
from test_gameplay_mirror_session_access_service import _context, _projection_source


def _setup(world):
    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)
    registry = GameplayMirrorSubscriptionRegistry(projection_source=repository.view_for)
    sent, bindings = [], {}
    delivery = GameplayMirrorAfterCommitDelivery(registry=registry, deliver=lambda session, payload: sent.append((session, payload)))
    source = PopulationMirrorSource(world=world, publisher=publisher, registry=registry, delivery=delivery)
    service = GameplayMirrorSessionAccessService(registry=registry, projection_publisher=publisher, binding_resolver=bindings.get)
    return repository, publisher, registry, source, service, sent, bindings


def test_composed_public_groups_preserve_metadata_and_roundtrip_changes(tmp_path):
    world = _runtime(tmp_path / "world.sqlite3")
    population = build_population_actor_view(world, actor_id="one")
    resources = _projection_source("character:one")
    combined = combine_godot_views(resources, population)
    assert combined == combine_godot_views(population, resources)
    assert set(combined.groups) == {"resources", "population_public"}
    assert combined.groups["resources"] is resources.groups["resources"]
    assert combined.groups["population_public"] is population.groups["population_public"]
    assert dict(combined.source_revision_vector) == {"character:one": 1}
    sync = GameplayGodotMirrorSyncAdapter()
    before = sync.snapshot(combined)
    assert _publisher(world, InMemoryAuthorityEventBus())(world.build_population_cadence(window_start=0, window_end=1))
    target = sync.snapshot(combine_godot_views(resources, build_population_actor_view(world, actor_id="one")))
    delta = sync.delta(before, target)
    assert set(delta.changed_group_envelopes) == {"population_public"}
    assert sync.apply_delta(before, delta) == target
    removed = sync.snapshot(combine_godot_views(replace(resources, groups={}), population))
    assert sync.delta(before, removed).removed_group_ids == ("resources",)
    for other in (population, replace(resources, actor_ref="outsider"), replace(resources, consumer="authority")):
        with pytest.raises(ValueError):
            combine_godot_views(population, other)


def test_installation_wraps_existing_source_once_when_runtime_restarts(tmp_path):
    world = _runtime(tmp_path / "world.sqlite3")
    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)
    resources = _projection_source("character:one")
    publisher.register_actor_source(actor_ref="character:one", source=lambda: resources)
    registry = GameplayMirrorSubscriptionRegistry(projection_source=repository.view_for)
    delivery = GameplayMirrorAfterCommitDelivery(registry=registry, deliver=lambda *_: None)
    for _ in range(2):
        PopulationMirrorSource(world=world, publisher=publisher, registry=registry, delivery=delivery)
        view = publisher.refresh_actor(actor_ref="character:one")
        assert set(view.groups) == {"resources", "population_public"}
        assert view.groups["resources"] is resources.groups["resources"]


def test_population_registration_is_lazy_rebinds_world_and_caps_unique_views(tmp_path, monkeypatch):
    world = _runtime(tmp_path / "world.sqlite3", tuple(f"resident_{i}" for i in range(10000)))
    built = []
    from app.population_continuity import presentation
    original = presentation.build_population_actor_view
    monkeypatch.setattr(presentation, "build_population_actor_view", lambda value, **kwargs: (built.append((value, kwargs["actor_id"])), original(value, **kwargs))[1])
    repository, publisher, registry, source, service, sent, bindings = _setup(world)
    assert not repository._views and not built
    refs = tuple(f"character:{actor}" for actor in world.roster.actor_ids[:161])
    first = _context(*refs)
    second = _context(*refs, "actor:ordinary")
    second.binding = second.binding.model_copy(update={"session_ref": "second"})
    bindings.update({first.binding.session_ref: first.binding, second.binding.session_ref: second.binding})
    for actor in refs[:160]:
        service.subscribe(context=first, request=GameplayMirrorSubscriptionRequest(actor_ref=actor))
    assert len(built) == len(repository._views) == 160
    with pytest.raises(GameplayMirrorDeliveryError, match="population_mirror_subscription_limit"):
        service.subscribe(context=second, request=GameplayMirrorSubscriptionRequest(actor_ref=refs[-1]))
    assert len(built) == 160
    service.subscribe(context=second, request=GameplayMirrorSubscriptionRequest(actor_ref=refs[0]))
    publisher.register_actor_source(actor_ref="actor:ordinary", source=lambda: _projection_source("actor:ordinary"))
    service.subscribe(context=second, request=GameplayMirrorSubscriptionRequest(actor_ref="actor:ordinary"))
    assert len(repository._views) == 161  # 非人口保留既有每session合同。
    service.unsubscribe(context=first, actor_ref=refs[0])
    assert refs[0] in repository._views
    service.unsubscribe(context=second, actor_ref=refs[0])
    service.subscribe(context=first, request=GameplayMirrorSubscriptionRequest(actor_ref=refs[-1]))
    assert refs[0] not in repository._views
    replacement = _runtime(tmp_path / "replacement.sqlite3", world.roster.actor_ids)
    PopulationMirrorSource(world=replacement, publisher=publisher, registry=registry, delivery=source.delivery)
    service.snapshot(context=first, actor_ref=refs[-1])
    assert built[-1][0] is replacement


def test_receipt_checkpoint_precedes_fanout_and_failures_never_send_stale_view(tmp_path, monkeypatch):
    world = _runtime(tmp_path / "world.sqlite3")
    repository, publisher, registry, source, service, sent, bindings = _setup(world)
    context = _context("character:one", "character:two")
    bindings[context.binding.session_ref] = context.binding
    for actor in context.binding.allowed_actor_refs:
        service.subscribe(context=context, request=GameplayMirrorSubscriptionRequest(actor_ref=actor))
    bus = InMemoryAuthorityEventBus()
    bus.subscribe("population_cadence_event", lambda _: sent.append("bus_before_receipt"))
    cadence_publisher = _publisher(world, bus)
    cadence = world.build_population_cadence(window_start=0, window_end=1)
    save = world.store.save_projection_checkpoints_atomic
    monkeypatch.setattr(world.store, "save_projection_checkpoints_atomic", lambda _: (_ for _ in ()).throw(RuntimeError("disk_failed")))
    with pytest.raises(RuntimeError, match="disk_failed"):
        cadence_publisher(cadence)
    assert sent == ["bus_before_receipt"]
    with pytest.raises(ValueError, match="unconfirmed"):
        source.refresh_confirmed()
    assert sent == ["bus_before_receipt"]
    monkeypatch.setattr(world.store, "save_projection_checkpoints_atomic", save)
    assert cadence_publisher(cadence)
    sent.clear()
    source.refresh_confirmed()
    assert [payload["groups"]["population_public"]["payload"]["confirmed_tick"] for _, payload in sent] == [1, 1]
    source.refresh_confirmed()
    assert len(sent) == 2
    publisher.register_actor_source(actor_ref="character:one", source=lambda: (_ for _ in ()).throw(RuntimeError("source_failed")))
    assert cadence_publisher(world.build_population_cadence(window_start=1, window_end=2))
    sent.clear()
    source.refresh_confirmed()
    assert [payload["actor_ref"] for _, payload in sent] == ["character:two"]
    assert "character:one" not in repository._views
    assert source.last_refresh.unavailable_actor_refs == ("character:one",)


@pytest.mark.parametrize("visible", [0, 160])
def test_full_population_advances_but_only_unique_subscribed_views_are_built(tmp_path, monkeypatch, visible):
    world = _runtime(tmp_path / "world.sqlite3", tuple(f"resident_{i}" for i in range(10000)))
    repository, publisher, registry, source, service, sent, bindings = _setup(world)
    for index, actor in enumerate(world.roster.actor_ids[:visible]):
        ref = f"character:{actor}"
        publisher.refresh_actor(actor_ref=ref)
        registry.grant_read_scope(session_ref="first", actor_ref=ref)
        registry.subscribe(session_ref="first", actor_ref=ref)
        if index == 0:
            registry.grant_read_scope(session_ref="shared", actor_ref=ref)
            registry.subscribe(session_ref="shared", actor_ref=ref)
    builds = []
    original = publisher.refresh_actor
    monkeypatch.setattr(publisher, "refresh_actor", lambda **kwargs: (builds.append(kwargs["actor_ref"]), original(**kwargs))[1])
    bus = InMemoryAuthorityEventBus()
    bus.subscribe("population_cadence_event", lambda _: builds.append("before-confirm"))
    assert _publisher(world, bus)(world.build_population_cadence(window_start=0, window_end=1))
    assert builds == ["before-confirm"] and not sent
    builds.clear()
    source.refresh_confirmed()
    assert world.latest_confirmation.advanced_count == 10000
    assert len(builds) == len(set(builds)) == len(repository._views) == visible
    assert len(sent) == visible + bool(visible)


@pytest.mark.parametrize("supports_delta", [False, True])
def test_main_population_source_is_same_world_and_first_update_uses_real_transport(monkeypatch, supports_delta):
    from time import time
    from fastapi.testclient import TestClient
    from app import main
    from app.ws_protocol import GameplayMirrorCapabilityOffer
    monkeypatch.setattr(main.settings, "population_runtime_profile", "benchmark_1x")
    with TestClient(main.component_app, client=("127.0.0.1", 47112)) as client:
        owner = main.runtime_execution
        def configure():
            assert main._population_mirror_source.world is main._population_runtime_driver.world_runtime
            actor = f"character:{main.population_roster.actor_ids[0]}"
            credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
                principal_ref="population-probe", allowed_actor_refs=(actor,), issued_at=int(time()), expires_at=int(time()) + 100)
            return actor, credential
        actor, credential = owner.submit(configure).result(5)
        with client.websocket_connect("/ws") as socket:
            socket.send_json({"message_type": "websocket_session_bind", "payload": {
                "credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 2,
                "capability_offer": GameplayMirrorCapabilityOffer(protocol_version=2, supports_snapshot=True,
                    supports_delta=supports_delta, supports_receipt=True,
                    projection_schemas=("gameplay_runtime_state.godot.v1",)).model_dump(mode="json")}})
            assert socket.receive_json()["payload"]["accepted"]
            assert socket.receive_json()["message_type"] == "websocket_session_bound"
            socket.send_json({"message_type": "gameplay_mirror_subscribe", "payload": {"actor_ref": actor}})
            assert socket.receive_json()["payload"]["accepted"]
            initial = socket.receive_json()["payload"]
            assert initial["delivery_kind"] == "snapshot" and initial["delivery_sequence"] == 1
            def tick():
                driver = main._population_runtime_driver
                result = driver.tick(driver.current_tick + driver.window_size)
                assert not result.rejected_windows
                return driver.current_tick
            confirmed_tick = owner.submit(tick).result(5)
            updated = socket.receive_json()["payload"]
            assert updated["delivery_sequence"] == 2 and updated["connection_epoch"] == initial["connection_epoch"]
            assert updated["delivery_kind"] == ("delta" if supports_delta else "snapshot")
            assert updated["payload"]["groups"]["population_public"]["payload"]["confirmed_tick"] == confirmed_tick
            if supports_delta:
                assert updated["base_snapshot_checksum"] == initial["payload"]["snapshot_checksum"]
                assert updated["payload"]["base_facade_revision"] == initial["facade_revision"]
            socket.send_json({"message_type": "gameplay_mirror_snapshot_request", "payload": {"actor_ref": actor}})
            assert socket.receive_json()["payload"]["accepted"]
            recovered = socket.receive_json()["payload"]
            assert recovered["delivery_kind"] == "snapshot"
            assert recovered["payload"]["canonical_snapshot_json"] == updated["payload"]["canonical_snapshot_json"]


def test_confirmed_batch_reuses_one_validation_without_reusing_it_for_later_requests(tmp_path, monkeypatch):
    from app.population_continuity import presentation
    world = _runtime(tmp_path / "world.sqlite3")
    repository, publisher, registry, source, service, sent, bindings = _setup(world)
    context = _context("character:one", "character:two")
    bindings[context.binding.session_ref] = context.binding
    for actor in context.binding.allowed_actor_refs:
        service.subscribe(context=context, request=GameplayMirrorSubscriptionRequest(actor_ref=actor))
    assert _publisher(world, InMemoryAuthorityEventBus())(world.build_population_cadence(window_start=0, window_end=1))
    sync = GameplayGodotMirrorSyncAdapter()
    expected = [sync.snapshot_payload(sync.snapshot(build_population_actor_view(world, actor_id=actor)))
                for actor in ("one", "two")]
    calls = []
    original = presentation.parse_population_checkpoint
    monkeypatch.setattr(presentation, "parse_population_checkpoint", lambda *args: (calls.append(1), original(*args))[1])
    source.refresh_confirmed()
    assert [payload for _, payload in sent] == expected
    assert len(calls) == 1
    service.snapshot(context=context, actor_ref="character:one")
    assert len(calls) == 2  # 新请求重新验证，不跨命令持有可信确认缓存。
    monkeypatch.setattr(world.store, "get_projection_checkpoint", lambda _: None)
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_projection_unavailable"):
        service.snapshot(context=context, actor_ref="character:one")

@pytest.mark.parametrize('supports_delta', [False, True])
def test_silent_expired_population_lease_closes_only_expired_subscriber(monkeypatch, supports_delta):
    from fastapi.testclient import TestClient
    from app import main
    from app.ws_protocol import GameplayMirrorCapabilityOffer
    now = [100]
    monkeypatch.setattr(main, 'time', lambda: now[0])
    monkeypatch.setattr(main.settings, 'population_runtime_profile', 'benchmark_1x')
    with TestClient(main.component_app, client=('127.0.0.1', 47113)) as client:
        owner = main.runtime_execution
        def configure():
            actor = 'character:' + main.population_roster.actor_ids[0]
            credentials = [main.websocket_session_auth_service.create_trusted_local_launch_credential(
                principal_ref=f'lease:{expiry}', allowed_actor_refs=(actor,), issued_at=100, expires_at=expiry)
                for expiry in (110, 200)]
            return actor, credentials
        actor, credentials = owner.submit(configure).result(5)
        with client.websocket_connect('/ws') as expired, client.websocket_connect('/ws') as healthy:
            sessions = []
            for socket, credential in zip((expired, healthy), credentials):
                socket.send_json({'message_type':'websocket_session_bind', 'payload':{
                    'credential_kind':'trusted_local_launch', 'credential':credential, 'protocol_version':2,
                    'capability_offer':GameplayMirrorCapabilityOffer(protocol_version=2, supports_snapshot=True,
                        supports_delta=supports_delta, supports_receipt=True,
                        projection_schemas=('gameplay_runtime_state.godot.v1',)).model_dump(mode='json')}})
                assert socket.receive_json()['payload']['accepted']
                sessions.append(socket.receive_json()['payload']['session_ref'])
                socket.send_json({'message_type':'gameplay_mirror_subscribe', 'payload':{'actor_ref':actor}})
                assert socket.receive_json()['payload']['accepted']
                assert socket.receive_json()['payload']['delivery_sequence'] == 1
            now[0] = 111
            def advance():
                driver = main._population_runtime_driver
                result = driver.tick(driver.current_tick + driver.window_size)
                assert not result.rejected_windows
            owner.submit(advance).result(5)
            closed = expired.receive_json()
            assert closed['message_type'] == 'websocket_session_revoked', closed
            assert closed['payload']['reason_code'] == 'websocket_session_lease_expired'
            expired.send_json({'message_type':'websocket_session_revocation_received', 'payload':closed['payload']})
            update = healthy.receive_json()
            assert update['message_type'] == 'gameplay_mirror_delivery'
            assert update['payload']['delivery_kind'] == ('delta' if supports_delta else 'snapshot')
            assert owner.submit(lambda: main.gameplay_mirror_subscription_registry.subscribed_session_refs(actor_ref=actor)).result(5) == (sessions[1],)
            assert owner.submit(lambda: main.websocket_session_auth_service.resolve_binding(sessions[0])).result(5) is None


def test_encoding_crosses_lease_deadline_without_sending_or_advancing_base(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.ws_protocol import GameplayMirrorCapabilityOffer
    now = [100]
    monkeypatch.setattr(main, 'time', lambda: now[0])
    monkeypatch.setattr(main.settings, 'population_runtime_profile', 'benchmark_1x')
    original_prepare = main.GameplayMirrorDeltaEncoder.prepare
    original_sent = main.GameplayMirrorDeltaEncoder.sent
    sent, encoded = [], []
    def prepare(encoder, message, **kwargs):
        result = original_prepare(encoder, message, **kwargs)
        if message.get('payload', {}).get('delivery_sequence') == 2:
            assert now[0] == 109
            assert result[0]['payload']['delivery_kind'] == 'delta'
            encoded.append(encoder)
            now[0] = 110
        return result
    def mark_base(encoder, message, target):
        if 'delivery_sequence' in message.get('payload', {}):
            sent.append(message['payload']['delivery_sequence'])
        return original_sent(encoder, message, target)
    monkeypatch.setattr(main.GameplayMirrorDeltaEncoder, 'prepare', prepare)
    monkeypatch.setattr(main.GameplayMirrorDeltaEncoder, 'sent', mark_base)
    with TestClient(main.component_app, client=('127.0.0.1', 47114)) as client:
        owner = main.runtime_execution
        marked = []
        registry = main.gameplay_mirror_connection_registry
        original_mark_sent = registry.mark_sent
        def mark_receipt(**kwargs):
            marked.append(kwargs['delivery_sequence'])
            return original_mark_sent(**kwargs)
        monkeypatch.setattr(registry, 'mark_sent', mark_receipt)
        def configure():
            actor = 'character:' + main.population_roster.actor_ids[0]
            credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
                principal_ref='lease-encode', allowed_actor_refs=(actor,), issued_at=100, expires_at=110)
            return actor, credential
        actor, credential = owner.submit(configure).result(5)
        with client.websocket_connect('/ws') as socket:
            socket.send_json({'message_type':'websocket_session_bind', 'payload':{
                'credential_kind':'trusted_local_launch', 'credential':credential, 'protocol_version':2,
                'capability_offer':GameplayMirrorCapabilityOffer(protocol_version=2, supports_snapshot=True,
                    supports_delta=True, supports_receipt=True,
                    projection_schemas=('gameplay_runtime_state.godot.v1',)).model_dump(mode='json')}})
            assert socket.receive_json()['payload']['accepted']
            session = socket.receive_json()['payload']['session_ref']
            socket.send_json({'message_type':'gameplay_mirror_subscribe', 'payload':{'actor_ref':actor}})
            assert socket.receive_json()['payload']['accepted']
            assert socket.receive_json()['payload']['delivery_sequence'] == 1
            now[0] = 109
            def tick():
                driver = main._population_runtime_driver
                assert not driver.tick(driver.current_tick + driver.window_size).rejected_windows
            owner.submit(tick).result(5)
            revoked = socket.receive_json()
            assert revoked['message_type'] == 'websocket_session_revoked', revoked
            assert revoked['payload']['reason_code'] == 'websocket_session_lease_expired'
            socket.send_json({'message_type':'websocket_session_revocation_received', 'payload':revoked['payload']})
            assert marked == [1] and sent == [1]
            assert len(encoded) == 1 and encoded[0]._bases == {}
            assert owner.submit(lambda: main.websocket_session_auth_service.resolve_binding(session)).result(5) is None
            assert owner.submit(lambda: main.gameplay_mirror_subscription_registry.subscribed_session_refs(actor_ref=actor)).result(5) == ()
