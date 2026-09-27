from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_embodied_bridge_attestation_uses_an_isolated_graph_for_its_pytest_child() -> None:
    source = (ROOT / "verify_embodied_bridge_attestation.py").read_text(encoding="utf-8")

    assert 'verification_env = {"PARALLS_HEAVENLY_GRAPH_PATH": ":memory:"}' in source
    assert "env=verification_env" in source
