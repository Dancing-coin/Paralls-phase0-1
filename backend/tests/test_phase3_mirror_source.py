from __future__ import annotations

from time import time

import pytest
from fastapi.testclient import TestClient

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.godot_mirror_delivery import GameplayGodotProjectionPublisher, GameplayGodotProjectionRepository
from app.gameplay.models import ProjectionRefreshHint
from app.gameplay.phase3_mirror_source import (
    Phase3MirrorActorConfiguration,
    Phase3MirrorSource,
    Phase3MirrorSourceError,
    install_phase3_mirror_sources,
)
from app.gameplay.runtime_state import StateGroupDefinition
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy


def _configuration(actor_ref: str = "actor:configured") -> Phase3MirrorActorConfiguration:
    return Phase3MirrorActorConfiguration(
        actor_ref=actor_ref,
        state_group_definitions=(
            StateGroupDefinition(group_id="core.resources", definition_version="1", projection_schema_version=1),
        ),
        godot_view_policies=(
            StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("entries",)),
        ),
        godot_allowed_group_ids=("core.resources",),
        registry_revision="registry:phase3:v1",
        world_config_revision="world:phase3:v1",
        active_patch_set_revision="patch:phase3:v1",
    )


def _append_resource_state(store: GameplayEventStore, *, actor_ref: str, command_id: str = "mirror-source") -> None:
    transaction_id = f"tx:{command_id}"
    lifecycle_stream = f"gameplay:state_groups:{actor_ref}"
    resource_stream = f"gameplay:resources:{actor_ref}"
    events = [
        {
            "event_id": f"evt:{command_id}:materialize",
            "event_type": "gameplay.state_group.materialized",
            "schema_version": 1,
            "stream_id": lifecycle_stream,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": transaction_id,
            "command_id": command_id,
            "causation_id": f"cmd:{command_id}",
            "correlation_id": f"corr:{command_id}",
            "visibility_policy": "authority_only",
            "payload": {
                "actor_ref": actor_ref,
                "group_id": "core.resources",
                "definition_version": "1",
                "source_patch_revision": "patch:phase3:v1",
            },
        },
        {
            "event_id": f"evt:{command_id}:enable",
            "event_type": "gameplay.state_group.enabled",
            "schema_version": 1,
            "stream_id": lifecycle_stream,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": transaction_id,
            "command_id": command_id,
            "causation_id": f"cmd:{command_id}",
            "correlation_id": f"corr:{command_id}",
            "visibility_policy": "authority_only",
            "payload": {
                "actor_ref": actor_ref,
                "group_id": "core.resources",
                "definition_version": "1",
                "source_patch_revision": "patch:phase3:v1",
            },
        },
        {
            "event_id": f"evt:{command_id}:stamina",
            "event_type": "gameplay.resource.materialized",
            "schema_version": 1,
            "stream_id": resource_stream,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": transaction_id,
            "command_id": command_id,
            "causation_id": f"cmd:{command_id}",
            "correlation_id": f"corr:{command_id}",
            "visibility_policy": "authority_only",
            "payload": {
                "actor_ref": actor_ref,
                "resource_id": "core.stamina",
                "minimum": 0,
                "maximum": 10,
                "current": 7,
            },
        },
    ]
    result = store.append_batch(
        {
            "transaction_id": transaction_id,
            "command_id": command_id,
            "expected_stream_revisions": {lifecycle_stream: 0, resource_stream: 0},
            "pinned_revisions": {},
            "events": events,
            "idempotency_record": {
                "principal_ref": "test:mirror-source",
                "idempotency_key": command_id,
                "payload_digest": f"sha256:{command_id}",
            },
            "outbox_entries": [],
            "result_digest": f"sha256:{command_id}",
            "projection_refresh_hints": [],
        }
    )
    assert result.committed


def test_configured_phase3_source_rebuilds_only_committed_backend_state() -> None:
    store = GameplayEventStore()
    configuration = _configuration()
    source = Phase3MirrorSource.create(configuration=configuration, store=store)

    _append_resource_state(store, actor_ref=configuration.actor_ref)
    view = source.godot_view()

    assert view.actor_ref == configuration.actor_ref
    assert view.consumer == "godot"
    assert view.groups["core.resources"].payload == {
        "entries": {
            "core.stamina": {
                "current": 7,
                "minimum": 0,
                "maximum": 10,
                "reserved": 0,
                "available": 7,
                "source_event_id": "evt:mirror-source:stamina",
            }
        }
    }


