from __future__ import annotations

from math import dist

from pydantic import BaseModel, ConfigDict


class DefaultScenePickupPolicy(BaseModel):
    """Backend-owned pickup binding for one reviewed default-scene object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_object_id: str
    asset_ref: str
    source_holder_ref: str
    source_position: tuple[float, float, float]
    allowed_actor_ids: tuple[str, ...]
    inventory_definition_id: str
    inventory_quantity: int = 1
    inventory_destination_by_actor_id: dict[str, str]
    room_id: str = "room_demo"
    scene_id: str = "scene_demo"
    zone_id: str = "zone_focus"
    max_interaction_distance: float = 3.0
    policy_revision: int = 1


class DefaultScenePickupResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    error_code: str = ""
    policy: DefaultScenePickupPolicy | None = None
    actor_ref: str = ""
    drop_target_ref: str = ""


class DefaultSceneRetrievePolicy(BaseModel):
    """Backend-owned retrieval binding for one reviewed scene container."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_object_id: str
    source_position: tuple[float, float, float]
    allowed_actor_ids: tuple[str, ...]
    asset_ref: str
    item_id: str
    expected_definition_id: str
    source_container_by_actor_id: dict[str, str]
    destination_receiver_by_actor_id: dict[str, str]
    room_id: str = "room_demo"
    scene_id: str = "scene_demo"
    zone_id: str = "zone_focus"
    max_interaction_distance: float = 3.0
    policy_revision: int = 1


class DefaultSceneRetrieveResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    error_code: str = ""
    policy: DefaultSceneRetrievePolicy | None = None
    actor_ref: str = ""
    source_container_id: str = ""
    destination_receiver_ref: str = ""


class DefaultScenePickupPolicyService:
    """Resolves reviewed pickup and retrieval targets without client world refs."""

    def __init__(
        self,
        policies: tuple[DefaultScenePickupPolicy, ...],
        retrieve_policies: tuple[DefaultSceneRetrievePolicy, ...] = (),
    ) -> None:
        self._policies = {policy.target_object_id: policy for policy in policies}
        self._retrieve_policies = {
            policy.target_object_id: policy for policy in retrieve_policies
        }

    @classmethod
    def demo_defaults(cls) -> DefaultScenePickupPolicyService:
        return cls(
            policies=(
                DefaultScenePickupPolicy(
                    target_object_id="obj_archive_token",
                    asset_ref="item:archive_token_01",
                    source_holder_ref="world:anchor:archive_token_pedestal_01",
                    source_position=(3.8, 0.7, -1.2),
                    allowed_actor_ids=("char_c",),
                    inventory_definition_id="archive_token",
                    inventory_destination_by_actor_id={
                        "char_c": "container:char_c:backpack",
                    },
                ),
            )
            ,
            retrieve_policies=(
                DefaultSceneRetrievePolicy(
                    target_object_id="obj_archive_storage_chest",
                    source_position=(1.2, 0.7, -1.2),
                    allowed_actor_ids=("char_c",),
                    asset_ref="item:archive_token_01",
                    item_id="item:archive_token_01",
                    expected_definition_id="archive_token",
                    source_container_by_actor_id={
                        "char_c": "container:char_c:backpack",
                    },
                    destination_receiver_by_actor_id={
                        "char_c": "character:char_c:hand",
                    },
                ),
            ),
        )

    def policies(self) -> tuple[DefaultScenePickupPolicy, ...]:
        return tuple(self._policies.values())

    def retrieve_policies(self) -> tuple[DefaultSceneRetrievePolicy, ...]:
        return tuple(self._retrieve_policies.values())

    @staticmethod
    def inventory_destination_for(
        policy: DefaultScenePickupPolicy,
        actor_id: str,
    ) -> str:
        return policy.inventory_destination_by_actor_id.get(actor_id, "")

    def resolve(
        self,
        *,
        target_object_id: str,
        interaction_type: str,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        actor_position: tuple[float, float, float] | None,
    ) -> DefaultScenePickupResolution:
        policy = self._policies.get(target_object_id)
        if policy is None:
            return DefaultScenePickupResolution(accepted=False, error_code="pickup_target_unknown")
        if interaction_type != "grab":
            return DefaultScenePickupResolution(accepted=False, error_code="pickup_interaction_unsupported")
        if (room_id, scene_id, zone_id) != (policy.room_id, policy.scene_id, policy.zone_id):
            return DefaultScenePickupResolution(accepted=False, error_code="pickup_context_mismatch")
        if actor_id not in policy.allowed_actor_ids:
            return DefaultScenePickupResolution(accepted=False, error_code="pickup_actor_not_allowed")
        if actor_position is None:
            return DefaultScenePickupResolution(accepted=False, error_code="pickup_actor_position_unknown")
        if dist(actor_position, policy.source_position) > policy.max_interaction_distance:
            return DefaultScenePickupResolution(accepted=False, error_code="pickup_out_of_range")
        return DefaultScenePickupResolution(
            accepted=True,
            policy=policy,
            actor_ref=f"character:{actor_id}",
            drop_target_ref=f"character:{actor_id}:hand",
        )

    def resolve_stow(self, *, target_object_id: str, actor_id: str, room_id: str, scene_id: str, zone_id: str) -> DefaultScenePickupResolution:
        policy = self._policies.get(target_object_id)
        if policy is None:
            return DefaultScenePickupResolution(accepted=False, error_code="pickup_target_unknown")
        if (room_id, scene_id, zone_id) != (policy.room_id, policy.scene_id, policy.zone_id):
            return DefaultScenePickupResolution(accepted=False, error_code="pickup_context_mismatch")
        if actor_id not in policy.allowed_actor_ids:
            return DefaultScenePickupResolution(accepted=False, error_code="pickup_actor_not_allowed")
        return DefaultScenePickupResolution(accepted=True, policy=policy, actor_ref=f"character:{actor_id}", drop_target_ref=f"character:{actor_id}:hand")

    def resolve_retrieve(
        self,
        *,
        target_object_id: str,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        actor_position: tuple[float, float, float] | None,
    ) -> DefaultSceneRetrieveResolution:
        policy = self._retrieve_policies.get(target_object_id)
        if policy is None:
            return DefaultSceneRetrieveResolution(
                accepted=False, error_code="retrieve_target_unknown"
            )
        if (room_id, scene_id, zone_id) != (
            policy.room_id,
            policy.scene_id,
            policy.zone_id,
        ):
            return DefaultSceneRetrieveResolution(
                accepted=False, error_code="retrieve_context_mismatch"
            )
        if actor_id not in policy.allowed_actor_ids:
            return DefaultSceneRetrieveResolution(
                accepted=False, error_code="retrieve_actor_not_allowed"
            )
        if actor_position is None:
            return DefaultSceneRetrieveResolution(
                accepted=False, error_code="retrieve_actor_position_unknown"
            )
        if dist(actor_position, policy.source_position) > policy.max_interaction_distance:
            return DefaultSceneRetrieveResolution(
                accepted=False, error_code="retrieve_out_of_range"
            )
        source_container_id = policy.source_container_by_actor_id.get(actor_id, "")
        destination_receiver_ref = policy.destination_receiver_by_actor_id.get(actor_id, "")
        if not source_container_id or not destination_receiver_ref:
            return DefaultSceneRetrieveResolution(
                accepted=False, error_code="retrieve_policy_incomplete"
            )
        return DefaultSceneRetrieveResolution(
            accepted=True,
            policy=policy,
            actor_ref=f"character:{actor_id}",
            source_container_id=source_container_id,
            destination_receiver_ref=destination_receiver_ref,
        )
