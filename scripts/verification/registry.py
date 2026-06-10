from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProfileRegistry:
    profiles: dict[str, dict[str, object]]
    profile_order: list[str]


@dataclass(frozen=True)
class RuleRegistry:
    rules: dict[str, dict[str, object]]


def _read_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema_version = payload.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"{path} uses unsupported schema_version {schema_version!r}; "
            f"expected {SUPPORTED_SCHEMA_VERSION}"
        )
    return payload


def load_profile_registry(project_root: Path) -> ProfileRegistry:
    profile_dir = project_root / ".harness" / "profiles"
    profiles: dict[str, dict[str, object]] = {}
    for path in sorted(profile_dir.glob("*.json")):
        payload = _read_manifest(path)
        name = str(payload["name"])
        profiles[name] = payload
    profile_order = [
        str(profile["name"])
        for profile in sorted(profiles.values(), key=lambda payload: int(payload.get("order", 0)))
    ]
    return ProfileRegistry(profiles=profiles, profile_order=profile_order)


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
