"""Authored candidate policy for Economy owned random business.

This is a small, versioned policy designed and implemented in stage three.  It
contains no storage or clock; the Economy owner supplies those at commit time.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import hmac
from typing import Literal

from pydantic import ConfigDict, Field, StrictInt, model_validator

from app.gameplay.models import StrictGameplayModel

RandomBusinessKind = Literal["lottery", "loot", "event_choice"]

# Versioned contracts used by the stage-three owner.  The draw seed is derived
# from a durable per-window anchor using HMAC-SHA256; it is not a
# world-tick/operation seed and must not silently accept another algorithm.
SUPPORTED_ALGORITHM_REVISION = "algorithm:sha256-weighted-v1"
SUPPORTED_SEED_POLICY_REVISION = "seed:anchor-hmac-sha256-v1"


class EconomyRandomPolicyError(ValueError):
    pass


class RandomCandidate(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_ref: str = Field(min_length=1)
    result_ref: str = Field(min_length=1)
    weight: StrictInt = Field(gt=0)


class EconomyRandomPolicy(StrictGameplayModel):
    """The authored candidate/drop table consumed by the Economy owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    kind: RandomBusinessKind
    candidates: tuple[RandomCandidate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_candidates(self) -> "EconomyRandomPolicy":
        if len({candidate.candidate_ref for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("economy_random_candidate_duplicate")
        return self

    @property
    def candidate_registry_digest(self) -> str:
        value = [candidate.model_dump(mode="json") for candidate in self.candidates]
        return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def choose(self, *, seed: bytes) -> RandomCandidate:
        if not seed:
            raise EconomyRandomPolicyError("economy_random_seed_empty")
        total = sum(candidate.weight for candidate in self.candidates)
        point = int.from_bytes(sha256(seed).digest(), "big") % total
        for candidate in self.candidates:
            if point < candidate.weight:
                return candidate
            point -= candidate.weight
        raise EconomyRandomPolicyError("economy_random_candidate_selection_failed")

    def derive_draw_seed(self, *, anchor_seed: bytes, context: dict[str, object]) -> bytes:
        if len(anchor_seed) != 32:
            raise EconomyRandomPolicyError("economy_random_anchor_invalid")
        encoded = json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
        return hmac.new(anchor_seed, encoded, "sha256").digest()


@dataclass(frozen=True)
class EconomyRandomResult:
    kind: str
    operation_ref: str
    target_ref: str
    candidate_ref: str
    result_ref: str
    seed: str
    source_digest: str
    candidate_registry_digest: str
    policy_revision: str


def validate_random_payload(payload: dict[str, object]) -> None:
    """Rebuild the recorded choice without drawing entropy during replay."""
    try:
        policy = EconomyRandomPolicy.model_validate(payload["candidate_policy"])
        seed = bytes.fromhex(str(payload["seed"]))
        chosen = policy.choose(seed=seed)
        valid = (
            len(seed) == 32
            and payload["seed_digest"] == "sha256:" + sha256(seed).hexdigest()
            and payload["candidate_registry_digest"] == policy.candidate_registry_digest
            and payload["candidate_ref"] == chosen.candidate_ref
            and payload["result_ref"] == chosen.result_ref
            and payload["kind"] == policy.kind
            and payload["policy_revision"] == policy.policy_revision
            and payload["candidate_registry_ref"] == policy.policy_ref
            and payload["candidate_registry_revision"] == policy.policy_revision
            and payload["result_digest"] == random_payload_digest(payload)
        )
        context = payload.get("context")
        if isinstance(context, dict):
            context_digest = "sha256:" + sha256(json.dumps(context, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            valid = valid and payload.get("context_digest") == context_digest
    except (KeyError, TypeError, ValueError) as exc:
        raise EconomyRandomPolicyError("economy_random_payload_invalid") from exc
    if not valid:
        raise EconomyRandomPolicyError("economy_random_payload_invalid")


def validate_anchored_random_payload(payload: dict[str, object], *, anchor_seed: bytes) -> None:
    validate_random_payload(payload)
    context = payload.get("context")
    if not isinstance(context, dict):
        raise EconomyRandomPolicyError("economy_random_context_missing")
    if (payload.get("algorithm_revision") != SUPPORTED_ALGORITHM_REVISION
            or payload.get("seed_policy_revision") != SUPPORTED_SEED_POLICY_REVISION):
        raise EconomyRandomPolicyError("economy_random_revision_unsupported")
    if any(payload.get(key) != context.get(key) for key in (
        "world_ref", "timeline_ref", "window_ref", "operation_ref", "effect_ref",
        "target_ref", "draw_index", "source_digest", "demand_revision",
        "candidate_registry_digest", "candidate_registry_ref",
        "candidate_registry_revision", "algorithm_revision", "seed_policy_revision",
    )):
        raise EconomyRandomPolicyError("economy_random_context_conflict")
    policy = EconomyRandomPolicy.model_validate(payload["candidate_policy"])
    expected = policy.derive_draw_seed(anchor_seed=anchor_seed, context=context)
    if payload.get("seed") != expected.hex():
        raise EconomyRandomPolicyError("economy_random_derived_seed_invalid")


def random_payload_digest(payload: dict[str, object]) -> str:
    value = {key: item for key, item in payload.items() if key != "result_digest"}
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


__all__ = [
    "EconomyRandomPolicy",
    "EconomyRandomPolicyError",
    "EconomyRandomResult",
    "RandomCandidate",
    "RandomBusinessKind",
    "SUPPORTED_ALGORITHM_REVISION",
    "SUPPORTED_SEED_POLICY_REVISION",
]
