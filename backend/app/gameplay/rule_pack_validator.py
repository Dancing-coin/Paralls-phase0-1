"""Atomic, offline loader for the supported rule-pack YAML sections."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Callable, Iterator, Mapping

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode
from yaml.tokens import AliasToken, AnchorToken, TagToken

from app.gameplay.fact_type_registry import (
    REGISTERED_OWNER_IDS, FactTypeRegistry, RegistrationRejected, Violation, freeze,
)
from app.gameplay.l5_pipeline import Pipeline, compile_pipeline, impact_layers_cross_hosts
from app.gameplay.l5_play_pattern import PlayPattern, PlayPatternRejected, compile_play_pattern
from app.gameplay.l5_reaction import Reaction, ReactionRejected, compile_reactions
from app.gameplay.l5_workflow import Workflow, compile_workflow
from app.gameplay.pool_runtime import PoolDefinition, PoolError, PoolThreshold

_FACT_TYPE_PRIMITIVES = frozenset({"pool", "machine", "holdings", "bond", "process", "place"})


@dataclass(frozen=True)
class PackRevision:
    pack_id: str
    pack_version: str
    content_hash: str


@dataclass(frozen=True)
class LoadedPack:
    pack_id: str
    version: str
    content_hash: str
    registry: FactTypeRegistry
    legacy_rule: Mapping[str, Any]
    pool_defs: Mapping[str, Mapping[str, Any]] = field(default_factory=lambda: MappingProxyType({}))
    entity_types: Mapping[str, Mapping[str, Any]] = field(default_factory=lambda: MappingProxyType({}))
    impact_profiles: Mapping[str, Mapping[str, Any]] = field(default_factory=lambda: MappingProxyType({}))
    aggregation_models: Mapping[str, Mapping[str, Any]] = field(default_factory=lambda: MappingProxyType({}))
    bindings: Mapping[str, Mapping[str, Any]] = field(default_factory=lambda: MappingProxyType({}))
    resolved_packs: tuple[PackRevision, ...] = ()
    command_catalog: Mapping[str, Mapping[str, Any]] = field(default_factory=lambda: MappingProxyType({}))
    pipelines: Mapping[str, Pipeline] = field(default_factory=lambda: MappingProxyType({}))
    workflows: Mapping[str, Workflow] = field(default_factory=lambda: MappingProxyType({}))
    reactions: Mapping[str, Reaction] = field(default_factory=lambda: MappingProxyType({}))
    play_patterns: Mapping[str, PlayPattern] = field(default_factory=lambda: MappingProxyType({}))


def _validate_pool_definition(target: str, spec: Any) -> None:
    fields = {
        "bound_lower", "bound_upper", "initial", "decimals", "integration", "hysteresis",
        "description", "version", "deprecated",
    }
    if not isinstance(spec, dict) or spec.keys() - fields:
        raise PoolError("pack_schema_invalid")
    scale = spec.get("decimals")
    if type(scale) is not int or scale < 0:
        raise PoolError("pack_pool_scale_invalid")

    def decimal_value(value: Any) -> Decimal:
        if type(value) is int:
            return Decimal(value)
        if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
            raise PoolError("pack_pool_number_invalid")
        if len(value.partition(".")[2]) > scale:
            raise PoolError("pack_pool_scale_invalid")
        return Decimal(value)

    integration = spec.get("integration")
    if not isinstance(integration, dict):
        raise PoolError("pack_pool_integration_invalid")
    mode = integration.get("mode")
    if mode == "none" and integration.keys() == {"mode"}:
        rate = Decimal(0)
    elif mode == "rate" and integration.keys() == {"mode", "rate_per_tick"}:
        rate = decimal_value(integration["rate_per_tick"])
    else:
        raise PoolError("pack_pool_integration_invalid")

    hysteresis = spec.get("hysteresis")
    if not isinstance(hysteresis, list):
        raise PoolError("pack_pool_hysteresis_invalid")
    thresholds = []
    for row in hysteresis:
        if (not isinstance(row, dict) or row.keys() != {"state", "enter_below", "exit_above"}
                or not isinstance(row["state"], str)):
            raise PoolError("pack_pool_hysteresis_invalid")
        thresholds.append(PoolThreshold(
            row["state"], decimal_value(row["enter_below"]), decimal_value(row["exit_above"]),
        ))
    PoolDefinition(
        target, decimal_value(spec.get("bound_lower")), decimal_value(spec.get("bound_upper")),
        decimal_value(spec.get("initial")), rate, tuple(thresholds),
    )


def _impact_violations(
    spec: Any, *, registry: FactTypeRegistry, entity_types: Mapping[str, Any],
    fact_specs: Mapping[str, Any],
) -> Iterator[tuple[str, str]]:
    fields = {"target_entity_type", "layers", "atomicity", "description", "version", "deprecated"}
    if not isinstance(spec, dict) or spec.keys() - fields:
        yield "pack_schema_invalid", "declare only impact routing fields"
        return

    target = spec.get("target_entity_type")
    slot_patterns = None
    if isinstance(target, str) and target in entity_types:
        slot_patterns = {slot["fact_type_pattern"] for slot in entity_types[target]["slots"]}
    else:
        yield "impact_target_entity_unknown", "reference a declared entity type"

    atomicity = spec.get("atomicity")
    if "atomicity" in spec and atomicity not in ("atomic", "obligation"):
        yield "impact_atomicity_invalid", "declare atomic or obligation"

    layers = spec.get("layers")
    if not isinstance(layers, list) or not layers:
        yield "impact_layers_invalid", "declare a nonempty ordered list of routing layers"
        return

    orders = []
    fact_orders = []
    hosts = set()
    for layer in layers:
        if isinstance(layer, dict) and "owner_ref" in layer:
            yield "impact_layer_owner_mismatch", "derive the writer from the registered FactType"
            continue
        if (not isinstance(layer, dict) or layer.keys() != {"order", "fact_type", "resolver"}
                or type(layer["order"]) is not int or layer["order"] < 1
                or not isinstance(layer["fact_type"], str) or not isinstance(layer["resolver"], str)):
            yield "impact_layer_invalid", "each layer needs a positive order and FactType and Resolver references"
            continue

        orders.append(layer["order"])
        fact_id = layer["fact_type"]
        fact = registry.facts.get(fact_id)
        model = registry.models.get(layer["resolver"])
        if model is None:
            yield "impact_layer_resolver_unknown", "reference a registered Resolver"
        if fact is None:
            yield "impact_layer_facttype_unknown", "reference a registered FactType"
            continue
        if slot_patterns is not None and fact_id not in slot_patterns:
            yield "impact_layer_slot_unknown", "reference a FactType slot on the target entity type"
        if model is not None and (model.owner_ref != fact.owner_ref or fact_id not in model.writes_fact_types):
            yield "impact_layer_owner_mismatch", "the resolver must declare this FactType in its Owner write set"
        fact_orders.append(fact.resolution_order)
        host = fact_specs[fact_id].get("host")
        if host not in ("ue", "paralls", "population", "either"):
            yield "impact_layer_host_unknown", "declare a supported host on the layer FactType"
        else:
            hosts.add(host)

    if orders != sorted(set(orders)) or fact_orders != sorted(set(fact_orders)):
        yield "impact_layer_conflicts_order", "list unique layers in ascending FactType resolution order"
    if impact_layers_cross_hosts(hosts, len(layers)) and atomicity != "obligation":
        yield "impact_atomic_cross_host", "use obligation unless all layers are pinned to the same host"


def _aggregation_violations(spec: Any, registry: FactTypeRegistry) -> Iterator[tuple[str, str]]:
    fields = {"mode", "refold_model_ref", "refold_triggers", "description", "version", "deprecated"}
    if not isinstance(spec, dict) or spec.keys() - fields:
        yield "pack_schema_invalid", "declare only aggregation fields"
        return

    mode = spec.get("mode")
    if mode not in ("none", "sum", "distribution", "ordered"):
        yield "pack_aggregation_mode_invalid", "declare none, sum, distribution or ordered"
        return
    if mode != "distribution":
        if {"refold_model_ref", "refold_triggers"} & spec.keys():
            yield "pack_aggregation_refold_unexpected", "refold declarations apply only to distribution"
        return

    refold = spec.get("refold_model_ref")
    if not isinstance(refold, str) or not refold:
        yield "pack_aggregation_refold_missing", "distribution requires a refold Resolver"
    elif refold not in registry.models:
        yield "pack_aggregation_refold_unknown", "reference a registered refold Resolver"

    if "refold_triggers" in spec:
        triggers = spec["refold_triggers"]
        supported = ("split", "merge", "fidelity_change", "scope_change")
        if (not isinstance(triggers, list) or not triggers
                or any(trigger not in supported for trigger in triggers)
                or len(set(triggers)) != len(triggers)):
            yield "pack_aggregation_triggers_invalid", "list unique distribution refold triggers"


def _binding_violations(spec: Any, registry: FactTypeRegistry) -> Iterator[tuple[str, str]]:
    fields = {"applies_to", "cost_model", "description", "version", "deprecated"}
    if not isinstance(spec, dict) or spec.keys() - fields:
        yield "pack_schema_invalid", "declare only skill cost binding fields"
        return
    targets = spec.get("applies_to")
    if (not isinstance(targets, list) or not targets
            or any(not isinstance(target, str) or not re.fullmatch(r"skill:[a-z][a-z0-9_-]*", target)
                   for target in targets)
            or len(set(targets)) != len(targets)):
        yield "pack_binding_targets_invalid", "list unique qualified skill references"
    model_ref = spec.get("cost_model")
    if not isinstance(model_ref, str) or model_ref not in registry.models:
        yield "pack_binding_model_unknown", "reference a registered cost Resolver"


def _command_violations(
    command_type: str, spec: Mapping[str, Any], owner_domains: Mapping[str, str], owners: list[str],
) -> Iterator[tuple[str, str]]:
    fields = {"version", "handled_by", "payload_schema", "requires_authority", "idempotency_shape",
              "description", "deprecated"}
    if spec.keys() - fields:
        yield "pack_schema_invalid", "declare only Command catalog fields"

    if not re.fullmatch(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*", command_type):
        yield "pack_command_name_invalid", "use the domain.verb command name"
    elif command_type.partition(".")[0] not in owner_domains.values():
        yield "pack_command_domain_unknown", "reference a code-registered Owner domain"

    owner = spec.get("handled_by")
    if not isinstance(owner, str) or owner not in owners or owner not in owner_domains:
        yield "pack_command_owner_unknown", "declare a single code-registered handler Owner"
    version = spec.get("version")
    if type(version) is not int or version < 1:
        yield "pack_command_version_invalid", "use a positive command version"
    payload_schema = spec.get("payload_schema")
    if not isinstance(payload_schema, str) or not payload_schema.strip():
        yield "pack_command_payload_schema_invalid", "declare a payload schema reference"
    if type(spec.get("requires_authority")) is not bool:
        yield "pack_command_authority_invalid", "declare whether a grant is required"
    if spec.get("idempotency_shape") not in (
        "command_id", "command_id + step", "principal_ref + idempotency_key",
        "effect_id + scheduled_world_tick",
    ):
        yield "pack_command_idempotency_shape_invalid", "declare a registered command idempotency shape"


@dataclass
class _PackSource:
    manifest_path: Path
    manifest: dict[str, Any]
    sections: dict[str, dict[str, Any]]
    locations: dict[tuple[str, str], tuple[str, int]]
    revision: PackRevision


def _reject_issues(issues: list[Violation]) -> None:
    if issues:
        unique = {(v.code, v.target, v.file, v.line): v for v in issues}
        raise RegistrationRejected(sorted(unique.values(), key=lambda v: (v.file, v.line, v.code, v.target)))


def _read_pack(directory: Path, *, running: bool = False) -> _PackSource:
    directory = directory.resolve()
    issues: list[Violation] = []
    locations: dict[tuple[str, str], tuple[str, int]] = {}
    raw_files = {}

    def reject(code, target, file, line, hint):
        issues.append(Violation(code, target, str(file), line, hint))

    def read(path: Path, section: str) -> dict:
        if not path.is_file():
            reject("pack_content_missing", path.name, path, 1, "declare an existing pack file")
            return {}
        if path.stat().st_size > 512 * 1024:
            reject("pack_file_too_large", path.name, path, 1, "split files larger than 512 KB")
            return {}
        try:
            text = path.read_text(encoding="utf-8")
            forbidden = False
            for token in yaml.scan(text):
                if isinstance(token, (AnchorToken, AliasToken, TagToken)):
                    forbidden = True
                    reject("pack_yaml_feature_forbidden", path.name, path, token.start_mark.line + 1, "anchors, aliases and explicit tags are forbidden")
            if forbidden:
                return {}
            node = yaml.compose(text, Loader=yaml.SafeLoader)
        except (yaml.YAMLError, UnicodeError) as error:
            mark = getattr(error, "problem_mark", None)
            reject("pack_yaml_invalid", path.name, path, mark.line + 1 if mark else 1, "use one UTF-8 YAML mapping document")
            return {}
        if not isinstance(node, MappingNode):
            reject("pack_schema_invalid", path.name, path, 1, "each file must be a mapping")
            return {}

        def convert(n, target, key=False):
            line = n.start_mark.line + 1
            if isinstance(n, MappingNode):
                result = {}
                for k, v in n.value:
                    if not isinstance(k, ScalarNode) or k.tag != "tag:yaml.org,2002:str":
                        reject("pack_key_invalid", target, path, line, "mapping keys must be strings")
                        continue
                    if k.value in result:
                        reject("pack_key_duplicate", target, path, k.start_mark.line + 1, "duplicate keys are forbidden")
                    if k.value in {"if", "loop", "script", "code"}:
                        reject("pack_contains_logic", target, path, k.start_mark.line + 1, "use a registered model reference and data parameters")
                    result[k.value] = convert(v, target)
                return result
            if isinstance(n, SequenceNode):
                return [convert(item, target) for item in n.value]
            if not isinstance(n, ScalarNode):
                reject("pack_schema_invalid", target, path, line, "use scalar, sequence or mapping data")
                return None
            if n.tag == "tag:yaml.org,2002:float" or (n.style is None and re.fullmatch(r"[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)", n.value)):
                reject("pack_float_forbidden", target, path, line, "use a quoted decimal with explicit precision")
                return None
            if n.tag == "tag:yaml.org,2002:int":
                if not re.fullmatch(r"-?(0|[1-9][0-9]*)", n.value):
                    reject("pack_number_invalid", target, path, line, "use a decimal integer literal")
                    return None
                return int(n.value)
            if n.tag == "tag:yaml.org,2002:bool" and n.value in ("true", "false"):
                return n.value == "true"
            if n.tag == "tag:yaml.org,2002:null" and n.value == "null":
                return None
            if n.tag != "tag:yaml.org,2002:str" or n.style not in ('"', "'"):
                reject("pack_scalar_invalid", target, path, line, "quote string values; only true, false, null and integers may be bare")
            if "${" in n.value:
                reject("pack_contains_logic", target, path, line, "environment substitution is forbidden")
            return n.value

        result = {}
        for k, v in node.value:
            if not isinstance(k, ScalarNode) or k.tag != "tag:yaml.org,2002:str":
                reject("pack_key_invalid", path.name, path, 1, "mapping keys must be strings")
                continue
            if k.value in result:
                reject("pack_key_duplicate", k.value, path, k.start_mark.line + 1, "duplicate entry")
            if k.value in {"if", "loop", "script", "code"}:
                reject("pack_contains_logic", k.value, path, k.start_mark.line + 1, "executable keys are forbidden")
            locations[section, k.value] = (str(path), k.start_mark.line + 1)
            result[k.value] = convert(v, k.value)
        raw_files[path.relative_to(directory).as_posix()] = result
        return result

    manifest_path = directory / "pack.yaml"
    manifest = read(manifest_path, "manifest")
    if "primitives" in manifest:
        file, line = locations["manifest", "primitives"]
        reject("pack_defines_primitive", "primitives", file, line,
               "the six FactType primitives are registered in code")
    if running:
        reject("pack_runtime_reload_forbidden", "pack", manifest_path, 1, "load only before runtime starts")
    parent = manifest.get("parent_pack")
    if parent is not None and (
        not isinstance(parent, dict) or parent.keys() != {"pack_id", "pack_version"}
        or any(not isinstance(value, str) or not value for value in parent.values())
    ):
        reject("pack_parent_ref_invalid", "parent_pack", manifest_path, 1, "pin the parent package ID and version")
    for key in ("pack_id", "pack_version"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            reject("pack_schema_invalid", key, manifest_path, 1, "declare nonempty pack identity and version")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        reject("pack_schema_invalid", "schema_version", manifest_path, 1, "supported pack schema is 1")
    contents = manifest.get("contents", {})
    sections = {name: {} for name in (
        "fact_types", "machine_defs", "models", "pool_defs", "entity_types", "impact_profiles",
        "aggregation_models", "bindings", "command_catalog", "pipelines", "workflows",
        "reactions", "play_patterns",
    )}
    declared = {"pack.yaml"}
    if not isinstance(contents, dict):
        reject("pack_schema_invalid", "contents", manifest_path, 1, "contents must be a mapping")
        contents = {}
    for section, names in contents.items():
        if section == "primitives":
            reject("pack_defines_primitive", section, manifest_path, 1,
                   "the six FactType primitives are registered in code")
            continue
        if section not in sections or not isinstance(names, list) or any(not isinstance(n, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", n) for n in names):
            reject("pack_schema_invalid", section, manifest_path, 1, "declare supported content sections and lowercase file stems")
            continue
        for name in names:
            relative = f"{section}/{name}.yaml"
            declared.add(relative)
            for target, spec in read(directory / relative, section).items():
                if target in sections[section]:
                    reject("pack_entry_duplicate", target, directory / relative, 1, "entry IDs must be unique")
                sections[section][target] = spec
                if section == "pool_defs":
                    try:
                        _validate_pool_definition(target, spec)
                    except PoolError as error:
                        file, line = locations[section, target]
                        reject(str(error), target, file, line, "declare a valid fixed-point pool definition")
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.relative_to(directory).as_posix() not in declared:
            reject("pack_content_undeclared", path.name, path, 1, "list every content file in pack.yaml")

    # Shape checks protect the compiler from untrusted YAML structures.
    for section, entries in sections.items():
        for target, spec in entries.items():
            file, line = locations[section, target]
            valid = isinstance(spec, dict)
            if valid and section == "entity_types":
                slots = spec.get("slots")
                if not isinstance(slots, list):
                    reject("pack_entity_slots_invalid", target, file, line, "declare a list of FactType slots")
                    continue
                seen_patterns = set()
                for slot in slots:
                    if (not isinstance(slot, dict) or slot.keys() != {"fact_type_pattern"}
                            or not isinstance(slot["fact_type_pattern"], str) or not slot["fact_type_pattern"]):
                        reject("pack_entity_slot_invalid", target, file, line, "each slot declares one FactType pattern")
                        continue
                    pattern = slot["fact_type_pattern"]
                    if pattern in seen_patterns:
                        reject("pack_entity_slot_duplicate", target, file, line, "list each FactType pattern once")
                    seen_patterns.add(pattern)
            if valid and section == "fact_types":
                primitive = spec.get("primitive")
                if primitive is not None and (
                    not isinstance(primitive, str) or primitive not in _FACT_TYPE_PRIMITIVES
                ):
                    reject("primitive_unknown", target, file, line,
                           "reference one of the six code-registered FactType primitives")
                    continue
                valid = (
                    isinstance(spec.get("owner_ref"), str)
                    and (primitive is None or primitive in ("machine", "pool"))
                    and ("visibility" not in spec or isinstance(spec["visibility"], dict))
                    and (
                        primitive is None
                        or (
                            isinstance(spec.get("state_set_ref"), str)
                            if primitive == "machine"
                            else "state_set_ref" not in spec
                        )
                    )
                )
            if valid and section == "machine_defs":
                valid = (isinstance(spec.get("states"), list) and all(isinstance(s, str) for s in spec["states"])
                    and isinstance(spec.get("terminal_states"), list) and all(isinstance(s, str) for s in spec["terminal_states"])
                    and isinstance(spec.get("transitions"), list) and all(isinstance(e, list) and len(e) == 2 and all(isinstance(s, str) for s in e) for e in spec["transitions"]))
            if valid and section == "models":
                valid = (isinstance(spec.get("implementation"), str) and spec["implementation"] in ("code", "data")
                    and all(isinstance(spec.get(key), str) and spec[key] for key in ("input_schema", "output_schema"))
                    and (spec["implementation"] != "data" or isinstance(spec.get("evaluator_ref"), str) and bool(spec["evaluator_ref"]))
                    and isinstance(spec.get("owner_ref"), str) and isinstance(spec.get("determinism_policy"), dict)
                    and all(isinstance(spec.get(key), list) and all(isinstance(s, str) for s in spec[key]) for key in ("reads", "writes_fact_types"))
                    and isinstance(spec.get("params", {}), dict) and isinstance(spec.get("layers", []), list)
                    and all(isinstance(layer, dict) and isinstance(layer.get("owner_ref"), str)
                        and isinstance(layer.get("writes_fact_types"), list) and all(isinstance(s, str) for s in layer["writes_fact_types"]) for layer in spec.get("layers", [])))
            if not valid:
                reject("pack_schema_invalid", target, file, line, "entry has the wrong field types")
    order = manifest.get("resolve_order")
    if order is not None and (not isinstance(order, dict)
            or not isinstance(order.get("unrelated", []), list) or any(not isinstance(s, str) for s in order.get("unrelated", []))
            or not isinstance(order.get("before", []), list) or any(not isinstance(e, list) or len(e) != 2 or any(not isinstance(s, str) for s in e) for e in order.get("before", []))):
        reject("pack_schema_invalid", "resolve_order", manifest_path, 1, "declare lists of fact IDs and edge pairs")
    if parent is None or "owners" in manifest:
        owners = manifest.get("owners")
        if not isinstance(owners, list) or any(not isinstance(o, str) for o in owners):
            reject("pack_schema_invalid", "owners", manifest_path, 1, "declare owner identifiers")
        elif any(owner not in REGISTERED_OWNER_IDS for owner in owners):
            reject("facttype_owner_unknown", "owners", manifest_path, 1, "reference a code-registered Owner ID; packs cannot create owners")
    _reject_issues(issues)
    revision = PackRevision(
        manifest["pack_id"], manifest["pack_version"],
        sha256(json.dumps(raw_files, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    )
    return _PackSource(manifest_path, manifest, sections, locations, revision)


def _visibility_is_preserved(older: Any, newer: Any) -> bool:
    if older == newer:
        return True
    if not isinstance(older, dict) or not isinstance(newer, dict):
        return False
    if {k: v for k, v in older.items() if k != "learnable_by"} != {
        k: v for k, v in newer.items() if k != "learnable_by"
    }:
        return False
    before, after = older.get("learnable_by"), newer.get("learnable_by")
    if (not isinstance(before, list) or not isinstance(after, list) or not after
            or any(not isinstance(selector, str) for selector in before + after)):
        return False
    if newer.get("class") == "public" and "world" not in after:
        return False
    return set(after) <= set(before)


def load_pack(
    directory: Path, *, handlers: Mapping[str, Callable], running: bool = False,
    parent_packs: Mapping[tuple[str, str], Path] | None = None,
    expected_content_hash: str | None = None,
    owner_domains: Mapping[str, str] | None = None,
    command_fact_outputs: Mapping[str, set[str] | frozenset[str]] | None = None,
) -> LoadedPack:
    leaf = _read_pack(directory, running=running)
    manifest_path = leaf.manifest_path
    issues: list[Violation] = []

    def reject(code, target, file, line, hint):
        issues.append(Violation(code, target, str(file), line, hint))

    chain = [leaf]
    seen = {(leaf.revision.pack_id, leaf.revision.pack_version)}
    while (reference := chain[-1].manifest.get("parent_pack")) is not None:
        identity = reference["pack_id"], reference["pack_version"]
        child = chain[-1].manifest_path
        if identity in seen:
            reject("pack_cycle_in_parents", "parent_pack", child, 1, "parent package pins must be acyclic")
            _reject_issues(issues)
        parent_path = parent_packs.get(identity) if parent_packs is not None else None
        if parent_path is None:
            reject("pack_parent_unknown", "parent_pack", child, 1, "register the pinned parent package source")
            _reject_issues(issues)
        parent = _read_pack(parent_path)
        if (parent.revision.pack_id, parent.revision.pack_version) != identity:
            reject("pack_parent_identity_mismatch", "parent_pack", child, 1, "parent manifest must match the pinned identity")
            _reject_issues(issues)
        chain.append(parent)
        seen.add(identity)
    chain.reverse()

    manifest = {}
    sections = {name: {} for name in leaf.sections}
    locations = {}
    for source in chain:
        manifest.update(source.manifest)
        for target, spec in source.sections["fact_types"].items():
            previous = sections["fact_types"].get(target)
            if previous is None:
                continue
            file, line = source.locations["fact_types", target]
            if not _visibility_is_preserved(previous.get("visibility"), spec.get("visibility")):
                reject("pack_overrides_visibility_requirement", target, file, line, "preserve visibility or narrow its learner set")
            if any(previous.get(key) != spec.get(key) for key in ("owner_ref", "primitive", "identity")):
                reject("pack_overrides_fact_authority", target, file, line, "preserve the inherited FactType authority and primitive")
            if previous.get("unknown_policy") != spec.get("unknown_policy"):
                reject("pack_overrides_unknown_policy", target, file, line, "preserve the inherited unknown policy")
        for target, spec in source.sections["command_catalog"].items():
            previous = sections["command_catalog"].get(target)
            if previous is None:
                continue
            file, line = source.locations["command_catalog", target]
            if (previous.get("handled_by") != spec.get("handled_by")
                    or (previous.get("requires_authority") is True and spec.get("requires_authority") is False)):
                reject("pack_overrides_command_authority", target, file, line, "preserve inherited command authority")
        for section, entries in source.sections.items():
            sections[section].update(entries)
        locations.update(source.locations)

    for target, spec in sections["entity_types"].items():
        file, line = locations["entity_types", target]
        for slot in spec["slots"]:
            if slot["fact_type_pattern"] not in sections["fact_types"]:
                reject("pack_entity_slot_fact_unknown", target, file, line, "reference a declared FactType pattern")

    order = manifest.get("resolve_order")
    owners = manifest["owners"]
    registered_domains = {
        owner: domain for owner, domain in (owner_domains or {}).items()
        if owner in REGISTERED_OWNER_IDS and owner != "Credential"
    }
    for target, spec in sections["command_catalog"].items():
        file, line = locations["command_catalog", target]
        for code, hint in _command_violations(target, spec, registered_domains, owners):
            reject(code, target, file, line, hint)
    revisions = tuple(source.revision for source in chain)
    content_hash = leaf.revision.content_hash
    if len(revisions) > 1:
        pins = [(pin.pack_id, pin.pack_version, pin.content_hash) for pin in revisions]
        content_hash = sha256(json.dumps(pins, separators=(",", ":")).encode()).hexdigest()
    if expected_content_hash is not None and content_hash != expected_content_hash:
        reject("pack_content_hash_mismatch", "content_hash", manifest_path, 1, "resolved contents differ from the saved package pin")
    registry = None
    if not issues:
        try:
            registry = FactTypeRegistry.compile(facts=sections["fact_types"], models=sections["models"],
                machines=sections["machine_defs"], owners=owners, resolve_order=order, handlers=handlers,
                pool_defs=sections["pool_defs"],
                locations={target: location for (section, target), location in locations.items()
                           if section in ("manifest", "fact_types", "machine_defs", "models")})
        except RegistrationRejected as error:
            issues.extend(error.violations)
    pipelines = {}
    workflows = {}
    reactions = {}
    play_patterns = {}
    if registry is not None:
        valid_profiles = {}
        for target, spec in sections["impact_profiles"].items():
            file, line = locations["impact_profiles", target]
            violations = tuple(_impact_violations(
                spec, registry=registry, entity_types=sections["entity_types"], fact_specs=sections["fact_types"],
            ))
            for code, hint in violations:
                reject(code, target, file, line, hint)
            if not violations:
                valid_profiles[target] = spec
        if len(valid_profiles) == len(sections["impact_profiles"]):
            for target, spec in sections["pipelines"].items():
                file, line = locations["pipelines", target]
                try:
                    pipelines[target] = compile_pipeline(
                        target, spec, impact_profiles=valid_profiles, fact_specs=sections["fact_types"],
                    )
                except ValueError as error:
                    reject(str(error), target, file, line, "declare ordered pipeline steps and valid settlement mode")
        for target, spec in sections["workflows"].items():
            file, line = locations["workflows", target]
            if spec.get("workflow_id", target) != target:
                reject("workflow_schema_invalid", target, file, line, "match workflow_id to the declared entry")
                continue
            try:
                workflows[target] = compile_workflow(
                    {"workflow_id": target, **spec}, command_types=sections["command_catalog"].keys(),
                )
            except ValueError as error:
                reject(str(error), target, file, line, "declare ordered dependencies and registered commands")
        for section, validate in (("aggregation_models", _aggregation_violations), ("bindings", _binding_violations)):
            for target, spec in sections[section].items():
                file, line = locations[section, target]
                for code, hint in validate(spec, registry):
                    reject(code, target, file, line, hint)
        if not issues and sections["reactions"]:
            declarations = []
            for target, spec in sections["reactions"].items():
                if spec.get("reaction_id", target) != target:
                    file, line = locations["reactions", target]
                    reject("reaction_schema_invalid", target, file, line, "match reaction_id to the declared entry")
                declarations.append({"reaction_id": target, **spec})
            if not issues:
                trusted_outputs = {
                    command: facts for command, facts in (command_fact_outputs or {}).items()
                    if command in sections["command_catalog"]
                }
                try:
                    reactions = {
                        reaction.reaction_id: reaction for reaction in
                        compile_reactions(declarations, command_fact_outputs=trusted_outputs)
                    }
                except ReactionRejected as error:
                    reject(error.code, error.field, manifest_path, 1, "check the reaction graph and command outputs")
        if not issues and sections["play_patterns"]:
            pack_pins = {f"{revision.pack_id}@{revision.pack_version}" for revision in revisions}
            for target, spec in sections["play_patterns"].items():
                file, line = locations["play_patterns", target]
                if spec.get("play_pattern_id", target) != target:
                    reject("pattern_schema_invalid", target, file, line, "match play_pattern_id to the declared entry")
                    continue
                try:
                    play_patterns[target] = compile_play_pattern(
                        {"play_pattern_id": target, **spec}, reaction_ids=reactions.keys(),
                        pipeline_ids=pipelines.keys(), workflow_ids=workflows.keys(), pack_pins=pack_pins,
                    )
                except PlayPatternRejected as error:
                    reject(error.code, target, file, line, f"check the play pattern's {error.field} declaration")
    _reject_issues(issues)
    assert registry is not None
    return LoadedPack(
        manifest["pack_id"], manifest["pack_version"], content_hash, registry,
        freeze(manifest.get("legacy_rule", {})), freeze(sections["pool_defs"]),
        freeze(sections["entity_types"]), freeze(sections["impact_profiles"]),
        freeze(sections["aggregation_models"]), freeze(sections["bindings"]), revisions,
        freeze(sections["command_catalog"]), MappingProxyType(pipelines), MappingProxyType(workflows),
        MappingProxyType(reactions), MappingProxyType(play_patterns),
    )
