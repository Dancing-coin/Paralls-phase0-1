import pytest

from app.character_agent.storage.session_store import CharacterAgentSessionStore


def _store(tmp_path):
    store = CharacterAgentSessionStore(database_path=tmp_path / "sessions.sqlite3")
    store.initialize_recovery()
    store.initialize_cognition_admissions()
    return store


def _admit(store, key="child:1"):
    entry = {
        "child_key": key,
        "actor_id": "char_a",
        "admitted_at": 10.0,
        "source_event_id": "source:1",
        "expires_at": 100.0,
    }
    store.save_receipt("char_a", kind="cognition_admission", key=key, receipt=entry)
    store._connection.execute(
        "INSERT INTO character_session_cognition_heads(child_key,actor_id,admitted_at) VALUES (?,?,?)",
        (key, "char_a", 10.0),
    )
    store._connection.commit()


def _progress(key="child:1", revision=1, status="completed"):
    return {
        "schema_version": 1,
        "child_key": key,
        "actor_id": "char_a",
        "input_digest": "input:1",
        "revision": revision,
        "stage": "goal_proposal",
        "status": status,
        "frame": {"actor_id": "char_a", "stage": "goal_proposal"},
        "plan": None,
        "completion": {"output": {"active_goal_frame": {"primary_goal": "open"}, "evidence_refs": ["source:1"]}},
        "request_json": "{}",
        "reason": "",
        "progress_digest": "progress:1",
    }


def test_goal_acceptance_commits_event_terminal_receipt_and_progress_atomically(tmp_path):
    store = _store(tmp_path)
    try:
        _admit(store)
        result = store.commit_cognition_goal_proposal(
            actor_id="char_a", key="child:1", expected_revision=0,
            events=[{"event_type": "goal_state_event", "producer_ts": 20, "payload": {"primary_goal": "open"}}],
            before={"primary_goal": "wait"}, after={"primary_goal": "open"},
            progress=_progress(), expected_progress_revision=0,
        )
        assert result["progress"]["status"] == "completed"
        assert [row["event_type"] for row in store.list_events("char_a")] == ["goal_state_event"]
        assert store.read_receipt("char_a", kind="cognition_goal_terminal", key="child:1") == result["terminal"]
        assert store.read_cognition_progress("child:1")["status"] == "completed"
    finally:
        store.close()


def test_goal_acceptance_rolls_back_event_receipt_and_progress_together(tmp_path):
    store = _store(tmp_path)
    try:
        _admit(store)
        store._connection.execute(
            "CREATE TRIGGER reject_goal_progress BEFORE INSERT ON character_session_receipts "
            "WHEN NEW.kind='cognition_progress' BEGIN SELECT RAISE(ABORT, 'progress_failure'); END"
        )
        with pytest.raises(Exception, match="progress_failure"):
            store.commit_cognition_goal_proposal(
                actor_id="char_a", key="child:1", expected_revision=0,
                events=[{"event_type": "goal_state_event", "producer_ts": 20, "payload": {"primary_goal": "open"}}],
                before={"primary_goal": "wait"}, after={"primary_goal": "open"},
                progress=_progress(), expected_progress_revision=0,
            )
        assert store.list_events("char_a") == []
        assert store.read_receipt("char_a", kind="cognition_goal_terminal", key="child:1") is None
        assert store.read_cognition_progress("child:1") is None
    finally:
        store.close()


def test_goal_acceptance_exact_retry_returns_original_terminal_receipt(tmp_path):
    store = _store(tmp_path)
    try:
        _admit(store)
        kwargs = dict(
            actor_id="char_a", key="child:1", expected_revision=0,
            events=[{"event_type": "goal_state_event", "producer_ts": 20, "payload": {"primary_goal": "open"}}],
            before={"primary_goal": "wait"}, after={"primary_goal": "open"},
            progress=_progress(), expected_progress_revision=0,
        )
        first = store.commit_cognition_goal_proposal(**kwargs)
        changes = store._connection.total_changes
        second = store.commit_cognition_goal_proposal(**kwargs)
        assert second == first
        assert store._connection.total_changes == changes
    finally:
        store.close()


@pytest.mark.parametrize("status", ["stale", "cancelled", "failed"])
def test_rejected_goal_proposal_terminal_is_durable_without_goal_event(tmp_path, status):
    store = _store(tmp_path)
    try:
        _admit(store)
        result = store.commit_cognition_goal_proposal(
            actor_id="char_a", key="child:1", expected_revision=0,
            events=[], before={}, after={},
            progress=_progress(status=status), expected_progress_revision=0,
        )
        assert result["terminal"]["outcome"] == status
        assert store.list_events("char_a") == []
        assert store.read_cognition_progress("child:1")["status"] == status
        assert store.list_cognition_admissions(limit=1) == ()
    finally:
        store.close()


def test_rejected_goal_proposal_cannot_smuggle_goal_event(tmp_path):
    store = _store(tmp_path)
    try:
        _admit(store)
        with pytest.raises(ValueError, match="cognition_goal_terminal_events_invalid"):
            store.commit_cognition_goal_proposal(
                actor_id="char_a", key="child:1", expected_revision=0,
                events=[{"event_type": "goal_state_event", "producer_ts": 20, "payload": {"primary_goal": "open"}}],
                before={}, after={},
                progress=_progress(status="stale"), expected_progress_revision=0,
            )
        assert store.list_events("char_a") == []
        assert store.read_receipt("char_a", kind="cognition_goal_terminal", key="child:1") is None
    finally:
        store.close()


