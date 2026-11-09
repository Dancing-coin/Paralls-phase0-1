from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from types import MappingProxyType

from app.gameplay.modifier_runtime import ModifierDefinitionRegistry, ModifierStateProjector, ModifierTemplate, _digest
from app.gameplay.models import GameplayEvent


ACTOR = "actor:modifier"


def test_modifier_digest_preserves_nested_decimal_representation() -> None:
    value = MappingProxyType({
        "sequence": [Decimal("1.0"), Decimal("1.00")],
        "nested": MappingProxyType({"value": Decimal("123.4500"), "negative_zero": Decimal("-0.00")}),
    })
    canonical = b'{"nested":{"negative_zero":"-0.00","value":"123.4500"},"sequence":["1.0","1.00"]}'
    assert _digest(value) == sha256(canonical).hexdigest()
    assert _digest({"value": Decimal("1.0")}) != _digest({"value": Decimal("1.00")})


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
