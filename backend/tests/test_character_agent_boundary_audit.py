from pathlib import Path


def test_character_agent_runtime_is_not_used_as_world_truth_authority() -> None:
    project_root = Path(__file__).resolve().parents[2]
    runtime_source = (project_root / "backend" / "app" / "services" / "character_agent_runtime.py").read_text(
        encoding="utf-8"
    )
    esm_source = (project_root / "backend" / "app" / "services" / "esm_service.py").read_text(
        encoding="utf-8"
    )

    assert "RawFactEvent" not in runtime_source
    assert "AuthorityEvent" not in runtime_source
    assert "CharacterAgentRuntime" not in esm_source


def test_character_agent_l1_does_not_depend_on_public_authority_objects() -> None:
    project_root = Path(__file__).resolve().parents[2]
    l1_source = (project_root / "backend" / "app" / "services" / "character_agent_l1.py").read_text(
        encoding="utf-8"
    )

    assert "RawFactEvent" not in l1_source
    assert "AuthorityEvent" not in l1_source
    assert "ESMService" not in l1_source
