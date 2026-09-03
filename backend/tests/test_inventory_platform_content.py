from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.inventory_platform_content import InventoryPackageContent


def test_inventory_package_content_requires_versioned_refs_canonical_arrays_and_plain_data() -> None:
    content = InventoryPackageContent.model_validate(
        {
            "package_ref": "package:inventory:baseline@1",
            "package_revision_ref": "package:inventory:baseline@1",
            "item_definitions": [
                {
                    "item_definition_ref": "item:inventory:apple@1",
                    "item_namespace_ref": "namespace:inventory:food@1",
                    "stack_policy_ref": "policy:inventory:stacking@1",
                    "quality_policy_ref": "policy:inventory:quality@1",
                }
            ],
            "lot_policies": [
                {
                    "lot_policy_ref": "policy:inventory:lot@1",
                    "lot_namespace_ref": "namespace:inventory:lot@1",
                    "owner_family_ref": "owner-family:inventory@1",
                }
            ],
            "container_definitions": [
                {
                    "container_definition_ref": "container:inventory:bag@1",
                    "container_namespace_ref": "namespace:inventory:container@1",
                    "capacity_policy_ref": "policy:inventory:capacity@1",
                    "custody_policy_ref": "policy:inventory:custody@1",
                    "reservation_policy_ref": "policy:inventory:reservation@1",
                    "transport_policy_ref": "policy:inventory:transport@1",
                    "quality_policy_ref": "policy:inventory:quality@1",
                }
            ],
            "custody_policies": [
                {
                    "custody_policy_ref": "policy:inventory:custody@1",
                    "custody_namespace_ref": "namespace:inventory:custody@1",
                    "owner_family_ref": "owner-family:inventory@1",
                    "stream_ref": "stream:inventory:custody@1",
                }
            ],
            "reservation_policies": [
                {
                    "reservation_policy_ref": "policy:inventory:reservation@1",
                    "reservation_namespace_ref": "namespace:inventory:reservation@1",
                    "stream_ref": "stream:inventory:reservation@1",
                }
            ],
            "transport_policies": [
                {
                    "transport_policy_ref": "policy:inventory:transport@1",
                    "transport_namespace_ref": "namespace:inventory:transport@1",
                    "stream_ref": "stream:inventory:transport@1",
                }
            ],
            "quality_policies": [
                {
                    "quality_policy_ref": "policy:inventory:quality@1",
                    "quality_namespace_ref": "namespace:inventory:quality@1",
                    "stream_ref": "stream:inventory:quality@1",
                }
            ],
            "consumer_edges": [
                {
                    "consumer_edge_ref": "edge:inventory:buyer@1",
                    "consumer_namespace_ref": "namespace:inventory:consumer@1",
                    "source_item_definition_ref": "item:inventory:apple@1",
                    "target_container_definition_ref": "container:inventory:bag@1",
                    "policy_ref": "policy:inventory:consumer@1",
                }
            ],
        }
    )

    assert content.package_ref == "package:inventory:baseline@1"
    assert content.item_definitions[0].item_definition_ref == "item:inventory:apple@1"


def test_inventory_package_content_rejects_noncanonical_arrays_and_authority_shaped_payload() -> None:
    with pytest.raises(ValidationError, match="platform_array_not_canonical"):
        InventoryPackageContent.model_validate(
            {
                "package_ref": "package:inventory:baseline@1",
                "package_revision_ref": "package:inventory:baseline@1",
                "item_definitions": [
                    {
                        "item_definition_ref": "item:inventory:zeta@1",
                        "item_namespace_ref": "namespace:inventory:food@1",
                        "stack_policy_ref": "policy:inventory:stacking@1",
                        "quality_policy_ref": "policy:inventory:quality@1",
                    },
                    {
                        "item_definition_ref": "item:inventory:alpha@1",
                        "item_namespace_ref": "namespace:inventory:food@1",
                        "stack_policy_ref": "policy:inventory:stacking@1",
                        "quality_policy_ref": "policy:inventory:quality@1",
                    },
                ],
                "lot_policies": [],
                "container_definitions": [],
                "custody_policies": [],
                "reservation_policies": [],
                "transport_policies": [],
                "quality_policies": [],
                "consumer_edges": [],
            }
        )


def test_inventory_package_content_rejects_container_parent_cycle():
    with pytest.raises(ValidationError, match="inventory_container_definition_cycle"):
        InventoryPackageContent.model_validate({
            "package_ref": "package:inventory:cycle@1",
            "package_revision_ref": "package:inventory:cycle@1",
            "container_definitions": [
                {"container_definition_ref": "container:a@1", "container_namespace_ref": "namespace:container@1", "capacity_policy_ref": "policy:capacity@1", "custody_policy_ref": "policy:custody@1", "reservation_policy_ref": "policy:reservation@1", "transport_policy_ref": "policy:transport@1", "quality_policy_ref": "policy:quality@1", "parent_container_definition_ref": "container:b@1"},
                {"container_definition_ref": "container:b@1", "container_namespace_ref": "namespace:container@1", "capacity_policy_ref": "policy:capacity@1", "custody_policy_ref": "policy:custody@1", "reservation_policy_ref": "policy:reservation@1", "transport_policy_ref": "policy:transport@1", "quality_policy_ref": "policy:quality@1", "parent_container_definition_ref": "container:a@1"},
            ],
        })

    with pytest.raises(ValidationError, match="platform_authority_shaped_payload"):
        InventoryPackageContent.model_validate(
            {
                "package_ref": "package:inventory:baseline@1",
                "package_revision_ref": "package:inventory:baseline@1",
                "item_definitions": [],
                "lot_policies": [],
                "container_definitions": [],
                "custody_policies": [],
                "reservation_policies": [],
                "transport_policies": [],
                "quality_policies": [],
                "consumer_edges": [],
                "owner_ref": "caller:owner",
            }
        )
