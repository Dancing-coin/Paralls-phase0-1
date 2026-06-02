from fastapi.testclient import TestClient

from app.main import app


def test_health_exposes_current_backend_identity() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["build"] == "paralls-phase0-backend-worktree-2026-06-02"
    assert payload["worktree_root"].endswith("paralls-phase-0-demo")
