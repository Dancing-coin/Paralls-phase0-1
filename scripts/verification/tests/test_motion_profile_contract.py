"""Contract tests for body, calibration, and IK motion profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
STREET_PACKAGES = (
    "female_jk_external",
    "female_t_external",
    "female_bandage_external",
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile_path(profile_id: str) -> Path:
    kind, name = profile_id.split(":", 1)
    return ROOT / "assets" / "characters" / "profiles" / kind / f"{name}.json"


def _schema_path(kind: str) -> Path:
    return ROOT / "assets" / "validation" / "schemas" / f"{kind}-profile.v1.json"


def test_three_packages_declare_separate_body_and_shared_ik_profiles() -> None:
    manifests = [
        _read_json(ROOT / "assets" / "active" / package_id / "manifest.json")
        for package_id in STREET_PACKAGES
    ]

    assert {manifest["body_profile_id"] for manifest in manifests} == {
        "body:female_jk.default",
        "body:female_t.default",
        "body:female_bandage.default",
    }
    assert {manifest["calibration_profile_id"] for manifest in manifests} == {
        "calibration:humanoid.v1.street.default"
    }
    assert {manifest["ik_profile_id"] for manifest in manifests} == {
        "ik:humanoid.v1.default"
    }


def test_declared_profiles_validate_against_their_schemas() -> None:
    schema_kinds = ("body", "calibration", "ik")
    for kind in schema_kinds:
        schema = _read_json(_schema_path(kind))
        validator = Draft202012Validator(schema)
        profile_dir = ROOT / "assets" / "characters" / "profiles" / kind
        profiles = sorted(profile_dir.glob("*.json"))
        assert profiles, f"no {kind} profiles found"
        for profile_path in profiles:
            errors = sorted(validator.iter_errors(_read_json(profile_path)), key=str)
            assert not errors, f"{profile_path}: {errors[0].message}"


@pytest.mark.parametrize(
    ("kind", "missing_field"),
    (
        ("body", "leg_length_ratio"),
        ("calibration", "foot_contact_tolerance"),
        ("calibration", "socket_offsets"),
        ("ik", "weapon_anchor_policy"),
    ),
)
def test_profiles_reject_missing_required_fields(kind: str, missing_field: str) -> None:
    schema = _read_json(_schema_path(kind))
    profile_dir = ROOT / "assets" / "characters" / "profiles" / kind
    profile = _read_json(sorted(profile_dir.glob("*.json"))[0])
    profile.pop(missing_field)

    validator = Draft202012Validator(schema)
    assert not validator.is_valid(profile)
