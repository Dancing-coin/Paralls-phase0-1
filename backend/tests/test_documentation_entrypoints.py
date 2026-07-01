from pathlib import Path


def test_character_index_points_to_complete_mind_core_spec() -> None:
    index_path = Path(__file__).resolve().parents[2] / "docs" / "INDEX.md"
    index_text = index_path.read_text(encoding="utf-8")

    assert "2026-06-29-complete-character-mind-core-design.md" in index_text
    assert "character-agent-runtime-architecture.md" in index_text


def test_mainline_docs_entrypoints_promote_world_character_siming_authority_tree() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_text = (repo_root / "docs" / "INDEX.md").read_text(encoding="utf-8")
    workflow_text = (repo_root / "docs" / "ai-engineering-workflow.md").read_text(
        encoding="utf-8"
    )
    runtime_text = (
        repo_root / "docs" / "character" / "character-agent-runtime-architecture.md"
    ).read_text(encoding="utf-8")
    migration_text = (
        repo_root / "docs" / "character" / "character-actor-migration-status.md"
    ).read_text(encoding="utf-8")

    assert "world-character-siming-authority-mainline/README.md" in index_text
    assert "world-character-siming-authority-mainline/README.md" in workflow_text
    assert "world-character-siming-authority-mainline-master-design.md" in runtime_text
    assert "world-character-siming-authority-mainline-master-design.md" in migration_text


def test_phase0_mission_docs_are_marked_as_compatibility_surfaces() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    phase0_text = (repo_root / "PHASE0_README.md").read_text(encoding="utf-8").lower()
    agents_text = (repo_root / "AGENTS.md").read_text(encoding="utf-8").lower()
    demo_text = (repo_root / "docs" / "demo-script.md").read_text(encoding="utf-8").lower()

    assert "historical" in phase0_text or "compatibility" in phase0_text
    assert "world-character-siming-authority-mainline" in agents_text
    assert "compatibility" in agents_text or "historical" in agents_text
    assert "compatibility" in demo_text or "historical" in demo_text
