from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_mid_term_controller_port_is_documented_but_not_implemented_in_near_term_cleanup() -> None:
    control_doc = (ROOT / "docs" / "character" / "character-control-chain.md").read_text(
        encoding="utf-8"
    )
    migration_doc = (ROOT / "docs" / "character" / "character-actor-migration-status.md").read_text(
        encoding="utf-8"
    )

    assert "ControllerPort" in control_doc
    assert "mid-term" in control_doc.lower()
    assert "not implemented in the near-term cleanup" in migration_doc
    assert (ROOT / "scripts" / "character" / "CharacterControllerPort.gd").exists()
    assert "Actor Stage 2 first-batch items now landed in code:" in migration_doc
    assert "`CharacterControllerPort` and adapter family" in migration_doc
