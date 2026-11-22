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
from app.gameplay.pool_runtime import PoolDefinition, PoolError, PoolThreshold


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
    if len(layers) > 1 and (len(hosts) > 1 or "either" in hosts) and atomicity != "obligation":
        yield "impact_atomic_cross_host", "use obligation unless all layers are pinned to the same host"


def load_pack(directory: Path, *, handlers: Mapping[str, Callable], running: bool = False) -> LoadedPack:
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
    if running:
        reject("pack_runtime_reload_forbidden", "pack", manifest_path, 1, "load only before runtime starts")
    if manifest.get("parent_pack") is not None:
        reject("pack_parent_unsupported", "parent_pack", manifest_path, 1, "this reference slice requires a self-contained pack")
    for key in ("pack_id", "pack_version"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            reject("pack_schema_invalid", key, manifest_path, 1, "declare nonempty pack identity and version")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        reject("pack_schema_invalid", "schema_version", manifest_path, 1, "supported pack schema is 1")
    contents = manifest.get("contents", {})
    sections = {name: {} for name in ("fact_types", "machine_defs", "models", "pool_defs", "entity_types", "impact_profiles")}
    declared = {"pack.yaml"}
    if not isinstance(contents, dict):
        reject("pack_schema_invalid", "contents", manifest_path, 1, "contents must be a mapping")
        contents = {}
    for section, names in contents.items():
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
                    if pattern not in sections["fact_types"]:
                        reject("pack_entity_slot_fact_unknown", target, file, line, "reference a declared FactType pattern")
                    if pattern in seen_patterns:
                        reject("pack_entity_slot_duplicate", target, file, line, "list each FactType pattern once")
                    seen_patterns.add(pattern)
            if valid and section == "fact_types":
                valid = (isinstance(spec.get("owner_ref"), str) and isinstance(spec.get("state_set_ref"), str)
                    and ("visibility" not in spec or isinstance(spec["visibility"], dict)))
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
    owners = manifest.get("owners")
    if not isinstance(owners, list) or any(not isinstance(o, str) for o in owners):
        reject("pack_schema_invalid", "owners", manifest_path, 1, "declare owner identifiers")
    elif any(owner not in REGISTERED_OWNER_IDS for owner in owners):
        reject("facttype_owner_unknown", "owners", manifest_path, 1, "reference a code-registered Owner ID; packs cannot create owners")
    registry = None
    if not issues:
        try:
            registry = FactTypeRegistry.compile(facts=sections["fact_types"], models=sections["models"],
                machines=sections["machine_defs"], owners=owners, resolve_order=order, handlers=handlers,
                locations={target: location for (section, target), location in locations.items()
                           if section in ("fact_types", "machine_defs", "models")})
        except RegistrationRejected as error:
            issues.extend(error.violations)
    if registry is not None:
        for target, spec in sections["impact_profiles"].items():
            file, line = locations["impact_profiles", target]
            for code, hint in _impact_violations(
                spec, registry=registry, entity_types=sections["entity_types"], fact_specs=sections["fact_types"],
            ):
                reject(code, target, file, line, hint)
    if issues:
        unique = {(v.code, v.target, v.file, v.line): v for v in issues}
        raise RegistrationRejected(sorted(unique.values(), key=lambda v: (v.file, v.line, v.code, v.target)))
    assert registry is not None
    content_hash = sha256(json.dumps(raw_files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return LoadedPack(
        manifest["pack_id"], manifest["pack_version"], content_hash, registry,
        freeze(manifest.get("legacy_rule", {})), freeze(sections["pool_defs"]),
        freeze(sections["entity_types"]), freeze(sections["impact_profiles"]),
    )
