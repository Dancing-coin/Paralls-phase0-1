from pathlib import Path

from app.gameplay.rule_pack_validator import load_pack


PACK = Path(__file__).resolve().parents[2] / "packs" / "reference_data"


def test_reference_data_pack_registers_dataset_lifecycle_candidate() -> None:
    loaded = load_pack(PACK, handlers={})

    fact = loaded.registry.facts["fact:information:*:dataset_status"]
    assert fact.owner_ref == "Information"
    assert fact.primitive == "machine"
    assert fact.state_set_ref == "machine_def/dataset_status@1"
    assert fact.resolution_order == 10
