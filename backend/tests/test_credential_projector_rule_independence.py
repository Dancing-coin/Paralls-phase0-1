from pathlib import Path
import re
from shutil import copytree

import pytest

from app.gameplay.credential_reference_chain import load_credential_pack
from app.gameplay.credential_runtime import CredentialAuthorityService, CredentialProjector, CredentialRuntimeError
from g3_credential_fixture import PACK, command, setup_reference


def _pack_with_seal(tmp_path: Path):
    directory = tmp_path / "credential-pack"
    copytree(PACK, directory)
    path = directory / "models/credential_command.yaml"
    text = path.read_text(encoding="utf-8")
    pattern = r'(?m)^    credential_kinds: \[[^\r\n]*\]$'
    match = re.search(pattern, text)
    assert match is not None
    text = re.sub(pattern, lambda found: found.group(0)[:-1] + ', "seal"]', text, count=1)
    path.write_text(text, encoding="utf-8")
    return load_credential_pack(directory)


def test_default_projector_reads_committed_pack_declared_seal(tmp_path):
    store, _, chain = setup_reference(pack=_pack_with_seal(tmp_path))
    chain._owner.activate_v2_authority()
    args = command("issue_credential") | {"credential_kind": "seal"}
    receipt = chain.execute("issue_credential", **args)
    assert receipt.committed

    projection = CredentialProjector().rebuild(store.read_events())
    assert projection.links[args["credential_id"]].credential_kind == "seal"


def test_undeclared_seal_write_is_rejected_without_snapshot_change():
    store, registry, _ = setup_reference()
    owner = CredentialAuthorityService(store=store, inventory_registry=registry)
    before = store.export_snapshot()

    with pytest.raises(CredentialRuntimeError, match="^credential_invalid$"):
        owner.issue_credential(**(command("issue_credential") | {"credential_kind": "seal"}))

    assert store.export_snapshot() == before