def test_goal_acceptance_rejects_non_goal_events_and_bool_revisions(tmp_path):
    store = _store(tmp_path)
    try:
        _admit(store)
        with pytest.raises(ValueError, match="cognition_goal_event_invalid"):
            store.commit_cognition_goal_proposal(
                actor_id="char_a", key="child:1", expected_revision=0,
                events=[{"event_type": "action_intent", "producer_ts": 20, "payload": {}}],
                before={}, after={}, progress=_progress(), expected_progress_revision=0,
            )
        with pytest.raises(ValueError, match="cognition_stage_invalid"):
            store.commit_cognition_goal_proposal(
                actor_id="char_a", key="child:1", expected_revision=True,
                events=[], before={}, after={}, progress=_progress(status="stale"), expected_progress_revision=0,
            )
    finally:
        store.close()


def test_goal_acceptance_changed_retry_is_rejected_without_writes(tmp_path):
    store = _store(tmp_path)
    try:
        _admit(store)
        kwargs = dict(
            actor_id="char_a", key="child:1", expected_revision=0,
            events=[{"event_type": "goal_state_event", "producer_ts": 20, "payload": {"primary_goal": "open"}}],
            before={"primary_goal": "wait"}, after={"primary_goal": "open"},
            progress=_progress(), expected_progress_revision=0,
        )
        store.commit_cognition_goal_proposal(**kwargs)
        changes = store._connection.total_changes
        kwargs["after"] = {"primary_goal": "different"}
        with pytest.raises(ValueError, match="cognition_goal_terminal_conflict"):
            store.commit_cognition_goal_proposal(**kwargs)
        assert store._connection.total_changes == changes
    finally:
        store.close()


def test_goal_acceptance_retry_rejects_corrupt_stage_receipt(tmp_path):
    store = _store(tmp_path)
    try:
        _admit(store)
        kwargs = dict(
            actor_id="char_a", key="child:1", expected_revision=0,
            events=[{"event_type": "goal_state_event", "producer_ts": 20, "payload": {"primary_goal": "open"}}],
            before={"primary_goal": "wait"}, after={"primary_goal": "open"},
            progress=_progress(), expected_progress_revision=0,
        )
        store.commit_cognition_goal_proposal(**kwargs)
        store._connection.execute(
            "UPDATE character_session_receipts SET receipt_json='{}' WHERE actor_id='char_a' AND kind='cognition_stage' AND receipt_key='child:1'"
        )
        with pytest.raises(ValueError, match="cognition_stage_projection_proof_invalid"):
            store.commit_cognition_goal_proposal(**kwargs)
    finally:
        store.close()


def test_goal_acceptance_survives_sqlite_reopen_and_recovers_goal_state(tmp_path):
    store = _store(tmp_path)
    _admit(store)
    result = store.commit_cognition_goal_proposal(
        actor_id="char_a", key="child:1", expected_revision=0,
        events=[{"event_type": "goal_state_event", "producer_ts": 20, "payload": {"primary_goal": "open"}}],
        before={"primary_goal": "wait"}, after={"primary_goal": "open"},
        progress=_progress(), expected_progress_revision=0,
    )
    store.close()
    reopened = _store(tmp_path)
    try:
        assert reopened.read_receipt("char_a", kind="cognition_goal_terminal", key="child:1") == result["terminal"]
        assert reopened.read_cognition_progress("child:1")["status"] == "completed"
        recovered = reopened.read_runtime_state("char_a")
        assert recovered["goal_history"][-1]["primary_goal"] == "open"
        assert reopened.read_current_cognition_stage("char_a")["plan"]["key"] == "child:1"
        assert [row["event_type"] for row in reopened.list_events("char_a")] == ["goal_state_event"]
    finally:
        reopened.close()


@pytest.mark.parametrize("bad_revision", [False, -1, 0.0])
def test_goal_acceptance_rejects_non_strict_progress_revisions(tmp_path, bad_revision):
    store = _store(tmp_path)
    try:
        _admit(store)
        with pytest.raises(ValueError, match="cognition_goal_terminal_progress_invalid"):
            store.commit_cognition_goal_proposal(
                actor_id="char_a", key="child:1", expected_revision=0,
                events=[], before={}, after={}, progress=_progress(status="stale"),
                expected_progress_revision=bad_revision,
            )
        assert store.list_events("char_a") == []
        assert store.read_cognition_progress("child:1") is None
    finally:
        store.close()


def test_goal_acceptance_requires_durable_session():
    store = CharacterAgentSessionStore()
    try:
        with pytest.raises(ValueError, match="cognition_stage_requires_durable_session"):
            store.commit_cognition_goal_proposal(
                actor_id="char_a", key="child:1", expected_revision=0,
                events=[], before={}, after={}, progress=_progress(status="stale"), expected_progress_revision=0,
            )
    finally:
        store.close()
