from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PlanningHorizon = Literal["immediate", "short", "scene", "arc", "long_term"]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class CognitiveLimits(BaseModel):
    """Absolute per-turn limits. Provider budget cannot raise these values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_context_items: int = Field(default=8, ge=0)
    max_active_hypotheses: int = Field(default=3, ge=0)
    max_reasoning_hops: int = Field(default=2, ge=0)
    max_candidate_intents: int = Field(default=3, ge=0)
    max_concurrent_goals: int = Field(default=2, ge=0)
    planning_horizon: PlanningHorizon = "short"
    confidence_ceiling_without_evidence: float = Field(default=0.68, ge=0.0, le=1.0)


class DomainCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effective_proficiency: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    match: Literal["direct", "adjacent", "weak", "unknown"] = "unknown"


class StableAbilityInput(BaseModel):
    """Small structural input accepted from the existing skill snapshot compiler."""

    model_config = ConfigDict(extra="allow", frozen=True)

    actor_id: str = Field(min_length=1)
    capability_revision: str = Field(default="capability:unknown", min_length=1)
    registry_revision: str = Field(default="skills:unknown", min_length=1)
    skills: tuple[dict[str, Any], ...] = ()
    allowed_action_families: tuple[str, ...] = ()
    blocked_action_families: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()

    @classmethod
    def from_value(cls, value: Mapping[str, Any] | BaseModel) -> "StableAbilityInput":
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        return cls.model_validate(dict(value))


class CapabilityEnvelope(BaseModel):
    """Frozen ability and cognition ceiling for one actor and turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    capability_revision: str = Field(min_length=1)
    envelope_revision: str = Field(min_length=1)
    cognitive_limits: CognitiveLimits
    active_domains: dict[str, DomainCapability] = Field(default_factory=dict)
    allowed_action_families: tuple[str, ...] = ()
    blocked_action_families: tuple[str, ...] = ()
    degradation_reasons: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    revision_pins: dict[str, str] = Field(default_factory=dict)
    envelope_digest: str = ""

    @model_validator(mode="after")
    def _freeze_digest(self) -> "CapabilityEnvelope":
        expected = self.compute_digest()
        if self.envelope_digest and self.envelope_digest != expected:
            raise ValueError("capability_envelope_digest_mismatch")
        object.__setattr__(self, "envelope_digest", expected)
        return self

    def compute_digest(self) -> str:
        payload = self.model_dump(mode="json", exclude={"envelope_digest"})
        return _digest(payload)

    def validate_domain(self, domain: str) -> DomainCapability:
        if not isinstance(domain, str) or not domain:
            raise ValueError("cognition_domain_required")
        capability = self.active_domains.get(domain)
        if capability is None or capability.match == "unknown":
            raise ValueError("cognition_domain_not_allowed")
        return capability

    @classmethod
    def compile(
        cls,
        *,
        actor_id: str,
        turn_id: str,
        profile: Mapping[str, Any] | BaseModel | None = None,
        stable_snapshot: Mapping[str, Any] | BaseModel | None = None,
        dynamic_state: Mapping[str, Any] | None = None,
        memory_modifier: float = 1.0,
        event_domain: str | None = None,
        event_domains: tuple[str, ...] | list[str] = (),
        allowed_action_families: tuple[str, ...] | list[str] = (),
        blocked_action_families: tuple[str, ...] | list[str] = (),
        capability_revision: str | None = None,
        envelope_revision: str | None = None,
        source_refs: tuple[str, ...] | list[str] = (),
        revision_pins: Mapping[str, str] | None = None,
    ) -> "CapabilityEnvelope":
        p = profile.model_dump(mode="json") if isinstance(profile, BaseModel) else dict(profile or {})
        layer = p.get("cognitive_capability_layer") or {}
        # The production profile currently predates this layer. These values are
        # the design's explicit baseline and are kept here until profile schema
        # admission adds authored values.
        authored = {
            "max_context_items": 8,
            "max_active_hypotheses": 3,
            "max_reasoning_hops": 2,
            "max_candidate_intents": 3,
            "max_concurrent_goals": 2,
            "planning_horizon": "short",
            "confidence_ceiling_without_evidence": 0.68,
        }
        authored.update(dict(layer.get("hard_limits") or {}))
        limits = CognitiveLimits.model_validate(authored)
        snapshot = StableAbilityInput.from_value(stable_snapshot or {
            "actor_id": actor_id,
            "capability_revision": capability_revision or f"capability:{actor_id}:0",
            "registry_revision": "skills:unknown",
        })
        dynamic = dict(dynamic_state or {})
        memory_modifier = max(0.0, min(1.0, float(memory_modifier)))
        domains = list(dict.fromkeys([*(event_domains or ()), *(([event_domain] if event_domain else []))]))
        skills = list(snapshot.skills)
        known_domains: dict[str, tuple[float, float]] = {}
        for skill in skills:
            proficiency = max(0.0, min(1.0, float(skill.get("proficiency", 0.0))))
            confidence = max(0.0, min(1.0, float(skill.get("confidence", 0.0))))
            for domain in skill.get("domains", ()) or ():
                known_domains[str(domain)] = (max(known_domains.get(str(domain), (0.0, 0.0))[0], proficiency), max(known_domains.get(str(domain), (0.0, 0.0))[1], confidence))
        if not known_domains:
            for domain in layer.get("knowledge_domains", ()) or ():
                known_domains[str(domain)] = (1.0, 1.0)
        active: dict[str, DomainCapability] = {}
        reasons: list[str] = []
        modifiers = dynamic.get("cognitive_modifiers", dynamic.get("modifiers", {}))
        if not isinstance(modifiers, Mapping):
            modifiers = {}
        for domain, (proficiency, confidence) in known_domains.items():
            if not domains:
                match = "direct"
            elif domain in domains:
                match = "direct"
            elif domain.split(":", 1)[0] in {item.split(":", 1)[0] for item in domains}:
                match = "adjacent"
            else:
                match = "weak"
            factor = {"direct": 1.0, "adjacent": 0.75, "weak": 0.45, "unknown": 0.20}[match]
            modifier = modifiers.get(domain, modifiers.get("general", 1.0))
            try:
                modifier = max(0.0, min(1.0, float(modifier)))
            except (TypeError, ValueError):
                modifier = 1.0
            active[domain] = DomainCapability(
                effective_proficiency=min(proficiency, proficiency * factor * modifier * memory_modifier),
                confidence=min(confidence, confidence * factor * modifier * memory_modifier),
                match=match,
            )
        if domains and not any(domain in active for domain in domains):
            reasons.append("domain_mismatch")
        if memory_modifier < 1.0:
            reasons.append("memory_degradation")
        if any(float(v) < 1.0 for v in modifiers.values() if isinstance(v, (int, float))):
            reasons.append("dynamic_state_degradation")
        refs = tuple(dict.fromkeys((*snapshot.source_refs, *source_refs)))
        pins = dict(revision_pins or {})
        pins.setdefault("capability_revision", snapshot.capability_revision)
        pins.setdefault("registry_revision", snapshot.registry_revision)
        return cls(
            actor_id=actor_id,
            turn_id=turn_id,
            capability_revision=capability_revision or snapshot.capability_revision,
            envelope_revision=envelope_revision or f"envelope:{actor_id}:{turn_id}",
            cognitive_limits=limits,
            active_domains=active,
            allowed_action_families=tuple(dict.fromkeys((*snapshot.allowed_action_families, *allowed_action_families))),
            blocked_action_families=tuple(dict.fromkeys((*snapshot.blocked_action_families, *blocked_action_families))),
            degradation_reasons=tuple(dict.fromkeys(reasons)),
            source_refs=refs,
            revision_pins=pins,
        )

    from_inputs = compile


__all__ = ["CapabilityEnvelope", "CognitiveLimits", "DomainCapability", "StableAbilityInput"]
