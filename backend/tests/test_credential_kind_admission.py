"""The reference chain feeds declared kinds into the real credential Owner."""
from pathlib import Path
import re
from shutil import copytree

import pytest

from app.gameplay.credential_reference_chain import load_credential_pack
from app.gameplay.credential_runtime import CredentialAuthorityService, CredentialProjector, CredentialRuntimeError
from g3_credential_fixture import PACK, command, setup_reference

KINDS = ("deed", "receipt", "certificate", "key", "contract_document")


def pack_with(tmp_path: Path, *, kinds: str, proves: str | None = None):
    directory = tmp_path / "pack"
    copytree(PACK, directory)
    path = directory / "models/credential_command.yaml"
    text = path.read_text(encoding="utf-8")
    pattern = r'(?m)^    credential_kinds: \[[^\r\n]*\]$'
    assert re.search(pattern, text)
    text = re.sub(pattern, f'    credential_kinds: {kinds}', text, count=1)
    if proves is not None:
        text = text.replace('    proves: ["evidence_only", "access_only", "evidence_and_access"]',
            f'    proves: {proves}')
    path.write_text(text, encoding="utf-8")
    return load_credential_pack(directory)


@pytest.mark.parametrize("kind", KINDS)
def test_default_owner_keeps_all_five_existing_kinds(kind):
    store, registry, _ = setup_reference()
    owner = CredentialAuthorityService(store=store, inventory_registry=registry)
    args = command("issue_credential") | {"credential_kind": kind}
    receipt = owner.issue_credential(**args)
    assert receipt.committed
    event = store.get_event(receipt.committed_event_ids[0])
    assert event.event_type == "gameplay.credential.issued"
    assert event.payload["credential_kind"] == kind
    assert CredentialProjector().rebuild(store.read_events()).links["credential:g3:1"].credential_kind == kind


def test_injected_rule_pack_kind_is_issued_and_projected(tmp_path):
    pack = pack_with(tmp_path, kinds='["deed", "receipt", "certificate", "key", "contract_document", "permit"]')
    store, _, chain = setup_reference(pack=pack)
    receipt = chain.execute("issue_credential", **(command("issue_credential") | {"credential_kind": "permit"}))
    assert receipt.committed and len(receipt.committed_event_ids) == 1
    event = store.get_event(receipt.committed_event_ids[0])
    assert event.event_type == "gameplay.credential.issued"
    assert event.stream_id == "gameplay:credentials" and event.schema_version == 1
    assert event.payload["credential_kind"] == "permit"
    assert chain._owner._projector.rebuild(store.read_events()).links["credential:g3:1"].credential_kind == "permit"


def test_kind_omitted_from_injected_pack_is_rejected_without_writes(tmp_path):
    pack = pack_with(tmp_path, kinds='["deed"]')
    store, _, chain = setup_reference(pack=pack)
    before = store.export_snapshot()
    with pytest.raises(CredentialRuntimeError, match="^credential_invalid$"):
        chain.execute("issue_credential", **(command("issue_credential") | {"credential_kind": "receipt"}))
    assert store.export_snapshot() == before


def test_empty_injected_sets_do_not_fall_back_to_defaults(tmp_path):
    pack = pack_with(tmp_path, kinds="[]", proves="[]")
    store, _, chain = setup_reference(pack=pack)
    before = store.export_snapshot()
    with pytest.raises(CredentialRuntimeError, match="^credential_invalid$"):
        chain.execute("issue_credential", **command("issue_credential"))
    assert store.export_snapshot() == before


def test_injected_proves_set_controls_owner_admission(tmp_path):
    pack = pack_with(tmp_path, kinds='["deed"]', proves='["access_only"]')
    store, _, chain = setup_reference(pack=pack)
    before = store.export_snapshot()
    with pytest.raises(CredentialRuntimeError, match="^credential_invalid$"):
        chain.execute("issue_credential", **command("issue_credential"))
    assert store.export_snapshot() == before
