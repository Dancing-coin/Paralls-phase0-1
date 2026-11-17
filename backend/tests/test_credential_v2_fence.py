from __future__ import annotations

import pytest

from app.gameplay.credential_runtime import CredentialAuthorityService, CredentialRuntimeError
from g3_credential_fixture import command, setup_reference


def test_v2_fence_updates_the_v1_writer_and_rejects_old_service_without_writes():
    store, registry, _ = setup_reference()
    old_service = CredentialAuthorityService(store=store, inventory_registry=registry)
    new_service = CredentialAuthorityService(store=store, inventory_registry=registry)
    before = store.read_events()

    new_service.activate_v2_authority()

    assert store.get_authority_stream("gameplay:credentials") == {
        "stream_id": "gameplay:credentials",
        "scope_ref": "scope:credential-domain",
        "epoch": 2,
        "writer_ref": "actor_gameplay.credential_domain_v2",
    }
    with pytest.raises(CredentialRuntimeError, match="^credential_authority_fence_mismatch$"):
        old_service.issue_credential(**command("issue_credential"))
    assert store.read_events() == before
