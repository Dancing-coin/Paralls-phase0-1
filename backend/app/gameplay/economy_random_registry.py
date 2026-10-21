"""Versioned authored candidate and seed policies for Economy random draws.

These YAML policies are introduced by the current stage-three design. They are
content inputs only; the Economy owner remains the sole result/receipt writer.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Self

import yaml

from app.gameplay.economy_random_policy import (
    EconomyRandomPolicy,
    SUPPORTED_ALGORITHM_REVISION,
    SUPPORTED_SEED_POLICY_REVISION,
)
from app.gameplay.random_business_admission import RandomBusinessSource


class EconomyRandomRegistryError(ValueError):
    """An authored random policy is missing, malformed, or ambiguous."""


_FIELDS = {
    "policy_ref", "policy_revision", "kind", "candidates", "issuer_ref",
    "fact_owner_ref", "actor_scope", "world_scope", "timeline_scope",
    "valid_from_world_tick", "valid_until_world_tick", "algorithm_revision",
    "seed_policy_revision", "read_principals", "receipt_lookup_ref",
    "revocation_owner_ref",
}


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


class EconomyRandomPolicyRegistry:
    """Read-only loader that freezes YAML policy revisions as admission sources."""

    def __init__(self, entries: dict[str, tuple[EconomyRandomPolicy, RandomBusinessSource]]) -> None:
        self._entries = dict(entries)
        self._directory: Path | None = None

    @classmethod
    def from_directory(cls, directory: str | Path) -> Self:
        root = Path(directory)
        if not root.is_dir():
            raise EconomyRandomRegistryError("economy_random_registry_directory_missing")
        entries: dict[str, tuple[EconomyRandomPolicy, RandomBusinessSource]] = {}
        for path in sorted(root.glob("*.yaml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict) or set(raw) != _FIELDS:
                    raise EconomyRandomRegistryError("economy_random_policy_fields_invalid")
                policy = EconomyRandomPolicy.model_validate({
                    "policy_ref": raw["policy_ref"],
                    "policy_revision": raw["policy_revision"],
                    "kind": raw["kind"],
                    "candidates": raw["candidates"],
                })
                if raw["algorithm_revision"] != SUPPORTED_ALGORITHM_REVISION:
                    raise EconomyRandomRegistryError("economy_random_algorithm_revision_unsupported")
                if raw["seed_policy_revision"] != SUPPORTED_SEED_POLICY_REVISION:
                    raise EconomyRandomRegistryError("economy_random_seed_policy_revision_unsupported")
                if policy.policy_ref in entries:
                    raise EconomyRandomRegistryError("economy_random_policy_duplicate")
                policy_data = policy.model_dump(mode="json")
                source_content = {key: raw[key] for key in sorted(_FIELDS - {"candidates"})}
                source_content["candidates"] = policy_data["candidates"]
                source_digest = _digest(source_content)
                source = RandomBusinessSource(
                    demand_ref=policy.policy_ref,
                    demand_revision=policy.policy_revision,
                    kind=policy.kind,
                    issuer_ref=raw["issuer_ref"],
                    fact_owner_ref=raw["fact_owner_ref"],
                    actor_scope=tuple(raw["actor_scope"]),
                    world_scope=tuple(raw["world_scope"]),
                    timeline_scope=tuple(raw["timeline_scope"]),
                    valid_from_world_tick=raw["valid_from_world_tick"],
                    valid_until_world_tick=raw["valid_until_world_tick"],
                    candidate_registry_ref=policy.policy_ref,
                    candidate_registry_revision=policy.policy_revision,
                    algorithm_revision=raw["algorithm_revision"],
                    seed_policy_revision=raw["seed_policy_revision"],
                    source_digest=source_digest,
                    read_principals=tuple(raw["read_principals"]),
                    receipt_lookup_ref=raw["receipt_lookup_ref"],
                    revocation_owner_ref=raw["revocation_owner_ref"],
                )
                entries[policy.policy_ref] = (policy, source)
            except EconomyRandomRegistryError:
                raise
            except Exception as exc:
                raise EconomyRandomRegistryError(f"economy_random_policy_invalid:{path.name}") from exc
        if not entries:
            raise EconomyRandomRegistryError("economy_random_registry_empty")
        registry = cls(entries)
        registry._directory = root
        return registry

    def reload(self) -> Self:
        """Reload the original authored directory and fail closed on drift."""
        if self._directory is None:
            raise EconomyRandomRegistryError("economy_random_registry_reload_unavailable")
        return type(self).from_directory(self._directory)

    def policy(self, policy_ref: str) -> EconomyRandomPolicy:
        try:
            return self._entries[policy_ref][0]
        except KeyError as exc:
            raise EconomyRandomRegistryError("economy_random_policy_missing") from exc

    def source(self, policy_ref: str) -> RandomBusinessSource:
        try:
            return self._entries[policy_ref][1]
        except KeyError as exc:
            raise EconomyRandomRegistryError("economy_random_policy_missing") from exc

    def policy_refs(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))


__all__ = ["EconomyRandomPolicyRegistry", "EconomyRandomRegistryError"]
