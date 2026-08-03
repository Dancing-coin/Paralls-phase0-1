"""Event-derived stable abilities and read-only current affordance resolution."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.resource_body_runtime import BodyRuntimeProjection, ResourceStateProjection


AbilityRank = Literal["none", "novice", "basic", "trained", "expert", "master"]
_RANKS: Mapping[AbilityRank, int] = MappingProxyType(
    {"none": 0, "novice": 1, "basic": 2, "trained": 3, "expert": 4, "master": 5}
)
_ABILITY_EVENT_TYPES = {
    "gameplay.ability.learned",
    "gameplay.ability.grant_activated",
    "gameplay.ability.grant_revoked",
    "gameplay.ability.restriction_applied",
    "gameplay.ability.restriction_removed",
}


class AbilityRuntimeError(ValueError):
    """Raised when a stable-ability event or query is not valid."""


@dataclass(frozen=True)
class AbilitySkillDefinition:
    skill_id: str
    definition_version: str


@dataclass(frozen=True)
class AbilityPathDefinition:
    path_id: str
    skill_id: str
    action_ref: str
    required_rank: AbilityRank = "novice"
    stamina_resource_id: str | None = None
    stamina_cost: int = 0
    required_function_id: str | None = None


@dataclass(frozen=True)
class LearnedAbilityState:
    skill_id: str
    rank: AbilityRank
    source_event_id: str


@dataclass(frozen=True)
class AbilityGrantState:
    grant_id: str
    skill_ids: tuple[str, ...]
    path_ids: tuple[str, ...]
    source_ref: str
    status: Literal["active", "revoked"]
    source_event_id: str


@dataclass(frozen=True)
class AbilityRestrictionState:
    restriction_id: str
    skill_ids: tuple[str, ...]
    action_refs: tuple[str, ...]
    blocking: bool
    source_ref: str
    status: Literal["active", "removed"]
    source_event_id: str


@dataclass(frozen=True)
class AbilityStateProjection:
    actor_ref: str
    learned: Mapping[str, LearnedAbilityState]
    grants: Mapping[str, AbilityGrantState]
    restrictions: Mapping[str, AbilityRestrictionState]
    source_revision_vector: Mapping[str, int]
    projection_revision: str


@dataclass(frozen=True)
class AbilityPathAffordance:
    path_id: str
    status: Literal["available", "blocked", "unknown"]
    blocker_codes: tuple[str, ...]
    cost_estimate: Mapping[str, int]


@dataclass(frozen=True)
class AbilityAffordanceProjection:
    actor_ref: str
    action_ref: str
    overall_status: Literal["available", "blocked", "unknown"]
    path_results: tuple[AbilityPathAffordance, ...]
    selected_advisory_path_id: str | None
    source_revision_vector: Mapping[str, int]
    explanation_digest: str


class AbilityDefinitionRegistry:
    """Small immutable-definition registry; it contains no actor state."""

    def __init__(self) -> None:
        self._skills: dict[str, AbilitySkillDefinition] = {}
        self._paths: dict[str, AbilityPathDefinition] = {}

    def register_skill(self, definition: AbilitySkillDefinition) -> None:
        if not definition.skill_id or not definition.definition_version or definition.skill_id in self._skills:
            raise AbilityRuntimeError("ability_skill_definition_invalid")
        self._skills[definition.skill_id] = definition

    def register_path(self, definition: AbilityPathDefinition) -> None:
        if (
            not definition.path_id
            or definition.path_id in self._paths
            or definition.skill_id not in self._skills
            or not definition.action_ref
            or definition.stamina_cost < 0
        ):
            raise AbilityRuntimeError("ability_path_definition_invalid")
        self._paths[definition.path_id] = definition

    def skill(self, skill_id: str) -> AbilitySkillDefinition:
        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise AbilityRuntimeError("ability_skill_definition_unknown") from exc

    def paths_for_action(self, action_ref: str) -> tuple[AbilityPathDefinition, ...]:
        return tuple(sorted((path for path in self._paths.values() if path.action_ref == action_ref), key=lambda path: path.path_id))

    def path(self, path_id: str) -> AbilityPathDefinition:
        try:
            return self._paths[path_id]
        except KeyError as exc:
            raise AbilityRuntimeError("ability_path_definition_unknown") from exc


class AbilityStateProjector:
    """Rebuilds durable ability truth from committed Gameplay events only."""

    def __init__(self, registry: AbilityDefinitionRegistry) -> None:
        self._registry = registry

    def rebuild(self, actor_ref: str, events: Sequence[GameplayEvent]) -> AbilityStateProjection:
        learned: dict[str, LearnedAbilityState] = {}
        grants: dict[str, AbilityGrantState] = {}
        restrictions: dict[str, AbilityRestrictionState] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if event.event_type not in _ABILITY_EVENT_TYPES:
                continue
            payload = event.payload
            if str(payload.get("actor_ref", "")) != actor_ref:
                raise AbilityRuntimeError("ability_actor_mismatch")
            if event.event_type == "gameplay.ability.learned":
                skill_id = _required_text(payload, "skill_id")
                self._registry.skill(skill_id)
                rank = _rank(payload.get("rank"))
                prior = learned.get(skill_id)
                if prior is not None and _RANKS[rank] < _RANKS[prior.rank]:
                    raise AbilityRuntimeError("ability_rank_regression")
                learned[skill_id] = LearnedAbilityState(skill_id, rank, event.event_id)
            elif event.event_type == "gameplay.ability.grant_activated":
                grant_id = _required_text(payload, "grant_id")
                if grant_id in grants and grants[grant_id].status == "active":
                    raise AbilityRuntimeError("ability_grant_duplicate")
                skill_ids = _known_skill_ids(payload.get("skill_ids"), self._registry)
                path_ids = _known_path_ids(payload.get("path_ids"), self._registry)
                grants[grant_id] = AbilityGrantState(grant_id, skill_ids, path_ids, _required_text(payload, "source_ref"), "active", event.event_id)
            elif event.event_type == "gameplay.ability.grant_revoked":
                grant_id = _required_text(payload, "grant_id")
                prior = grants.get(grant_id)
                if prior is None or prior.status != "active":
                    raise AbilityRuntimeError("ability_grant_inactive")
                grants[grant_id] = AbilityGrantState(prior.grant_id, prior.skill_ids, prior.path_ids, prior.source_ref, "revoked", event.event_id)
            elif event.event_type == "gameplay.ability.restriction_applied":
                restriction_id = _required_text(payload, "restriction_id")
                if restriction_id in restrictions and restrictions[restriction_id].status == "active":
                    raise AbilityRuntimeError("ability_restriction_duplicate")
                restrictions[restriction_id] = AbilityRestrictionState(
                    restriction_id,
                    _known_skill_ids(payload.get("skill_ids"), self._registry),
                    _text_tuple(payload.get("action_refs")),
                    bool(payload.get("blocking", True)),
                    _required_text(payload, "source_ref"),
                    "active",
                    event.event_id,
                )
            else:
                restriction_id = _required_text(payload, "restriction_id")
                prior = restrictions.get(restriction_id)
                if prior is None or prior.status != "active":
                    raise AbilityRuntimeError("ability_restriction_inactive")
                restrictions[restriction_id] = AbilityRestrictionState(prior.restriction_id, prior.skill_ids, prior.action_refs, prior.blocking, prior.source_ref, "removed", event.event_id)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        frozen_learned = MappingProxyType(dict(sorted(learned.items())))
        frozen_grants = MappingProxyType(dict(sorted(grants.items())))
        frozen_restrictions = MappingProxyType(dict(sorted(restrictions.items())))
        frozen_revisions = MappingProxyType(dict(sorted(revisions.items())))
        digest = _digest({"actor_ref": actor_ref, "learned": frozen_learned, "grants": frozen_grants, "restrictions": frozen_restrictions, "revisions": frozen_revisions})
        return AbilityStateProjection(actor_ref, frozen_learned, frozen_grants, frozen_restrictions, frozen_revisions, f"ability:{digest[:16]}")


class AbilityAuthorityService:
    """Writes only explicit, append-only stable-ability events through the store."""

    _PRINCIPAL = "actor_gameplay.skill_domain"

    def __init__(self, *, store: GameplayEventStore, registry: AbilityDefinitionRegistry) -> None:
        self._store = store
        self._registry = registry

    def learn(self, *, command_id: str, actor_ref: str, skill_id: str, rank: AbilityRank, source_ref: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        self._registry.skill(skill_id)
        return self._append(command_id, actor_ref, "gameplay.ability.learned", {"skill_id": skill_id, "rank": rank, "source_ref": source_ref}, idempotency_key, causation_id, correlation_id)

    def activate_grant(self, *, command_id: str, actor_ref: str, grant_id: str, skill_ids: Sequence[str], path_ids: Sequence[str], source_ref: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        _known_skill_ids(skill_ids, self._registry)
        _known_path_ids(path_ids, self._registry)
        return self._append(command_id, actor_ref, "gameplay.ability.grant_activated", {"grant_id": grant_id, "skill_ids": list(sorted(set(skill_ids))), "path_ids": list(sorted(set(path_ids))), "source_ref": source_ref}, idempotency_key, causation_id, correlation_id)

    def _append(self, command_id: str, actor_ref: str, event_type: str, payload: Mapping[str, object], idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        stream_id = f"gameplay:abilities:{actor_ref}"
        transaction_id = f"tx:{command_id}"
        event_payload = {"actor_ref": actor_ref, **payload}
        return self._store.append_batch({"transaction_id": transaction_id, "command_id": command_id, "expected_stream_revisions": {stream_id: self._store.get_stream_head(stream_id)}, "pinned_revisions": {"ability": self._store.get_stream_head(stream_id)}, "events": [{"event_id": f"evt:{command_id}:ability:1", "event_type": event_type, "schema_version": 1, "stream_id": stream_id, "stream_revision": 0, "global_sequence": 0, "transaction_id": transaction_id, "command_id": command_id, "causation_id": causation_id, "correlation_id": correlation_id, "visibility_policy": "authority_only", "payload": event_payload}], "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": f"{actor_ref}:{idempotency_key}", "payload_digest": _digest(event_payload)}, "outbox_entries": [], "result_digest": _digest(event_payload), "projection_refresh_hints": []})


class AbilityAffordanceResolver:
    """Pure current-availability projection; queries never append or reserve events."""

    def __init__(self, registry: AbilityDefinitionRegistry) -> None:
        self._registry = registry

    def resolve(self, *, actor_ref: str, action_ref: str, abilities: AbilityStateProjection, resources: ResourceStateProjection, body: BodyRuntimeProjection) -> AbilityAffordanceProjection:
        if {abilities.actor_ref, resources.actor_ref, body.actor_ref} != {actor_ref}:
            raise AbilityRuntimeError("ability_affordance_actor_mismatch")
        paths = self._registry.paths_for_action(action_ref)
        if not paths:
            return AbilityAffordanceProjection(actor_ref, action_ref, "unknown", (), None, _revisions(abilities, resources, body), _digest({"actor_ref": actor_ref, "action_ref": action_ref, "error": "action_unknown"}))
        results = tuple(self._resolve_path(path, abilities, resources, body) for path in paths)
        available = tuple(result for result in results if result.status == "available")
        overall: Literal["available", "blocked", "unknown"] = "available" if available else "unknown" if all(result.status == "unknown" for result in results) else "blocked"
        selected = available[0].path_id if available else None
        digest = _digest({"actor_ref": actor_ref, "action_ref": action_ref, "results": results, "revisions": _revisions(abilities, resources, body)})
        return AbilityAffordanceProjection(actor_ref, action_ref, overall, results, selected, _revisions(abilities, resources, body), digest)

    def _resolve_path(self, path: AbilityPathDefinition, abilities: AbilityStateProjection, resources: ResourceStateProjection, body: BodyRuntimeProjection) -> AbilityPathAffordance:
        blockers: list[str] = []
        learned = abilities.learned.get(path.skill_id)
        active_grants = tuple(grant for grant in abilities.grants.values() if grant.status == "active")
        granted = any(path.skill_id in grant.skill_ids or path.path_id in grant.path_ids for grant in active_grants)
        if not granted and (learned is None or _RANKS[learned.rank] < _RANKS[path.required_rank]):
            blockers.append("ability_not_granted")
        if any(restriction.status == "active" and restriction.blocking and (path.skill_id in restriction.skill_ids or path.action_ref in restriction.action_refs) for restriction in abilities.restrictions.values()):
            blockers.append("ability_restriction_blocking")
        if path.required_function_id:
            capacity = body.functions.get(path.required_function_id)
            if capacity is not None and capacity.status == "unavailable":
                blockers.append("required_body_function_unavailable")
        estimate: Mapping[str, int] = MappingProxyType({})
        if path.stamina_resource_id:
            entry = resources.entries.get(path.stamina_resource_id)
            if entry is None:
                blockers.append("affordance_input_unknown")
            else:
                estimate = MappingProxyType({path.stamina_resource_id: path.stamina_cost})
                if entry.available < path.stamina_cost:
                    blockers.append("resource_insufficient")
        return AbilityPathAffordance(path.path_id, "available" if not blockers else "unknown" if blockers == ["affordance_input_unknown"] else "blocked", tuple(blockers), estimate)


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise AbilityRuntimeError("ability_event_payload_invalid")
    return value


def _rank(value: object) -> AbilityRank:
    if not isinstance(value, str) or value not in _RANKS:
        raise AbilityRuntimeError("ability_rank_invalid")
    return value  # type: ignore[return-value]


def _text_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item for item in value):
        raise AbilityRuntimeError("ability_event_payload_invalid")
    return tuple(sorted(set(value)))


def _known_skill_ids(value: object, registry: AbilityDefinitionRegistry) -> tuple[str, ...]:
    values = _text_tuple(value)
    for skill_id in values:
        registry.skill(skill_id)
    return values


def _known_path_ids(value: object, registry: AbilityDefinitionRegistry) -> tuple[str, ...]:
    values = _text_tuple(value)
    for path_id in values:
        registry.path(path_id)
    return values


def _revisions(*projections: object) -> Mapping[str, int]:
    revisions: dict[str, int] = {}
    for projection in projections:
        for stream_id, revision in getattr(projection, "source_revision_vector").items():
            revisions[stream_id] = max(revisions.get(stream_id, 0), revision)
    return MappingProxyType(dict(sorted(revisions.items())))


def _digest(value: object) -> str:
    def default(item: object) -> object:
        if hasattr(item, "__dict__"):
            return item.__dict__
        if isinstance(item, Mapping):
            return dict(item)
        raise TypeError(type(item).__name__)
    return sha256(json.dumps(value, default=default, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


__all__ = [
    "AbilityAffordanceProjection", "AbilityAffordanceResolver", "AbilityAuthorityService", "AbilityDefinitionRegistry",
    "AbilityGrantState", "AbilityPathAffordance", "AbilityPathDefinition", "AbilityRuntimeError", "AbilitySkillDefinition",
    "AbilityStateProjection", "AbilityStateProjector", "LearnedAbilityState",
]
