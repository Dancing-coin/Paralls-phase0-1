import json
from threading import Event

import app.services.dialogue_continuation as continuation
from test_dialogue_completion_lifecycle import begin, complete, coordinator, response_count


def _speech_stage():
    owner = coordinator()
    advance = begin(owner)
    while advance.job.stage == "cognition":
        advance, _ = complete(owner, advance)
    return owner, advance


def test_dialogue_speech_job_freezes_actor_target_and_existing_deadline():
    owner, advance = _speech_stage()
    lease = advance.job.speech_lease
    assert lease.actor_id == advance.job.actor_id
    assert lease.target_actor_id == "char_c"
    assert lease.request_id == "turn-1"
    assert lease.expires_at_monotonic > continuation.monotonic()
    owner.cancel(advance.job.ticket_id, reason="test_complete")


def test_expired_queued_speech_does_not_invoke_provider_or_write_response(monkeypatch):
    owner, advance = _speech_stage()
    clock = continuation.monotonic() + 100
    monkeypatch.setattr(continuation, "monotonic", lambda: clock)
    emitted = []
    completion = continuation.run_dialogue_provider(advance.job, object(), Event(), emitted.append)
    assert json.loads(completion)["cancelled"] is True
    assert emitted == []
    result = owner.advance(advance.job, completion)
    assert result.reason == "speech_lease_expired"
    assert response_count() == 0
    assert not owner.runtime.pending_actor_activations()


def test_expired_stream_discards_late_chunks_and_final_text(monkeypatch):
    owner, advance = _speech_stage()
    clock = [continuation.monotonic()]
    monkeypatch.setattr(continuation, "monotonic", lambda: clock[0])

    class LateStream:
        def stream_prepared_request(self, request, *, cancelled):
            yield {"event": "delta", "delta": "current"}
            clock[0] += 100
            yield {"event": "delta", "delta": "late"}
            yield {"event": "completed", "output": {"content": "late", "tone": "neutral"}}

    emitted = []
    completion = continuation.run_dialogue_provider(advance.job, LateStream(), Event(), emitted.append)
    assert json.loads(completion)["cancelled"] is True
    assert emitted == ["current"]
    owner.advance(advance.job, completion)
    assert response_count() == 0
