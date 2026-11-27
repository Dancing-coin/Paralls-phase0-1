from app.main import _handle_envelope, reset_runtime_state
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector
from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope
from app.gameplay.models import AtomicEventBatch, GameplayEvent, GameplayOutboxEntry, IdempotencyRecord


def _commit_project_drought_advisory(store, *, jurisdiction_ref: str) -> None:
    stream_id = f"gameplay:government:advisory:{jurisdiction_ref}"
    event = GameplayEvent(
        event_id=f"event:government:drought-advisory:{jurisdiction_ref}",
        event_type="gameplay.government.drought_advisory_issued",
        schema_version=1,
        stream_id=stream_id,
        stream_revision=0,
        global_sequence=0,
        transaction_id=f"tx:government:drought-advisory:{jurisdiction_ref}",
        command_id=f"command:government:drought-advisory:{jurisdiction_ref}",
        causation_id=f"cause:government:drought-advisory:{jurisdiction_ref}",
        correlation_id=f"corr:government:drought-advisory:{jurisdiction_ref}",
        visibility_policy="project",
        payload={
            "advisory_ref": f"advisory:drought:{jurisdiction_ref}",
            "jurisdiction_ref": jurisdiction_ref,
            "weather_ref": "weather:drought",
            "ecology_stream_id": f"gameplay:ecology:region:{jurisdiction_ref}",
            "ecology_event_revision": 2,
        },
    )
    batch = AtomicEventBatch(
        transaction_id=event.transaction_id,
        command_id=event.command_id,
        expected_stream_revisions={stream_id: 0},
        idempotency_record=IdempotencyRecord(
            principal_ref="authority:government",
            idempotency_key=f"government:drought-advisory:{jurisdiction_ref}",
            payload_digest=f"sha256:government-drought-advisory:{jurisdiction_ref}",
        ),
        events=[event],
        outbox_entries=[
            GameplayOutboxEntry(
                outbox_id=f"outbox:{event.event_id}",
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                global_sequence=0,
                topic="world.government.drought_advisory_projection",
                audience="project",
                payload_projection={
                    "advisory_ref": event.payload["advisory_ref"],
                    "jurisdiction_ref": jurisdiction_ref,
                    "event_type": event.event_type,
                },
            )
        ],
        result_digest=f"sha256:government-drought-advisory:{jurisdiction_ref}",
    )
    assert store.append_batch(batch).committed


def test_websocket_session_bind_keeps_backend_granted_multi_actor_scope_on_connection() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:a", "actor:b"),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=20)

    messages = _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "protocol_version": 1,
            },
        ),
        connection_context=context,
    )

    assert messages[0]["payload"]["accepted"] is True
    assert messages[1]["payload"]["allowed_actor_refs"] == ["actor:a", "actor:b"]
    assert context.binding is not None
    assert context.binding.allowed_actor_refs == ("actor:a", "actor:b")


def test_websocket_session_bind_rejects_non_loopback_peer_without_client_scope_fallback() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:a",),
        issued_at=10,
        expires_at=20,
    )

    messages = _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "protocol_version": 1,
            },
        ),
        connection_context=WebSocketConnectionContext(remote_host="198.51.100.8", observed_at=11),
    )

    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_code"] == "trusted_local_launch_requires_loopback"


def test_government_drought_advisory_websocket_subscription_uses_only_bound_jurisdiction_scope() -> None:
    import app.main as main

    jurisdiction_ref = "jurisdiction:websocket-advisory"
    reset_runtime_state()
    _commit_project_drought_advisory(main.gameplay_event_store, jurisdiction_ref=jurisdiction_ref)
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:advisory",
        allowed_actor_refs=("actor:unrelated",),
        allowed_government_drought_advisory_jurisdiction_refs=(jurisdiction_ref,),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11)
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )

    accepted = _handle_envelope(
        Envelope(
            message_type="gameplay_government_drought_advisory_subscribe",
            payload={"jurisdiction_ref": jurisdiction_ref},
        ),
        connection_context=context,
    )
    foreign = _handle_envelope(
        Envelope(
            message_type="gameplay_government_drought_advisory_subscribe",
            payload={"jurisdiction_ref": "jurisdiction:foreign"},
        ),
        connection_context=context,
    )

    assert accepted[0]["payload"]["accepted"] is True
    assert accepted[1]["message_type"] == "government_drought_advisory_projection"
    assert accepted[1]["payload"]["jurisdiction_ref"] == jurisdiction_ref
    assert foreign[0]["payload"]["accepted"] is False
    assert foreign[0]["payload"]["error_code"] == "government_drought_advisory_scope_unauthorized"


