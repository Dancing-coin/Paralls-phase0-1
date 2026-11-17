import pytest
from app.gameplay.credential_runtime import CredentialRuntimeError
from g3_credential_fixture import command, setup_reference


def test_v2_reference_replays_declared_kind_and_revokes():
    store, _, chain = setup_reference()
    chain._owner.activate_v2_authority()
    args = command('issue_credential') | {'credential_kind': 'permit'}
    issued = chain.execute('issue_credential', **args)
    replay = chain.execute('issue_credential', **args)
    assert replay.committed_event_ids == issued.committed_event_ids
    assert replay.idempotency_status == 'duplicate_replayed'
    revoked = chain.execute('revoke_credential', **(command('revoke_credential') | {'credential_id': args['credential_id']}))
    assert revoked.committed
    before = store.read_events()
    with pytest.raises(CredentialRuntimeError, match='^credential_invalid$'):
        chain.execute('issue_credential', **(args | {'command_id': 'cmd:unknown', 'idempotency_key': 'key:unknown', 'credential_id': 'credential:unknown', 'credential_kind': 'unknown'}))
    assert store.read_events() == before
