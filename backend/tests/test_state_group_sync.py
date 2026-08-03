from __future__ import annotations

import pytest

from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_sync import StateGroupSyncError, StateGroupSyncService


def _state(*, stamina: int, include_relationships: bool):
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="core.resources", definition_version="1.0.0", projection_schema_version=1))
    registry.register(StateGroupDefinition(group_id="core.relationships", definition_version="1.0.0", projection_schema_version=1))
    groups = {"core.resources": {"stamina": stamina}}
    enabled = ["core.resources"]
    if include_relationships:
        groups["core.relationships"] = {"public_disposition": "calm"}
        enabled.append("core.relationships")
    return CharacterGameRuntimeStateBuilder(registry).build(
        actor_ref="actor:char_a",
        enabled_group_ids=enabled,
        group_payloads=groups,
        source_revision_vector={"stream:char_a": stamina},
        registry_revision="registry:core:v1",
        world_config_revision="world:demo:v1",
        active_patch_set_revision="patches:demo:v1",
    )


def test_delta_uses_exact_base_and_reconstructs_changed_and_added_groups() -> None:
    service = StateGroupSyncService()
    base = service.snapshot(_state(stamina=7, include_relationships=False), schema_capabilities=("runtime_state.v1",))
    target = service.snapshot(_state(stamina=5, include_relationships=True), schema_capabilities=("runtime_state.v1",))

    delta = service.delta(base, target, confirmed_prediction_ids=("prediction:stamina",))
    rebuilt = service.apply_delta(base, delta, supported_schema_capabilities=("runtime_state.v1",))

    assert set(delta.changed_group_envelopes) == {"core.resources", "core.relationships"}
    assert delta.removed_group_ids == ()
    assert delta.confirmed_prediction_ids == ("prediction:stamina",)
    assert rebuilt.snapshot_checksum == target.snapshot_checksum
    assert rebuilt.groups["core.resources"].payload == {"stamina": 5}
    assert rebuilt.enabled_state_groups == ("core.relationships", "core.resources")


def test_delta_rejects_wrong_base_checksum_and_unsupported_capability() -> None:
    service = StateGroupSyncService()
    base = service.snapshot(_state(stamina=7, include_relationships=False), schema_capabilities=("runtime_state.v1",))
    target = service.snapshot(
        _state(stamina=5, include_relationships=False),
        schema_capabilities=("runtime_state.v1", "runtime_state.experimental"),
    )
    delta = service.delta(base, target)

    with pytest.raises(StateGroupSyncError, match="projection_schema_unsupported"):
        service.apply_delta(base, delta, supported_schema_capabilities=("runtime_state.v1",))
    with pytest.raises(StateGroupSyncError, match="facade_revision_conflict"):
        service.apply_delta(
            service.snapshot(_state(stamina=6, include_relationships=False), schema_capabilities=("runtime_state.v1",)),
            delta,
            supported_schema_capabilities=("runtime_state.v1", "runtime_state.experimental"),
        )

    tampered = base.__class__(
        actor_ref=base.actor_ref,
        facade_revision=base.facade_revision,
        source_revision_vector=base.source_revision_vector,
        schema_capabilities=base.schema_capabilities,
        enabled_state_groups=base.enabled_state_groups,
        groups=base.groups,
        snapshot_checksum="sha256:tampered",
    )
    with pytest.raises(StateGroupSyncError, match="snapshot_checksum_invalid"):
        service.apply_delta(
            tampered,
            delta,
            supported_schema_capabilities=("runtime_state.v1", "runtime_state.experimental"),
        )


def test_delta_carries_removed_groups_and_rejects_target_checksum_mismatch() -> None:
    service = StateGroupSyncService()
    base = service.snapshot(_state(stamina=7, include_relationships=True), schema_capabilities=("runtime_state.v1",))
    target = service.snapshot(_state(stamina=7, include_relationships=False), schema_capabilities=("runtime_state.v1",))
    delta = service.delta(base, target)

    assert delta.removed_group_ids == ("core.relationships",)
    assert service.apply_delta(base, delta, supported_schema_capabilities=("runtime_state.v1",)).groups == target.groups

    tampered_delta = delta.__class__(
        actor_ref=delta.actor_ref,
        base_facade_revision=delta.base_facade_revision,
        target_facade_revision=delta.target_facade_revision,
        target_source_revision_vector=delta.target_source_revision_vector,
        target_schema_capabilities=delta.target_schema_capabilities,
        target_enabled_state_groups=delta.target_enabled_state_groups,
        changed_group_envelopes=delta.changed_group_envelopes,
        removed_group_ids=delta.removed_group_ids,
        confirmed_prediction_ids=delta.confirmed_prediction_ids,
        rejected_predictions=delta.rejected_predictions,
        target_snapshot_checksum="sha256:tampered",
    )
    with pytest.raises(StateGroupSyncError, match="snapshot_checksum_invalid"):
        service.apply_delta(base, tampered_delta, supported_schema_capabilities=("runtime_state.v1",))
