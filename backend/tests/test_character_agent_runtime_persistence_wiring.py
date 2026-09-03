from pathlib import Path


def test_main_runtime_wires_character_storage_next_to_durable_graph() -> None:
    source = Path("backend/app/main.py").read_text(encoding="utf-8")

    assert "character_agent_storage_root" in source
    assert "CharacterAgentRuntime(" in source
    assert "storage_root=character_agent_storage_root" in source
