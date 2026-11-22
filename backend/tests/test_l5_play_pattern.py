from dataclasses import FrozenInstanceError

import pytest
import yaml

from app.gameplay.l5_play_pattern import PlayPatternRejected, compile_play_pattern


CATALOGS = {
    "reaction_ids": {"reaction_a", "reaction_b"},
    "pipeline_ids": {"pipeline_a"},
    "workflow_ids": {"workflow_a"},
    "pack_pins": {"base@2.1", "tuning@1.0"},
}


@pytest.mark.parametrize("pin", ["base@2.1", {"pack": "base@2.1"}])
def test_pattern_compiles_yaml_to_ordered_immutable_references(pin):
    declaration = yaml.safe_load("""
play_pattern_id: example@1
reactions: [reaction_b, reaction_a]
pipelines: [pipeline_a]
workflows: [workflow_a]
""")
    declaration["content_refs"] = [pin, "tuning@1.0"]

    plan = compile_play_pattern(declaration, **CATALOGS)

    assert plan.play_pattern_id == "example@1"
    assert plan.reactions == ("reaction_b", "reaction_a")
    assert plan.pipelines == ("pipeline_a",)
    assert plan.workflows == ("workflow_a",)
    assert plan.content_refs == ("base@2.1", "tuning@1.0")
    assert not hasattr(plan, "writes")
    with pytest.raises(FrozenInstanceError):
        plan.workflows = ()


@pytest.mark.parametrize(("field", "value", "code"), [
    ("writes", [], "pattern_declares_writes"),
    ("on_activate", "owner.write", "pattern_schema_invalid"),
    ("reactions", [{"reaction_id": "reaction_a", "writes": []}], "pattern_schema_invalid"),
    ("reactions", ["missing"], "pattern_reference_unknown"),
    ("pipelines", ["reaction_a"], "pattern_reference_unknown"),
    ("workflows", ["missing"], "pattern_reference_unknown"),
    ("content_refs", [{"pack": "base@2.1", "writes": []}], "pattern_schema_invalid"),
    ("content_refs", ["base"], "pattern_schema_invalid"),
    ("content_refs", ["base@3.0"], "pattern_reference_unknown"),
    ("content_refs", ["base@2.1", {"pack": "base@2.1"}], "pattern_reference_duplicate"),
], ids=[
    "writes", "unknown-field", "inline-reaction", "unknown-reaction", "wrong-namespace",
    "unknown-workflow", "inline-pack", "unpinned-pack", "unknown-pin", "duplicate-pin",
])
def test_pattern_rejects_invalid_declarations(field, value, code):
    with pytest.raises(PlayPatternRejected) as error:
        compile_play_pattern({"play_pattern_id": "example", field: value}, **CATALOGS)

    assert (error.value.code, error.value.field) == (code, field)
