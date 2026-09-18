from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProfileRegistry:
    profiles: dict[str, dict[str, object]]
    profile_order: list[str]
    suites: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleRegistry:
    rules: dict[str, dict[str, object]]


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"Duplicate manifest key: {key}")
        payload[key] = value
    return payload


def _read_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"{path} uses unsupported schema_version {schema_version!r}; "
            f"expected {SUPPORTED_SCHEMA_VERSION}"
        )
    return payload


def load_profile_registry(project_root: Path) -> ProfileRegistry:
    project_root = project_root.resolve()
    profile_dir = project_root / ".harness" / "profiles"
    profiles: dict[str, dict[str, object]] = {}
    for path in sorted(profile_dir.glob("*.json")):
        payload = _read_manifest(path)
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{path} must declare a non-empty profile name")
        if name in profiles:
            raise ValueError(f"Duplicate profile name {name!r} in {path}")
        script = payload.get("script")
        if not isinstance(script, str) or not script.strip():
            raise ValueError(f"{path} must declare a non-empty script path")
        script_path = (project_root / script).resolve()
        if Path(script).is_absolute() or not script_path.is_relative_to(project_root) or not script_path.is_file():
            raise ValueError(f"{path} script must be an existing file within the project: {script!r}")
        if "timeout_seconds" in payload:
            timeout = payload["timeout_seconds"]
            if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
                raise ValueError(f"{path} timeout_seconds must be a finite positive number")
        profiles[name] = payload
    profile_order = [
        str(profile["name"])
        for profile in sorted(profiles.values(), key=lambda payload: int(payload.get("order", 0)))
        if bool(profile.get("include_in_profile_order", True))
    ]
    suites: dict[str, list[str]] = {}
    suites_path = project_root / ".harness" / "suites.json"
    if suites_path.exists():
        payload = _read_manifest(suites_path)
        if set(payload) != {"schema_version", "suites"} or not isinstance(payload["suites"], dict):
            raise ValueError(f"{suites_path} must declare only schema_version and a suites object")
        for name, members in payload["suites"].items():
            if not name.strip() or not isinstance(members, list) or not members:
                raise ValueError(f"{suites_path} suite {name!r} must contain a non-empty profile list")
            if any(not isinstance(member, str) or member not in profiles for member in members):
                raise ValueError(f"{suites_path} suite {name!r} references an unknown profile")
            suites[name] = list(dict.fromkeys(members))
    return ProfileRegistry(profiles=profiles, profile_order=profile_order, suites=suites)


def select_profiles(
    registry: ProfileRegistry, *, profile: str | None = None, suite: str | None = None
) -> list[str]:
    if profile is not None and suite is not None:
        raise ValueError("profile and suite are mutually exclusive")
    if suite is not None:
        if suite not in registry.suites:
            raise ValueError(f"Unknown suite: {suite!r}")
        members = registry.suites[suite]
        if not isinstance(members, list) or not members or any(not isinstance(name, str) or name not in registry.profiles for name in members):
            raise ValueError(f"Suite {suite!r} must reference existing profiles")
        return list(dict.fromkeys(members))
    if profile is None:
        profile = "boundaries"
    if profile == "all":
        return [name for name in registry.profile_order if registry.profiles[name].get("include_in_all", True)]
    if profile not in registry.profiles:
        raise ValueError(f"Unknown profile: {profile!r}")
    return [profile]


def load_rule_registry(project_root: Path) -> RuleRegistry:
    rule_dir = project_root / ".harness" / "rules"
    rules: dict[str, dict[str, object]] = {}
    for path in sorted(rule_dir.glob("*.json")):
        payload = _read_manifest(path)
        name = str(payload["name"])
        rules[name] = payload
    return RuleRegistry(rules=rules)


def rule_evidence_map(registry: RuleRegistry) -> dict[str, dict[str, object]]:
    mapping: dict[str, dict[str, object]] = {}
    for manifest in registry.rules.values():
        profile = str(manifest["profile"])
        for rule in manifest["rules"]:
            if not isinstance(rule, dict):
                raise ValueError(f"Rule manifest {manifest['name']} contains a non-structured rule entry")
            rule_id = str(rule["id"])
            mapping[f"{profile}.{rule_id}"] = {
                "profile": profile,
                "rule_id": rule_id,
                "title": str(rule["title"]),
                "evidence": list(rule.get("evidence", [])),
            }
    return mapping
