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
