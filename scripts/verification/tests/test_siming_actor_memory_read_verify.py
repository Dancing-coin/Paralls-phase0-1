from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_actor_memory_read_verifier_isolates_graph_path_before_importing_backend() -> None:
    source = (ROOT / "scripts" / "verification" / "verify_siming_actor_memory_read.py").read_text(encoding="utf-8")

    assert "import app.main as app_main" not in source.split("def main()", 1)[0]
    assert 'os.environ["PARALLS_HEAVENLY_GRAPH_PATH"]' in source
