from copy import deepcopy

import pytest

from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from test_character_graph_memory_store import _scope
from test_character_memory_correction import make_runtime, perceived_claim, request_for


@pytest.mark.parametrize("heavy", [False, True])
def test_debug_settlement_preserves_full_snapshot_without_loading_working_memory(tmp_path, monkeypatch, heavy):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "graph.sqlite3")
    store = CharacterGraphMemoryStore(graph, scope_resolver=_scope) if heavy else CharacterAgentMemoryStore()
    runtime = make_runtime(tmp_path / "session", memory_store=store)
    try:
        runtime.record_character_perceived_event_without_cognition(perceived_claim())
        assert runtime.apply_memory_correction(request_for(runtime), principal_ref="siming").status == "applied"
        runtime.drain_observatory_messages("char_a")
        captured = []
        project = runtime._observatory_projection.project_snapshot

        def capture(**kwargs):
            captured.append(deepcopy(kwargs))
            return project(**kwargs)

        with monkeypatch.context() as guard:
            guard.setattr(runtime._observatory_projection, "project_snapshot", capture)
            guard.setattr(store, "retrieval_bundle", lambda *_: pytest.fail("debug loaded compatibility working memory"))
            if heavy:
                guard.setattr(store._normalizer, "_history_projection", lambda *_: pytest.fail("debug folded heavy history"))
            else:
                guard.setattr(store, "_history_projection", lambda *a, **k: pytest.fail("debug folded light history"))
            runtime.record_settlement_result(actor_id="char_a", producer_ts=12, payload={
                "result_type": "constraint_state_result", "actor_id": "char_a",
                "constraint_summary": "too far from obj_letter",
            })

        messages = runtime.drain_observatory_messages("char_a")
        snapshots = [item["payload"] for item in messages if item["message_type"] == "character_agent_debug_snapshot"]
        assert len(snapshots) == len(captured) == 1
        full_bundle = runtime.get_memory_bundle("char_a")
        captured[0]["memory_bundle"] = full_bundle
        captured[0].pop("memory_summary", None)
        assert snapshots[0] == project(**captured[0]).model_dump(exclude_none=True)
        assert snapshots[0]["latest_outcome_summary"] == "too far from obj_letter"
        assert "letter destroyed" in snapshots[0]["memory_summary"]
        # 显式历史读取保留完整会话与修正后的记忆语义。
        timeline = runtime.get_session_timeline("char_a")
        oracle = CharacterAgentMemoryStore()
        for event in timeline:
            oracle.write_event(event)
        assert full_bundle["working_memory"] == oracle.retrieval_bundle("char_a")["working_memory"]
        assert runtime.get_working_memory_state_record("char_a") == oracle.working_memory_state(
            "char_a", dynamic_state=runtime.get_dynamic_state_record("char_a"),
        )
        assert any(event["event_type"] == "character_memory_correction" for event in timeline)
    finally:
        runtime.close()
        graph.close()
