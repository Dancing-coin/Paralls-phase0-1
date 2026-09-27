from pathlib import Path


def test_interaction_orchestration_verifier_isolates_default_character_agent_persistence() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "verify_interaction_orchestration_runtime_service.py"
    ).read_text(encoding="utf-8")

    assert '"PARALLS_HEAVENLY_GRAPH_PATH": ":memory:"' in source
    assert "env=verification_env" in source
