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
