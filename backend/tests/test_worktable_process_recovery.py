"""Durable worktable recovery; supplied choices do not assess model quality."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_character_object_execution import vertical
from test_character_worktable_vertical import selected_contract


def test_worktable_cycle_reopens_original_receipts_and_repairs_finish_outcome(tmp_path, monkeypatch):
    with vertical(tmp_path, target="obj_worktable", intent="use_object", action="action:use") as (
        execution, runtime, owner, source, world, sessions, clock, _
    ):
        use = selected_contract(runtime, owner, sessions, "use_object", 1)
        execution.offer(use)
        use_receipt = execution.execute(use)[3]
        finish = selected_contract(runtime, owner, sessions, "finish_use", 2)
        execution.offer(finish)

        def unavailable(**kwargs):
            raise OSError("finish outcome unavailable")

        monkeypatch.setattr(runtime, "record_settlement_result", unavailable)
        with pytest.raises(OSError, match="finish outcome unavailable"):
            execution.execute(finish)
        assert owner.interaction_state_for(room_id="r", scene_id="s", zone_id="z",
                                          target_object_id="obj_worktable") == "ready"
        assert world.get_last_global_sequence() == 3
        finish_transaction = world.read_stream(owner._object_stream(
            ("r", "s", "z", "obj_worktable")))[-1].transaction_id
        outcomes_before = [e["payload"]["settlement_id"] for e in runtime.get_session_timeline("char_a")
                           if e["event_type"] == "character_agent_settlement_result"]

    # The child has no controller binding, pose source, dispatch epoch or live
    # snapshots. It may repair outcomes only from the original durable receipts.
    program = '''
import json, sys
from pathlib import Path
from app.character_agent.execution.object_execution import CharacterObjectExecution
from app.character_agent.models.character_execution import CharacterExecutionContract
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.gameplay.event_store import DurableGameplayEventStore
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.esm_service import ESMService
data = json.load(sys.stdin)
root = Path(data["root"])
world = DurableGameplayEventStore(root / "world.sqlite3")
sessions = CharacterAgentSessionStore(database_path=root / "sessions.sqlite3")
runtime = CharacterAgentRuntime(session_store=sessions)
try:
    owner = ESMService(store=world)
    execution = CharacterObjectExecution(runtime=runtime, owner=owner, source=None, scopes=[])
    contracts = [CharacterExecutionContract.model_validate(c) for c in data["contracts"]]
    receipts = [execution.execute(c)[3].transaction_id for c in contracts]
    repaired_count = sessions.event_count("char_a")
    assert [execution.execute(c)[3].transaction_id for c in contracts] == receipts
    assert sessions.event_count("char_a") == repaired_count
    changed = contracts[1].model_copy(update={"causation_id": "changed-cause"})
    try:
        execution.execute(changed)
    except ValueError:
        pass
    else:
        raise AssertionError("changed contract accepted")
    assert sessions.event_count("char_a") == repaired_count
    outcomes = [e["payload"]["settlement_id"] for e in runtime.get_session_timeline("char_a")
                if e["event_type"] == "character_agent_settlement_result"]
    print(json.dumps({"receipts": receipts, "outcomes": outcomes,
        "session_count": repaired_count, "world_sequence": world.get_last_global_sequence(),
        "state": owner.interaction_state_for(room_id="r", scene_id="s", zone_id="z",
                                            target_object_id="obj_worktable")}))
finally:
    runtime.close()
    world.close()
'''
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    child = subprocess.run([sys.executable, "-c", program], input=json.dumps({
        "root": str(tmp_path), "contracts": [c.model_dump(mode="json") for c in (use, finish)]}),
        text=True, capture_output=True, env=environment, timeout=30)
    assert child.returncode == 0, child.stderr
    result = json.loads(child.stdout)
    expected = [use_receipt.transaction_id, finish_transaction]
    assert result["receipts"] == expected
    assert result["outcomes"] == expected
    assert set(outcomes_before).issubset(result["outcomes"])
    assert len(result["outcomes"]) == len(set(result["outcomes"])) == 2
    assert result["world_sequence"] == 3
    assert result["state"] == "ready"
