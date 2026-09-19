import pytest
from pydantic import ValidationError
from app.ws_protocol import RuntimeEnqueueRequest


def test_runtime_enqueue_keeps_original_command_and_requires_bounded_request_identity():
    request = RuntimeEnqueueRequest(request_id='original:1', command={'message_type':'character_actor_status','payload':{'actor_id':'char_a'}})
    assert request.command.message_type == 'character_actor_status'
    assert request.request_id == 'original:1'


@pytest.mark.parametrize('change', [
    {'request_id':''}, {'request_id':'x'*129}, {'request_id':1},
    {'command':{'message_type':'runtime_enqueue','payload':{}}},
    {'command':{'message_type':'websocket_session_bind','payload':{}}},
    {'extra':True}, {'command':{'message_type':'raw_fact_event','payload':{},'extra':True}},
])
def test_runtime_enqueue_rejects_unsupported_or_ambiguous_requests(change):
    value = dict(request_id='one',command=dict(message_type='character_actor_status',payload={'actor_id':'char_a'}))
    value.update(change)
    with pytest.raises(ValidationError): RuntimeEnqueueRequest(**value)