def test_dispatched_government_advisory_outbox_delivers_only_to_the_bound_presentation_session() -> None:
    import app.main as main

    jurisdiction_ref = "jurisdiction:websocket-dispatch"
    reset_runtime_state()
    _commit_project_drought_advisory(main.gameplay_event_store, jurisdiction_ref=jurisdiction_ref)
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:dispatch",
        allowed_actor_refs=("actor:unrelated",),
        allowed_government_drought_advisory_jurisdiction_refs=(jurisdiction_ref,),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11, connection_ref="connection:dispatch")
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )
    assert context.binding is not None
    _handle_envelope(
        Envelope(
            message_type="gameplay_government_drought_advisory_subscribe",
            payload={"jurisdiction_ref": jurisdiction_ref},
        ),
        connection_context=context,
    )
    sent: list[dict[str, object]] = []
    main.gameplay_mirror_connection_registry.register(
        session_ref=context.binding.session_ref,
        connection_ref=context.connection_ref,
        connection_epoch=context.binding.connection_epoch,
        deliver=sent.append,
    )

    dispatched = main.gameplay_outbox_dispatcher.dispatch_pending()

    assert dispatched.published_count == 1
    assert sent[0]["message_type"] == "government_drought_advisory_delivery"
    assert sent[0]["payload"]["jurisdiction_ref"] == jurisdiction_ref
    assert "actor_ref" not in str(sent[0])


def test_embodied_controller_bind_uses_connection_peer_host_not_default_loopback() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id="actor:a",
        controller_instance_id="controller:a",
        issued_at=10,
        expires_at=20,
    )

    messages = _handle_envelope(
        Envelope(
            message_type="embodied_controller_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "actor_id": "actor:a",
                "controller_instance_id": "controller:a",
                "protocol_version": 1,
            },
        ),
        connection_context=WebSocketConnectionContext(remote_host="198.51.100.8", observed_at=11),
    )

    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_code"] == "trusted_local_launch_requires_loopback"


