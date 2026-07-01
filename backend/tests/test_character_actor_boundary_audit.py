from pathlib import Path


def test_character_actor_boundary_audit() -> None:
    project_root = Path(__file__).resolve().parents[2]
    scene_source = (project_root / "scenes" / "phase0" / "CharacterReplica.tscn").read_text(
        encoding="utf-8"
    )
    character_source = (project_root / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    esm_source = (project_root / "backend" / "app" / "services" / "esm_service.py").read_text(
        encoding="utf-8"
    )

    assert "GreyboxHumanoidVisual" not in scene_source
    assert "CharacterAgentRuntime" not in esm_source
    assert "output_type" not in character_source
    assert "command_type" in character_source
    assert "use_role_asset" not in character_source


def test_character_actor_runtime_models_do_not_keep_legacy_presentation_command() -> None:
    project_root = Path(__file__).resolve().parents[2]
    model_source = (project_root / "backend" / "app" / "models" / "character_agent_runtime.py").read_text(
        encoding="utf-8"
    )
    model_test_source = (project_root / "backend" / "tests" / "test_character_agent_runtime_models.py").read_text(
        encoding="utf-8"
    )

    assert "CharacterPresentationCommand" not in model_source
    assert "CharacterPresentationCommand" not in model_test_source
    assert "CharacterGoalCommand" in model_test_source
    assert "CharacterIntentFrame" in model_test_source


def test_character_replica_still_behaves_as_local_realization_host_not_semantics_owner() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert "execution_semantics" in source
    assert "selected_intent" not in source
