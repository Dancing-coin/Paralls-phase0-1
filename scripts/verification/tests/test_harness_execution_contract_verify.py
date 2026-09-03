from pathlib import Path


def test_harness_execution_contract_verifier_declares_expected_results() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "verify_harness_execution_contract.py"
    ).read_text(encoding="utf-8")

    assert "overall_harness_execution_contract_passed" in source
    assert '"lifecycle_transitions"' in source
    assert '"failure_policy"' in source
    assert '"terminal_guard"' in source
    assert '"trace_correlation"' in source
