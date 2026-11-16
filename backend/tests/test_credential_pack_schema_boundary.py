"""Untrusted pack metadata must fail atomically with located diagnostics."""
from hashlib import sha256
import json
from shutil import copytree

import pytest
import yaml

from app.gameplay.credential_reference_chain import load_credential_pack
from app.gameplay.fact_type_registry import RegistrationRejected
from g3_credential_fixture import PACK


@pytest.mark.parametrize("old,new", [
    ('input_schema: "credential_command_inputs@1"', 'input_schema: ["credential_command_inputs@1"]'),
    ('output_schema: "credential_evaluation@1"', 'output_schema: 7'),
    ('implementation: "code"', 'implementation: ["code"]'),
    ('implementation: "code"', 'implementation: "unknown"'),
    ('implementation: "code"', 'implementation: "data"\n  evaluator_ref: []'),
    ('implementation: "code"', 'implementation: "data"'),
])
def test_model_metadata_types_are_rejected_before_registration(tmp_path, old, new):
    directory = tmp_path / "pack"
    copytree(PACK, directory)
    path = directory / "models/credential_command.yaml"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    with pytest.raises(RegistrationRejected) as caught:
        load_credential_pack(directory)
    violations = caught.value.violations
    assert any(v.code == "pack_schema_invalid" and v.target == "credential_command@1" for v in violations)
    assert all(v.file == str(path) and v.line >= 1 and v.hint for v in violations)


def test_boolean_is_not_a_pack_schema_version(tmp_path):
    directory = tmp_path / "pack"
    copytree(PACK, directory)
    path = directory / "pack.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("schema_version: 1", "schema_version: true"), encoding="utf-8")
    with pytest.raises(RegistrationRejected, match="pack_schema_invalid"):
        load_credential_pack(directory)


def test_pack_digest_uses_portable_relative_paths():
    manifest = yaml.safe_load((PACK / "pack.yaml").read_text(encoding="utf-8"))
    portable_documents = {"pack.yaml": manifest}
    for section, names in manifest["contents"].items():
        for name in names:
            portable_name = f"{section}/{name}.yaml"
            portable_documents[portable_name] = yaml.safe_load((PACK / portable_name).read_text(encoding="utf-8"))
    expected = sha256(json.dumps(portable_documents, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert load_credential_pack(PACK).content_hash == expected
