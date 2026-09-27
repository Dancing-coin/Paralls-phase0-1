from pathlib import Path


def test_harness_embodied_task_verifier_declares_real_chain_results() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "verify_harness_embodied_task.py"
    ).read_text(encoding="utf-8")
    assert "overall_harness_embodied_task_passed" in source
    assert '"real_session_authority"' in source
    assert '"failure_and_recovery"' in source
    assert '"capability_and_redaction"' in source
    assert '"godot_projection_evidence"' in source


def test_harness_embodied_task_verifier_isolates_persistent_character_agent_state() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "verify_harness_embodied_task.py"
    ).read_text(encoding="utf-8")
    assert "verification_env" in source
    assert '"PARALLS_HEAVENLY_GRAPH_PATH": ":memory:"' in source
    assert "env=verification_env" in source
