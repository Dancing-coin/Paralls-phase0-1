from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_agent_domain_directories_exist() -> None:
    base = ROOT / "backend" / "app" / "character_agent"

    assert (base / "__init__.py").exists()
    assert (base / "runtime").is_dir()
    assert (base / "models").is_dir()
    assert (base / "memory").is_dir()
    assert (base / "reasoning").is_dir()
    assert (base / "planning").is_dir()
    assert (base / "execution").is_dir()
    assert (base / "storage").is_dir()
    assert (base / "gateway").is_dir()
    assert (base / "models" / "private_world_snapshot.py").exists()
    assert (base / "models" / "working_memory_state.py").exists()


def test_legacy_character_agent_services_become_compatibility_shells() -> None:
    runtime_source = (ROOT / "backend" / "app" / "services" / "character_agent_runtime.py").read_text(
        encoding="utf-8"
    )
    l1_source = (ROOT / "backend" / "app" / "services" / "character_agent_l1.py").read_text(
        encoding="utf-8"
    )
    l2_source = (ROOT / "backend" / "app" / "services" / "character_agent_l2.py").read_text(
        encoding="utf-8"
    )
    l3_source = (ROOT / "backend" / "app" / "services" / "character_agent_l3.py").read_text(
        encoding="utf-8"
    )
    l4_source = (ROOT / "backend" / "app" / "services" / "character_agent_l4_adapter.py").read_text(
        encoding="utf-8"
    )

    assert "backend.app.character_agent" or "app.character_agent"
    assert "app.character_agent" in runtime_source
    assert "app.character_agent" in l1_source
    assert "app.character_agent" in l2_source
    assert "app.character_agent" in l3_source
    assert "app.character_agent" in l4_source


def test_character_agent_models_package_exports_stage_b_model_paths() -> None:
    models_init = (ROOT / "backend" / "app" / "character_agent" / "models" / "__init__.py").read_text(
        encoding="utf-8"
    )
    private_snapshot_source = (
        ROOT / "backend" / "app" / "character_agent" / "models" / "private_world_snapshot.py"
    ).read_text(encoding="utf-8")
    working_memory_source = (
        ROOT / "backend" / "app" / "character_agent" / "models" / "working_memory_state.py"
    ).read_text(encoding="utf-8")

    assert "CharacterPrivateWorldSnapshot" in models_init
    assert "CharacterWorkingMemoryState" in models_init
    assert "from app.models.character_agent_runtime import CharacterPrivateWorldSnapshot" in private_snapshot_source
    assert "class CharacterWorkingMemoryState" in working_memory_source


def test_character_agent_working_memory_path_is_used_by_memory_layer() -> None:
    working_memory_source = (ROOT / "backend" / "app" / "character_agent" / "memory" / "working_memory.py").read_text(
        encoding="utf-8"
    )
    memory_store_source = (ROOT / "backend" / "app" / "character_agent" / "storage" / "memory_store.py").read_text(
        encoding="utf-8"
    )

    assert "CharacterWorkingMemoryState" in working_memory_source
    assert "def build_state(" in working_memory_source
    assert "def working_memory_state(" in memory_store_source