def test_installer_registers_explicit_backend_actor_source_without_scene_identity() -> None:
    store = GameplayEventStore()
    configuration = _configuration("actor:production-config")
    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)

    installed = install_phase3_mirror_sources(
        configurations=(configuration,),
        store=store,
        publisher=publisher,
    )
    _append_resource_state(store, actor_ref=configuration.actor_ref)
    transaction = store.read_transactions()[0].model_copy(
        update={
            "projection_refresh_hints": [
                ProjectionRefreshHint(
                    projection_id="godot_mirror",
                    stream_id=f"gameplay:resources:{configuration.actor_ref}",
                    reason="resource_state_changed",
                    actor_refs=(configuration.actor_ref,),
                )
            ]
        }
    )

    refreshed = publisher.after_transaction_dispatched(transaction)

    assert installed == ("actor:production-config",)
    assert refreshed.published_actor_refs == ("actor:production-config",)
    assert repository.view_for("actor:production-config").groups["core.resources"].payload["entries"]["core.stamina"]["available"] == 7


def test_phase3_mirror_configuration_fails_closed_for_unimplemented_group_or_missing_policy() -> None:
    with pytest.raises(ValueError, match="phase3_mirror_state_group_unsupported"):
        Phase3MirrorActorConfiguration(
            actor_ref="actor:configured",
            state_group_definitions=(StateGroupDefinition(group_id="core.inventory", definition_version="1", projection_schema_version=1),),
            registry_revision="registry:v1",
            world_config_revision="world:v1",
            active_patch_set_revision="patch:v1",
        )
    with pytest.raises(ValueError, match="phase3_mirror_godot_policy_required"):
        Phase3MirrorActorConfiguration(
            actor_ref="actor:configured",
            state_group_definitions=(StateGroupDefinition(group_id="core.resources", definition_version="1", projection_schema_version=1),),
            godot_allowed_group_ids=("core.resources",),
            registry_revision="registry:v1",
            world_config_revision="world:v1",
            active_patch_set_revision="patch:v1",
        )


def test_installer_rejects_duplicate_actor_configuration() -> None:
    configuration = _configuration()
    with pytest.raises(Phase3MirrorSourceError, match="phase3_mirror_actor_duplicate"):
        install_phase3_mirror_sources(
            configurations=(configuration, configuration),
            store=GameplayEventStore(),
            publisher=GameplayGodotProjectionPublisher(repository=GameplayGodotProjectionRepository()),
        )


def test_configured_actor_sources_ignore_other_actors_lifecycle_events() -> None:
    store = GameplayEventStore()
    first = _configuration("actor:configured-first")
    second = _configuration("actor:configured-second")
    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)
    install_phase3_mirror_sources(configurations=(first, second), store=store, publisher=publisher)

    _append_resource_state(store, actor_ref=first.actor_ref, command_id="first")
    _append_resource_state(store, actor_ref=second.actor_ref, command_id="second")

    assert publisher.refresh_actor(actor_ref=first.actor_ref).actor_ref == first.actor_ref
    assert publisher.refresh_actor(actor_ref=second.actor_ref).actor_ref == second.actor_ref


def test_websocket_reads_a_configured_phase3_source_through_backend_session_scope(monkeypatch) -> None:
    import app.main as main

    configuration = _configuration("actor:configured-websocket")
    monkeypatch.setattr(main.settings, "gameplay_mirror_phase3_actor_configs", [configuration.model_dump(mode="json")])
    main.reset_runtime_state()
    _append_resource_state(main.gameplay_event_store, actor_ref=configuration.actor_ref)
    now = int(time())
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:configured-websocket",
        allowed_actor_refs=(configuration.actor_ref,),
        issued_at=now,
        expires_at=now + 60,
    )

    client = TestClient(main.app, client=("127.0.0.1", 47001))
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "websocket_session_bind",
                "payload": {
                    "credential_kind": "trusted_local_launch",
                    "credential": credential,
                    "protocol_version": 1,
                },
            }
        )
        assert websocket.receive_json()["payload"]["accepted"] is True
        assert websocket.receive_json()["payload"]["allowed_actor_refs"] == [configuration.actor_ref]
        websocket.send_json(
            {
                "message_type": "gameplay_mirror_subscribe",
                "payload": {"actor_ref": configuration.actor_ref},
            }
        )
        assert websocket.receive_json()["payload"]["accepted"] is True
        projection = websocket.receive_json()

    assert projection["message_type"] == "gameplay_runtime_state_projection"
    assert projection["actor_ref"] == configuration.actor_ref
    assert projection["groups"]["core.resources"]["payload"]["entries"]["core.stamina"]["available"] == 7