def test_gameplay_mirror_websocket_routes_use_backend_published_view_and_bound_scope() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11)
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "protocol_version": 1,
                "capability_offer": {
                    "protocol_version": 2,
                    "supports_snapshot": True,
                    "supports_receipt": True,
                    "projection_schemas": ["gameplay_runtime_state.godot.v1"],
                },
            },
        ),
        connection_context=context,
    )
    main.gameplay_godot_projection_repository.publish(_godot_view("actor:visible"))

    subscribed = _handle_envelope(
        Envelope(
            message_type="gameplay_mirror_subscribe",
            payload={"actor_ref": "actor:visible", "requested_state_group_ids": ("core.resources",)},
        ),
        connection_context=context,
    )

    assert subscribed[0]["payload"]["accepted"] is True
    assert subscribed[1]["message_type"] == "gameplay_runtime_state_projection"
    assert subscribed[1]["actor_ref"] == "actor:visible"
    assert subscribed[1]["groups"]["core.resources"]["payload"] == {"current": 7}

    unauthorized = _handle_envelope(
        Envelope(message_type="gameplay_mirror_snapshot_request", payload={"actor_ref": "actor:hidden"}),
        connection_context=context,
    )
    assert unauthorized[0]["payload"]["error_code"] == "mirror_scope_unauthorized"

    unsubscribed = _handle_envelope(
        Envelope(message_type="gameplay_mirror_unsubscribe", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )
    assert unsubscribed[0]["payload"]["subscription_removed"] is True
    resync = _handle_envelope(
        Envelope(message_type="gameplay_mirror_snapshot_request", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )
    assert resync[0]["payload"]["error_code"] == "mirror_subscription_required"


def test_information_report_read_uses_bound_actor_scope_and_authoritative_world_clock(monkeypatch) -> None:
    import hashlib
    import hmac

    import app.main as main
    from app.gameplay.event_schema_registry import (
        EventSchemaRegistration,
        EventSchemaRegistry,
        register_social_delivery_event_schemas,
    )
    from app.gameplay.event_store import GameplayEventStore
    from app.gameplay.information_event_schema import register_information_event_schemas
    from app.gameplay.information_runtime import (
        InformationAuthority,
        SiegeReportPublicationReceipt,
    )
    from app.gameplay.settlement_plan import build_atomic_event_batch

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("character:defender-1",),
        issued_at=10,
        expires_at=100,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11)
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )
    registry = EventSchemaRegistry()
    register_social_delivery_event_schemas(registry)
    register_information_event_schemas(registry)
    registry.register(EventSchemaRegistration(
        "gameplay.social.knowledge_observed", 1, "sha256:test:information-read-source:v1"
    ))
    store = GameplayEventStore(event_schema_registry=registry)
    source_batch = build_atomic_event_batch(
        command_id="information-read:source",
        principal_ref="authority:facility:gate",
        stream_id="gameplay:facility:east-gate:integrity",
        expected_revision=0,
        event_specs=(("gameplay.social.knowledge_observed", {
            "fact_type": "fact:facility:east-gate:integrity",
            "integrity": "72",
        }),),
        idempotency_key="information-read:source",
        causation_id="event:facility-impact",
        correlation_id="correlation:east-gate",
    )
    source_result = store.append_batch(source_batch)
    assert source_result.committed
    source = store.get_event(source_result.committed_event_ids[0])
    report_secret = "fixture-key"
    receipt = SiegeReportPublicationReceipt(
        authority_ref="authority:information:report-publisher",
        receipt_id="receipt:east-gate:defender",
        report_ref="report:east-gate",
        recipient_ref="character:defender-1",
        summary="The east gate is breached.",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        effective_from=10,
        effective_to=20,
        signature="0" * 64,
    )
    signature = hmac.new(report_secret.encode(), receipt.canonical_bytes(), hashlib.sha256).hexdigest()
    authority = InformationAuthority(
        store=store,
        report_authority_secrets={receipt.authority_ref: report_secret},
    )
    publication = authority.publish_siege_report(
        receipt=receipt.model_copy(update={"signature": signature}), world_now=15,
    )
    assert publication.committed
    main.m6_5_siege_runtime = type("SiegeRuntimeStub", (), {"information": authority})()
    monkeypatch.setattr(main, "_session_world_clock_tick", lambda: 16)

    delivery_event_id, = publication.delivery_append_result.committed_event_ids
    knowledge = authority.update_from_delivery(
        delivery=store.get_event(delivery_event_id),
        world_now=15,
        command_id="information-read:knowledge",
        idempotency_key="information-read:knowledge",
        correlation_id="correlation:east-gate",
    )
    assert knowledge.committed
    report_event_id, = publication.report_append_result.committed_event_ids

    knowledge_result = _handle_envelope(
        Envelope(message_type="information_knowledge_read", payload={
            "actor_ref": "character:defender-1",
            "report_event_id": report_event_id,
            "as_of_tick": 16,
        }),
        connection_context=context,
    )

    assert knowledge_result[0]["payload"]["accepted"] is True
    assert knowledge_result[0]["payload"]["knowledge"] == {
        "fact_type": "fact:information:siege:report_knowledge",
        "recipient_ref": "character:defender-1",
        "report_event_id": report_event_id,
        "source_owner_ref": "Information",
        "source_revision": 1,
        "event_time": 15,
        "known_time": 15,
        "freshness": 1,
    }

    unauthorized_knowledge = _handle_envelope(
        Envelope(message_type="information_knowledge_read", payload={
            "actor_ref": "character:other",
            "report_event_id": report_event_id,
            "as_of_tick": 16,
        }),
        connection_context=context,
    )
    future_knowledge = _handle_envelope(
        Envelope(message_type="information_knowledge_read", payload={
            "actor_ref": "character:defender-1",
            "report_event_id": report_event_id,
            "as_of_tick": 17,
        }),
        connection_context=context,
    )
    assert unauthorized_knowledge[0]["payload"]["accepted"] is False
    assert future_knowledge[0]["payload"]["accepted"] is False

    result = _handle_envelope(
        Envelope(message_type="information_report_read", payload={
            "actor_ref": "character:defender-1",
            "report_ref": "report:east-gate",
            "as_of_tick": 16,
        }),
        connection_context=context,
    )

    assert result[0]["payload"]["accepted"] is True
    assert result[0]["payload"]["report"] == {
        "fact_type": "fact:information:siege:report",
        "report_ref": "report:east-gate",
        "recipient_ref": "character:defender-1",
        "summary": "The east gate is breached.",
        "source_owner_ref": "Information",
        "source_revision": 1,
        "event_time": 15,
        "known_time": 15,
        "freshness": 1,
    }

    forbidden = _handle_envelope(
        Envelope(message_type="information_report_read", payload={
            "actor_ref": "character:other",
            "report_ref": "report:east-gate",
            "as_of_tick": 16,
        }),
        connection_context=context,
    )
    future = _handle_envelope(
        Envelope(message_type="information_report_read", payload={
            "actor_ref": "character:defender-1",
            "report_ref": "report:east-gate",
            "as_of_tick": 17,
        }),
        connection_context=context,
    )
    assert forbidden[0]["payload"] == future[0]["payload"]
    assert forbidden[0]["payload"]["accepted"] is False


