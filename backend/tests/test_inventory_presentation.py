import pytest
from app.gameplay.inventory_platform_runtime import InventoryPlatformProjection
from app.gameplay.inventory_presentation import InventoryPresentationError, project_inventory_for_godot

def test_inventory_projection_is_read_only_godot_safe():
    projection = InventoryPlatformProjection()
    view = project_inventory_for_godot(projection)
    assert view["projection_kind"] == "inventory.generic.godot.v1"
    assert view["state"]["lots"] == {}

def test_inventory_projection_rejects_non_godot_consumer():
    with pytest.raises(InventoryPresentationError, match="inventory_presentation_consumer_invalid"):
        project_inventory_for_godot(InventoryPlatformProjection(), consumer="writer")
