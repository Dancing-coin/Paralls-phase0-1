"""Fact and pure-model registrations for the opt-in credential reference slice."""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
import heapq
import re
from types import MappingProxyType
from typing import Any


REGISTERED_OWNER_IDS = frozenset({
    "Body",
    "Equipment",
    "Inventory",
    "Ownership",
    "Production",
    "Morale",
    "Presence",
    "LifeState",
    "Survival",
    "Status",
    "Transport",
    "Population",
    "Command",
    "Organization",
    "Government",
    "Information",
    "Economy",
    "Social",
    "Politics",
    "Territory",
    "Objective",
    "Campaign",
    "Credential",  # Legacy pack identifier; not a v2 domain Owner.
})
REGISTERED_FACT_TYPE_PRIMITIVES = frozenset({"pool", "machine", "holdings", "bond", "process", "place"})
_FACT_TYPE_DOMAIN_PATTERN = re.compile(r"^[a-z_]{2,24}$")
_FACT_TYPE_NAME_PATTERN = re.compile(r"^[a-z0-9_-]{2,48}$")
_FACT_TYPE_FIELD_PRIMITIVES = {
    "aggregation": {"pool", "holdings"},
    "refold_model_ref": {"pool", "holdings"},
    "state_set_ref": {"machine"},
    "bond_types": {"bond"},
    "place_kind": {"place"},
}
_SELECTOR_REFERENCE_PATTERN = re.compile(r"^[^\s()]+$")


def _principal_selector_error(selector: Any) -> str | None:
    if not isinstance(selector, str) or not selector or selector != selector.strip():
        return "facttype_selector_invalid"
    if selector in ("world", "self", "recipient_of(subject)"):
        return None
    for prefix in ("faction:", "role:"):
        if selector.startswith(prefix):
            reference = selector[len(prefix):]
            return None if _SELECTOR_REFERENCE_PATTERN.fullmatch(reference) else "facttype_selector_invalid"
    for function in ("owner_of", "holder_of"):
        prefix = f"{function}("
        if selector.startswith(prefix) and selector.endswith(")"):
            reference = selector[len(prefix):-1]
            return None if _SELECTOR_REFERENCE_PATTERN.fullmatch(reference) else "facttype_selector_invalid"
    if selector.startswith("group_of(") and selector.endswith(")"):
        nested = selector[len("group_of("):-1]
        if nested.startswith("group_of("):
            return "facttype_selector_nesting_invalid"
        return _principal_selector_error(nested) or None
    return "facttype_selector_invalid"


@dataclass(frozen=True)
class Violation:
    code: str
    target: str
    file: str
    line: int
    hint: str


class RegistrationRejected(ValueError):
    def __init__(self, violations: Sequence[Violation]):
        self.violations = tuple(violations)
        super().__init__(", ".join(v.code for v in violations))


class ResolverInputError(ValueError):
    pass


def freeze(value: Any) -> Any:
    """Copy a JSON-shaped input; reject capabilities and mutable objects."""
    if value is None or type(value) in (str, bool, int):
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ResolverInputError("resolver_input_invalid")
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    raise ResolverInputError("resolver_input_invalid")


class RestrictedInputs(Mapping[str, Any]):
    """Only the declared input values survive construction."""
    def __init__(self, values: Mapping[str, Any], reads: Sequence[str]):
        self.__reads = frozenset(reads)
        self.__values = freeze({key: values[key] for key in reads if key in values})

    def __getitem__(self, key: str) -> Any:
        if key not in self.__reads:
            raise ResolverInputError("resolver_input_undeclared")
        if key not in self.__values:
            raise ResolverInputError("resolver_input_missing")
        return self.__values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self.__values))

    def __len__(self) -> int:
        return len(self.__values)


@dataclass(frozen=True)
class FactType:
    fact_type_id: str
    owner_ref: str
    primitive: str
    visibility: Mapping[str, Any]
    state_set_ref: str | None
    resolution_order: int


@dataclass(frozen=True)
class Model:
    model_ref: str
    owner_ref: str
    implementation: str
    reads: tuple[str, ...]
    writes_fact_types: tuple[str, ...]
    input_schema: str
    output_schema: str
    determinism_policy: Mapping[str, Any]
    params: Mapping[str, Any]
    handler: Callable[[RestrictedInputs, Mapping[str, Any]], Any]


