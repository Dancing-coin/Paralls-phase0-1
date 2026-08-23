from pathlib import Path

import pytest

from app.models.harness_execution import CapabilityGrant
from app.services.harness_capability_store import HarnessCapabilityStore


def _grant() -> CapabilityGrant:
    return CapabilityGrant(
        grant_id="grant:1",
        principal_ref="principal:godot",
        task_id="task:1",
        phase="commit",
        policy_revision="policy:1",
        expires_at=100,
        nonce="nonce:1",
    )


def test_capability_grant_survives_restart_and_is_one_time(tmp_path: Path) -> None:
    path = tmp_path / "capabilities.sqlite3"
    HarnessCapabilityStore(path).issue(_grant())
    reopened = HarnessCapabilityStore(path)
    consumed = reopened.consume(
        grant_id="grant:1",
        principal_ref="principal:godot",
        task_id="task:1",
        phase="commit",
        policy_revision="policy:1",
        correlation_id="corr:1",
        now=50,
    )
    assert consumed.state == "consumed"
    with pytest.raises(ValueError, match="already_consumed"):
        reopened.consume(
            grant_id="grant:1",
            principal_ref="principal:godot",
            task_id="task:1",
            phase="commit",
            policy_revision="policy:1",
            correlation_id="corr:1",
            now=50,
        )


def test_capability_scope_revision_and_expiry_fail_closed(tmp_path: Path) -> None:
    store = HarnessCapabilityStore(tmp_path / "capabilities.sqlite3")
    store.issue(_grant())
    with pytest.raises(ValueError, match="scope_denied"):
        store.consume(grant_id="grant:1", principal_ref="principal:other", task_id="task:1", phase="commit", policy_revision="policy:1", correlation_id="corr:1", now=50)
    with pytest.raises(ValueError, match="revision_mismatch"):
        store.consume(grant_id="grant:1", principal_ref="principal:godot", task_id="task:1", phase="verify", policy_revision="policy:1", correlation_id="corr:1", now=50)
    with pytest.raises(ValueError, match="expired"):
        store.consume(grant_id="grant:1", principal_ref="principal:godot", task_id="task:1", phase="commit", policy_revision="policy:1", correlation_id="corr:1", now=100)


def test_delete_task_clears_all_grants(tmp_path: Path) -> None:
    store = HarnessCapabilityStore(tmp_path / "capabilities.sqlite3")
    store.issue(_grant())
    store.delete_task("task:1")

    with pytest.raises(ValueError, match="unknown"):
        store.read("grant:1")
