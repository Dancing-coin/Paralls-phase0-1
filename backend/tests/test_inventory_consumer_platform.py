from app.gameplay.inventory_consumer_platform import admit_inventory_recipe, inventory_consumer_recipes


def test_inventory_recipes_cover_all_declared_owner_bound_edges():
    recipes = inventory_consumer_recipes()
    assert len(recipes) == 8
    assert len({recipe.recipe_ref for recipe in recipes}) == 8
    accepted = admit_inventory_recipe(recipe_ref=recipes[0].recipe_ref, source_event_type=recipes[0].source_event_type, target_event_type=recipes[0].target_event_type, privacy_scope=recipes[0].privacy_scope, source_revision=1, target_revision=0)
    assert accepted.accepted


def test_inventory_recipe_mismatch_is_zero_write():
    recipe = inventory_consumer_recipes()[0]
    rejected = admit_inventory_recipe(recipe_ref=recipe.recipe_ref, source_event_type="gameplay.inventory.fake@1", target_event_type=recipe.target_event_type, privacy_scope=recipe.privacy_scope, source_revision=1, target_revision=0)
    assert not rejected.accepted
    assert rejected.error_code == "inventory_recipe_binding_mismatch"
