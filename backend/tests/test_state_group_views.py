from __future__ import annotations

import pytest

from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import (
    StateGroupConsumerViewPolicy,
    StateGroupViewError,
    StateGroupViewProjector,
)


def _state():
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="core.resources", definition_version="1.0.0", projection_schema_version=1))
    registry.register(StateGroupDefinition(group_id="core.relationships", definition_version="1.0.0", projection_schema_version=1))
    state = CharacterGameRuntimeStateBuilder(registry).build(
        actor_ref="actor:char_a",
        enabled_group_ids=("core.resources", "core.relationships"),
        group_payloads={
            "core.resources": {"stamina": 7, "max_stamina": 10, "internal_cost_basis": "private"},
            "core.relationships": {"public_disposition": "calm", "private_belief": "untrusted"},
        },
        source_revision_vector={"stream:char_a": 4},
        registry_revision="registry:core:v1",
        world_config_revision="world:demo:v1",
        active_patch_set_revision="patches:demo:v1",
    )
    return state


def _projector() -> StateGroupViewProjector:
    return StateGroupViewProjector(
        [
            StateGroupConsumerViewPolicy(
                group_id="core.resources",
                godot_allowed_fields=("stamina", "max_stamina"),
                mind_allowed_fields=("stamina",),
                debug_allowed_fields=("stamina", "max_stamina", "internal_cost_basis"),
                debug_principal_refs=("principal:debug-admin",),
            ),
            StateGroupConsumerViewPolicy(
                group_id="core.relationships",
                mind_allowed_fields=("public_disposition",),
                debug_allowed_fields=("public_disposition", "private_belief"),
                debug_principal_refs=("principal:debug-admin",),
            ),
        ]
    )


def test_consumer_views_only_remove_or_reduce_authoritative_payload_fields() -> None:
    state = _state()
    projector = _projector()

    authority = projector.authority_view(state, allowed_group_ids=("core.resources", "core.relationships"))
    godot = projector.godot_view(state, allowed_group_ids=("core.resources", "core.relationships"))
    mind = projector.mind_frame_view(state, allowed_group_ids=("core.resources", "core.relationships"))

    assert authority.groups["core.resources"].payload == {
        "stamina": 7,
        "max_stamina": 10,
        "internal_cost_basis": "private",
    }
    assert godot.groups["core.resources"].payload == {"stamina": 7, "max_stamina": 10}
    assert "core.relationships" not in godot.groups
    assert mind.groups["core.resources"].payload == {"stamina": 7}
    assert mind.groups["core.relationships"].payload == {"public_disposition": "calm"}


def test_debug_view_requires_a_policy_authorized_principal() -> None:
    state = _state()
    projector = _projector()

    denied = projector.debug_view(
        state,
        allowed_group_ids=("core.resources", "core.relationships"),
        principal_ref="principal:viewer",
    )
    allowed = projector.debug_view(
        state,
        allowed_group_ids=("core.resources", "core.relationships"),
        principal_ref="principal:debug-admin",
    )

    assert denied.groups == {}
    assert allowed.groups["core.relationships"].payload == {
        "public_disposition": "calm",
        "private_belief": "untrusted",
    }


def test_view_projector_fails_closed_when_an_allowed_group_has_no_policy() -> None:
    state = _state()
    projector = StateGroupViewProjector(
        [StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("stamina",))]
    )

    with pytest.raises(StateGroupViewError, match="view_policy_missing"):
        projector.godot_view(state, allowed_group_ids=("core.resources", "core.relationships"))
