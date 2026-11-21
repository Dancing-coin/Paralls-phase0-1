from pathlib import Path
import shutil

import pytest

from app.gameplay.fact_type_registry import RegistrationRejected
from app.gameplay.rule_pack_validator import load_pack

PACK = Path(__file__).resolve().parents[2] / "packs/credential_reference"


def declared_kind_condition(inputs, params):
    return inputs["command@1"]["credential_kind"] in params["credential_kinds"]


HANDLERS = {"credential_command@1": declared_kind_condition}


def test_pack_load_is_repeatable_and_evaluates_registered_code():
    first = load_pack(PACK, handlers=HANDLERS)
    assert first.content_hash == load_pack(PACK, handlers=HANDLERS).content_hash
    assert first.registry.evaluate("credential_command@1", {"command@1": {"credential_kind": "deed"}})
    assert not first.registry.evaluate("credential_command@1", {"command@1": {"credential_kind": "unknown"}})
    assert first.legacy_rule["condition_revision"] == 1
    assert first.registry.facts["fact:credential:*:link"].resolution_order == 10


def test_credential_fact_is_owned_by_ownership_without_writing_title_facts():
    loaded = load_pack(PACK, handlers=HANDLERS)

    fact = loaded.registry.facts["fact:credential:*:link"]
    model = loaded.registry.models["credential_command@1"]

    assert fact.owner_ref == "Ownership"
    assert model.owner_ref == "Ownership"
    assert model.writes_fact_types == ("fact:credential:*:link",)


def test_pack_can_reference_another_registered_owner(tmp_path):
    destination = tmp_path / "economy-market-pack"
    shutil.copytree(PACK, destination)
    manifest_path = destination / "pack.yaml"
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest = manifest.replace('["Ownership"]', '["Economy / Market"]')
    manifest_path.write_text(manifest, encoding="utf-8")

    fact_path = destination / "fact_types/credential_link.yaml"
    fact = fact_path.read_text(encoding="utf-8")
    fact = fact.replace('"Ownership"', '"Economy / Market"')
    fact_path.write_text(fact, encoding="utf-8")

    model_path = destination / "models/credential_command.yaml"
    model = model_path.read_text(encoding="utf-8")
    model = model.replace('"Ownership"', '"Economy / Market"')
    model_path.write_text(model, encoding="utf-8")

    loaded = load_pack(destination, handlers=HANDLERS)

    assert loaded.registry.facts["fact:credential:*:link"].owner_ref == "Economy / Market"


def test_legacy_credential_owner_pack_remains_loadable(tmp_path):
    destination = tmp_path / "legacy-credential-pack"
    shutil.copytree(PACK, destination)

    for relative_path in (
        "pack.yaml",
        "fact_types/credential_link.yaml",
        "models/credential_command.yaml",
    ):
        path = destination / relative_path
        path.write_text(
            path.read_text(encoding="utf-8").replace('"Ownership"', '"Credential"'),
            encoding="utf-8",
        )

    loaded = load_pack(destination, handlers=HANDLERS)

    assert loaded.registry.facts["fact:credential:*:link"].owner_ref == "Credential"


def test_pack_cannot_register_an_unknown_owner(tmp_path):
    destination = tmp_path / "unknown-owner-pack"
    shutil.copytree(PACK, destination)
    manifest_path = destination / "pack.yaml"
    manifest = manifest_path.read_text(encoding="utf-8").replace('["Ownership"]', '["UnknownOwner"]')
    manifest_path.write_text(manifest, encoding="utf-8")

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    assert "facttype_owner_unknown" in {violation.code for violation in error.value.violations}


@pytest.mark.parametrize("suffix,code", [
    ('"bad": 0.1\n', "pack_float_forbidden"),
    ('"bad": &shared {"value": 1}\n"alias": *shared\n', "pack_yaml_feature_forbidden"),
    ('"bad": !!str "value"\n', "pack_yaml_feature_forbidden"),
    ('"script": "execute"\n', "pack_contains_logic"),
])
def test_forbidden_yaml_never_returns_a_partially_loaded_pack(tmp_path, suffix, code):
    destination = tmp_path / "pack"
    shutil.copytree(PACK, destination)
    path = destination / "models/credential_command.yaml"
    path.write_text(path.read_text() + suffix, encoding="utf-8")
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    assert code in {v.code for v in error.value.violations}
    assert all(v.target and v.file and v.line >= 1 and v.hint for v in error.value.violations)


def test_independent_errors_are_reported_together_with_locations(tmp_path):
    destination = tmp_path / "pack"
    shutil.copytree(PACK, destination)
    path = destination / "models/credential_command.yaml"
    path.write_text(path.read_text() + '"bad": 0.1\n"script": "execute"\n', encoding="utf-8")
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    codes = {v.code for v in error.value.violations}
    assert {"pack_float_forbidden", "pack_contains_logic"} <= codes


def test_undeclared_content_and_runtime_reload_are_rejected(tmp_path):
    destination = tmp_path / "pack"
    shutil.copytree(PACK, destination)
    (destination / "extra.yaml").write_text('"extra": 1\n', encoding="utf-8")
    with pytest.raises(RegistrationRejected, match="pack_content_undeclared"):
        load_pack(destination, handlers=HANDLERS)
    with pytest.raises(RegistrationRejected, match="pack_runtime_reload_forbidden"):
        load_pack(PACK, handlers=HANDLERS, running=True)