class FactTypeRegistry:
    def __init__(self, facts: Mapping[str, FactType], models: Mapping[str, Model], machines: Mapping[str, Any]):
        self.facts = MappingProxyType(dict(facts))
        # Code and data models use this same table and evaluation entry point.
        self.models = MappingProxyType(dict(models))
        self.machines = freeze(machines)

    @classmethod
    def compile(cls, *, facts: Mapping[str, Any], models: Mapping[str, Any],
                machines: Mapping[str, Any], owners: Sequence[str], resolve_order: Mapping[str, Any] | None,
                handlers: Mapping[str, Callable], locations: Mapping[str, tuple[str, int]] | None = None,
                pool_defs: Mapping[str, Any] | None = None) -> FactTypeRegistry:
        issues: list[Violation] = []
        def reject(code: str, target: str, hint: str) -> None:
            file, line = (locations or {}).get(target, ("<declaration>", 1))
            issues.append(Violation(code, target, file, line, hint))

        if any(owner not in REGISTERED_OWNER_IDS for owner in owners):
            reject("facttype_owner_unknown", "owners", "reference a code-registered Owner ID")

        for target, spec in facts.items():
            if not spec.get("visibility"):
                reject("facttype_visibility_missing", target, "visibility must be explicitly nonempty")
            visibility = spec.get("visibility")
            if isinstance(visibility, Mapping) and "learnable_by" in visibility:
                selectors = visibility["learnable_by"]
                if not isinstance(selectors, (list, tuple)):
                    reject("facttype_selector_invalid", target, "learnable_by must be a list of principal selectors")
                else:
                    for selector in selectors:
                        code = _principal_selector_error(selector)
                        if code is not None:
                            reject(code, target, "use a registered principal selector with at most one group_of layer")
            if spec.get("owner_ref") not in owners:
                reject("facttype_owner_unknown", target, "register the fact owner first")
            if spec.get("aggregation") == "distribution":
                refold_model_ref = spec.get("refold_model_ref")
                if not isinstance(refold_model_ref, str) or not refold_model_ref:
                    reject("facttype_refold_missing", target, "distribution FactTypes must reference a refold model")
            primitive = spec.get("primitive")
            if "process_kind" in spec and primitive != "process":
                reject("facttype_process_kind_invalid", target,
                       "process_kind is only valid for the process primitive")
            if any(field in spec and primitive not in allowed_primitives
                   for field, allowed_primitives in _FACT_TYPE_FIELD_PRIMITIVES.items()):
                reject("facttype_field_primitive_invalid", target,
                       "remove fields that are not supported by the FactType primitive")
            if primitive is None:
                reject("primitive_missing", target, "declare one of the registered FactType primitives")
            elif primitive not in REGISTERED_FACT_TYPE_PRIMITIVES:
                reject("facttype_primitive_unknown", target, "declare a registered FactType primitive")
            elif primitive == "machine":
                if spec.get("state_set_ref") not in machines:
                    reject("facttype_schema_unknown", target, "register the machine state set")
            elif primitive == "pool":
                if pool_defs is None or target not in pool_defs:
                    reject("facttype_schema_unknown", target, "register the Pool definition for this FactType")
            parts = target.split(":")
            has_missing_scope = (
                (len(parts) == 3 and parts[0] == "fact" and all(parts[1:]))
                or (len(parts) == 4 and parts[0] == "fact" and parts[1] != ""
                    and parts[2] == "" and parts[3] != "")
            )
            if has_missing_scope:
                reject("facttype_scope_missing", target, "include a nonempty scope in fact:domain:scope:name")
            elif (
                len(parts) != 4
                or parts[0] != "fact"
                or not all(parts[1:])
                or len(target) > 128
                or not _FACT_TYPE_DOMAIN_PATTERN.fullmatch(parts[1])
                or not _FACT_TYPE_NAME_PATTERN.fullmatch(parts[3])
            ):
                reject("facttype_naming_invalid", target, "use fact:domain:scope:name")
            else:
                identity = spec.get("identity")
                scope = parts[2]
                if identity is None:
                    reject("facttype_identity_missing", target, "declare one of the registered FactType identities")
                elif identity not in ("singleton", "entity_ref", "collection_ref", "region_ref"):
                    reject("facttype_identity_invalid", target, "use a registered FactType identity")
                elif identity == "singleton" and scope != "global":
                    reject("facttype_identity_scope_mismatch", target, "singleton FactTypes must use the global scope")
                elif identity != "singleton" and scope == "global":
                    reject("facttype_identity_scope_mismatch", target, "only singleton FactTypes may use the global scope")

        for target, machine in machines.items():
            states = machine.get("states", [])
            terminals = machine.get("terminal_states", [])
            transitions = machine.get("transitions", [])
            if (not states or len(set(states)) != len(states) or not set(terminals) <= set(states)
                    or any(len(edge) != 2 or edge[0] not in states or edge[1] not in states or edge[0] in terminals for edge in transitions)):
                reject("facttype_machine_invalid", target, "transitions must connect states and never leave a terminal")

        edges = [] if resolve_order is None else resolve_order.get("before", [])
        covered = set() if resolve_order is None else set(resolve_order.get("unrelated", []))
        adjacency = {name: set() for name in facts}
        degrees = {name: 0 for name in facts}
        for edge in edges:
            if len(edge) != 2 or any(name not in facts for name in edge):
                reject("facttype_resolution_order_unknown", "resolve_order", "edges must name registered facts")
                continue
            left, right = edge
            covered.update(edge)
            if right not in adjacency[left]:
                adjacency[left].add(right)
                degrees[right] += 1
        for target in facts:
            if target not in covered:
                reject("facttype_resolution_order_missing", target, "declare a before edge or explicit unrelated membership")
        ready = [(facts[name]["owner_ref"], name) for name, degree in degrees.items() if degree == 0]
        heapq.heapify(ready)
        ordered = []
        while ready:
            _, name = heapq.heappop(ready)
            ordered.append(name)
            for next_name in sorted(adjacency[name]):
                degrees[next_name] -= 1
                if degrees[next_name] == 0:
                    heapq.heappush(ready, (facts[next_name]["owner_ref"], next_name))
        if len(ordered) != len(facts):
            reject("facttype_resolution_order_cycle", "resolve_order", "remove the dependency cycle")

        compiled_models = {}
        for target, spec in models.items():
            writes = spec.get("writes_fact_types", [])
            layers = spec.get("layers", [])
            for layer in [spec, *layers]:
                for fact in layer.get("writes_fact_types", []):
                    if fact not in facts:
                        reject("resolver_writes_undeclared", target, "register every output fact")
                    elif facts[fact].get("owner_ref") in owners and layer.get("owner_ref") != facts[fact]["owner_ref"]:
                        reject("resolver_owner_mismatch", target, "each resolver layer must match the output fact owner")
                    if fact not in writes:
                        reject("resolver_writes_undeclared", target, "layer outputs must belong to the model write set")
            policy = spec.get("determinism_policy", {})
            random_policy = policy.get("random")
            seeded_source_valid = (
                random_policy != "seeded"
                or policy.get("seed_source") in ("world_tick", "command_id")
            )
            if (policy.get("iteration_order") != "resolution_order"
                    or random_policy not in ("none", "seeded")
                    or not seeded_source_valid
                    or policy.get("numeric_precision") not in ("fixed_point", "decimal", "float64")
                    or policy.get("rounding") not in ("half_up", "floor", "truncate")):
                reject("resolver_missing_determinism", target, "pin precision, rounding, iteration order and randomness")
            kind = spec.get("implementation")
            handler_ref = target if kind == "code" else spec.get("evaluator_ref")
            handler = handlers.get(handler_ref)
            if kind not in ("code", "data") or handler is None:
                reject("resolver_implementation_unknown", target, "provide a registered code or data evaluator")
                continue
            if not spec.get("input_schema") or not spec.get("output_schema"):
                reject("resolver_schema_missing", target, "declare versioned input and output schemas")
            compiled_models[target] = Model(target, spec["owner_ref"], kind, tuple(spec.get("reads", [])),
                tuple(writes), spec.get("input_schema", ""), spec.get("output_schema", ""),
                freeze(policy), freeze(spec.get("params", {})), handler)
        if issues:
            unique = {(v.code, v.target): v for v in issues}
            raise RegistrationRejected(sorted(unique.values(), key=lambda v: (v.file, v.line, v.code, v.target)))
        compiled = {name: FactType(name, facts[name]["owner_ref"], facts[name]["primitive"],
            freeze(facts[name]["visibility"]), facts[name].get("state_set_ref"), index + 10)
            for index, name in enumerate(ordered)}
        return cls(compiled, compiled_models, machines)

    def evaluate(self, model_ref: str, values: Mapping[str, Any]) -> Any:
        model = self.models[model_ref]
        return model.handler(RestrictedInputs(values, model.reads), model.params)
