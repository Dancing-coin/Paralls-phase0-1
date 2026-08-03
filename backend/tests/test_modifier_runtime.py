from __future__ import annotations

from decimal import Decimal

from app.gameplay.modifier_runtime import ModifierDefinitionRegistry, ModifierStateProjector, ModifierTemplate
from app.gameplay.models import GameplayEvent


ACTOR = "actor:modifier"


def _event(event_id: str, event_type: str, sequence: int, payload: dict[str, object]) -> GameplayEvent:
    return GameplayEvent(
        event_id=event_id,
        event_type=event_type,
        schema_version=1,
        stream_id=f"gameplay:modifiers:{ACTOR}",
        stream_revision=sequence,
        global_sequence=sequence,
        transaction_id=f"tx:{sequence}",
        command_id=f"cmd:{sequence}",
        causation_id="cause",
        correlation_id="corr",
        visibility_policy="authority_only",
        payload={"actor_ref": ACTOR, **payload},
    )


def test_modifier_source_replay_deactivates_only_the_matching_instance() -> None:
    registry = ModifierDefinitionRegistry()
    registry.register_template(
        ModifierTemplate("template:power", "combat.power", "additive", Decimal("2"), "power")
    )
    events = [
        _event("evt:one", "gameplay.modifier.source_activated", 1, {"modifier_instance_id": "modifier:one", "template_id": "template:power", "source_ref": "activation:one"}),
        _event("evt:two", "gameplay.modifier.source_activated", 2, {"modifier_instance_id": "modifier:two", "template_id": "template:power", "source_ref": "activation:two"}),
        _event("evt:three", "gameplay.modifier.source_deactivated", 3, {"modifier_instance_id": "modifier:one"}),
    ]

    projection = ModifierStateProjector(registry).rebuild(ACTOR, events)

    assert projection.instances["modifier:one"].status == "inactive"
    assert set(projection.active_modifiers) == {"modifier:two"}
    assert projection.active_modifiers["modifier:two"].source_ref == "activation:two"