def test_gameplay_mirror_subscription_fails_closed_without_backend_projection() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11)
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )

    messages = _handle_envelope(
        Envelope(message_type="gameplay_mirror_subscribe", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )

    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_code"] == "mirror_projection_unavailable"


def test_gameplay_mirror_resync_requires_an_existing_authorized_subscription() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11)
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )
    main.gameplay_godot_projection_repository.publish(_godot_view("actor:visible"))

    unsubscribed = _handle_envelope(
        Envelope(message_type="gameplay_mirror_resync_request", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )
    unauthorized = _handle_envelope(
        Envelope(message_type="gameplay_mirror_resync_request", payload={"actor_ref": "actor:hidden"}),
        connection_context=context,
    )

    assert unsubscribed[0]["payload"]["error_code"] == "mirror_subscription_required"
    assert unauthorized[0]["payload"]["error_code"] == "mirror_scope_unauthorized"


def test_gameplay_mirror_receipt_is_connection_local_and_does_not_mutate_authority_store() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11, connection_ref="connection:receipt")
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "protocol_version": 1,
                "capability_offer": {
                    "protocol_version": 2,
                    "supports_snapshot": True,
                    "supports_receipt": True,
                    "projection_schemas": ["gameplay_runtime_state.godot.v1"],
                },
            },
        ),
        connection_context=context,
    )
    assert context.binding is not None
    main.gameplay_mirror_connection_registry.register(
        session_ref=context.binding.session_ref,
        connection_ref=context.connection_ref,
        connection_epoch=context.binding.connection_epoch,
        deliver=lambda _payload: None,
    )
    main.gameplay_mirror_connection_registry.deliver(
        context.binding.session_ref,
        {"actor_ref": "actor:visible", "projection_kind": "gameplay_runtime_state.godot.v1", "facade_revision": "facade:1"},
    )
    authority_snapshot = main.gameplay_event_store.export_snapshot()

    receipt = _handle_envelope(
        Envelope(
            message_type="gameplay_mirror_receipt",
            payload={"connection_epoch": context.binding.connection_epoch, "delivery_sequence": 1},
        ),
        connection_context=context,
    )

    assert receipt[0]["payload"]["accepted"] is True
    assert receipt[0]["payload"]["route"] == "gameplay_mirror_receipt"
    assert main.gameplay_event_store.export_snapshot() == authority_snapshot


def test_websocket_bind_rejects_capability_offer_without_snapshot_support_before_connection_registration() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11)

    messages = _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "protocol_version": 1,
                "capability_offer": {
                    "protocol_version": 2,
                    "supports_snapshot": False,
                    "projection_schemas": ["gameplay_runtime_state.godot.v1"],
                },
            },
        ),
        connection_context=context,
    )

    assert messages[0]["payload"]["error_code"] == "mirror_capability_incompatible"
    assert context.binding is None


def _godot_view(actor_ref: str):
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="core.resources", definition_version="1", projection_schema_version=1))
    state = CharacterGameRuntimeStateBuilder(registry).build(
        actor_ref=actor_ref,
        enabled_group_ids=("core.resources",),
        group_payloads={"core.resources": {"current": 7, "private": "hidden"}},
        source_revision_vector={actor_ref: 1},
        registry_revision="registry:v1",
        world_config_revision="world:v1",
        active_patch_set_revision="patch:v1",
    )
    return StateGroupViewProjector(
        [StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("current",))]
    ).godot_view(state, allowed_group_ids=("core.resources",))
