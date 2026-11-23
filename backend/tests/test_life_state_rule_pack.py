from pathlib import Path

from app.gameplay.life_state_runtime import _FACT, _MODEL, life_state_transition
from app.gameplay.rule_pack_validator import load_pack


PACK = Path(__file__).resolve().parents[2] / "packs/life_state"


def test_life_state_pack_loads_registered_owner_machine_and_transition_model():
    pack = load_pack(PACK, handlers={_MODEL: life_state_transition})

    fact = pack.registry.facts[_FACT]
    assert fact.owner_ref == "LifeState"
    assert fact.primitive == "machine"
    assert fact.visibility["class"] == "private"
    assert pack.registry.evaluate(
        _MODEL,
        {"life_state_command@1": {"from_state": "alive", "to_state": "dead"}},
    ) == "dead"
    assert pack.registry.evaluate(
        _MODEL,
        {"life_state_command@1": {"from_state": "dead", "to_state": "alive"}},
    ) == "life_state_transition_invalid"
