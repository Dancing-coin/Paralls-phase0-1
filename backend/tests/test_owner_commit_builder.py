from app.gameplay.owner_runtime_base import OwnerCommitBuilder


def test_owner_commit_builder_preserves_caller_commit_semantics():
    events = [{
        "event_id": "evt:cmd:ownership",
        "event_type": "gameplay.ownership.right_granted",
        "schema_version": 1,
        "stream_id": "gameplay:ownership",
        "stream_revision": 0,
        "global_sequence": 0,
        "transaction_id": "transaction:cmd",
        "command_id": "cmd",
        "causation_id": "cause",
        "correlation_id": "corr",
        "visibility_policy": "authority_only",
        "payload": {"right_id": "right:1"},
    }]

    batch = OwnerCommitBuilder.build(
        principal_ref="owner:ownership",
        command_id="cmd",
        transaction_id="transaction:cmd",
        idempotency_key="actor:alice:grant",
        payload_digest="payload-digest",
        events=events,
        expected_stream_revisions={"gameplay:ownership": 4},
        pinned_revisions={"ownership": 4},
        result_digest="event-result-digest",
    )

    assert batch == {
        "transaction_id": "transaction:cmd",
        "command_id": "cmd",
        "expected_stream_revisions": {"gameplay:ownership": 4},
        "pinned_revisions": {"ownership": 4},
        "events": events,
        "idempotency_record": {
            "principal_ref": "owner:ownership",
            "idempotency_key": "actor:alice:grant",
            "payload_digest": "payload-digest",
        },
        "outbox_entries": [],
        "result_digest": "event-result-digest",
        "projection_refresh_hints": [],
    }


def test_owner_commit_builder_keeps_explicit_read_revisions():
    read_revisions = {"gameplay:ownership": 2, "gameplay:inventory:alice": 7}

    batch = OwnerCommitBuilder.build(
        principal_ref="owner:credential",
        command_id="cmd",
        transaction_id="tx:cmd",
        idempotency_key="credential-key",
        payload_digest="payload-digest",
        events=[{"event_id": "evt:cmd:credential:1"}],
        expected_stream_revisions={"fact:credential:1": 0},
        read_stream_revisions=read_revisions,
        pinned_revisions={"credential": 0, "ownership": 2},
        result_digest="credential-result-digest",
    )

    assert batch["read_stream_revisions"] == read_revisions
    assert batch["pinned_revisions"] == {"credential": 0, "ownership": 2}


def test_owner_commit_builder_omits_unspecified_read_revisions():
    batch = OwnerCommitBuilder.build(
        principal_ref="owner:ownership",
        command_id="cmd",
        transaction_id="tx:cmd",
        idempotency_key="key",
        payload_digest="digest",
        events=[{"event_id": "evt:cmd:ownership"}],
        expected_stream_revisions={"gameplay:ownership": 0},
        pinned_revisions={"ownership": 0},
        result_digest="result",
    )

    assert "read_stream_revisions" not in batch
