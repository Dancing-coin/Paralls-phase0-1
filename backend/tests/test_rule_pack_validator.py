from pathlib import Path
import shutil
from textwrap import dedent

import pytest

from app.gameplay.fact_type_registry import REGISTERED_OWNER_IDS, RegistrationRejected
from app.gameplay.fact_type_registry import REGISTERED_FACT_TYPE_PRIMITIVES
from app.gameplay.rule_pack_validator import load_pack

PACK = Path(__file__).resolve().parents[2] / "packs/credential_reference"


def declared_kind_condition(inputs, params):
    return inputs["command@1"]["credential_kind"] in params["credential_kinds"]


HANDLERS = {"credential_command@1": declared_kind_condition}
FACILITY_PACK = Path(__file__).resolve().parents[2] / "packs/county_siege_facility"


def test_registered_owner_ids_match_v2_short_names_and_legacy_credential():
    assert len(REGISTERED_OWNER_IDS) == 23
    assert "Credential" in REGISTERED_OWNER_IDS
    assert "Combat" not in REGISTERED_OWNER_IDS
    assert "Economy / Market" not in REGISTERED_OWNER_IDS


def test_fact_type_primitive_registry_has_exactly_six_code_registered_values():
    assert REGISTERED_FACT_TYPE_PRIMITIVES == {
        "pool", "machine", "holdings", "bond", "process", "place",
    }


def test_pack_load_is_repeatable_and_evaluates_registered_code():
    first = load_pack(PACK, handlers=HANDLERS)
    assert first.content_hash == load_pack(PACK, handlers=HANDLERS).content_hash
    assert first.registry.evaluate("credential_command@1", {"command@1": {"credential_kind": "deed"}})
    assert not first.registry.evaluate("credential_command@1", {"command@1": {"credential_kind": "unknown"}})
    assert first.legacy_rule["condition_revision"] == 1
    assert first.registry.facts["fact:credential:*:link"].resolution_order == 10


def test_pack_rejects_singleton_identity_with_non_global_scope(tmp_path):
    destination = shutil.copytree(PACK, tmp_path / "identity-scope-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(fact_type.replace('identity: "entity_ref"', 'identity: "singleton"', 1), encoding="utf-8")

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations
                if violation.code == "facttype_identity_scope_mismatch"]
    assert [violation.target for violation in matching] == ["fact:credential:*:link"]


def test_pack_rejects_entity_identity_with_global_scope(tmp_path):
    destination = shutil.copytree(PACK, tmp_path / "global-entity-scope-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(fact_type.replace('"fact:credential:*:link"', '"fact:credential:global:link"', 1), encoding="utf-8")

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations
                if violation.code == "facttype_identity_scope_mismatch"]
    assert [violation.target for violation in matching] == ["fact:credential:global:link"]


def test_pack_accepts_singleton_identity_with_global_scope(tmp_path):
    destination = shutil.copytree(PACK, tmp_path / "singleton-global-scope-pack")
    for path in destination.rglob("*.yaml"):
        contents = path.read_text(encoding="utf-8")
        contents = contents.replace("fact:credential:*:link", "fact:credential:global:link")
        contents = contents.replace('identity: "entity_ref"', 'identity: "singleton"')
        path.write_text(contents, encoding="utf-8")

    loaded = load_pack(destination, handlers=HANDLERS)

    assert loaded.registry.facts["fact:credential:global:link"].fact_type_id == "fact:credential:global:link"


@pytest.mark.parametrize(("identity_line", "replacement", "code"), [
    pytest.param('  identity: "entity_ref"\n', "", "facttype_identity_missing", id="missing"),
    pytest.param('  identity: "entity_ref"\n', '  identity: "unsupported"\n',
                 "facttype_identity_invalid", id="unknown"),
])
def test_pack_rejects_missing_or_unknown_fact_type_identity(tmp_path, identity_line, replacement, code):
    destination = shutil.copytree(PACK, tmp_path / "invalid-identity-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    assert identity_line in fact_type
    fact_type_path.write_text(fact_type.replace(identity_line, replacement, 1), encoding="utf-8")

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations if violation.code == code]
    assert [violation.target for violation in matching] == ["fact:credential:*:link"]


@pytest.mark.parametrize("identity", ["collection_ref", "region_ref"])
def test_pack_accepts_non_singleton_fact_type_identities(tmp_path, identity):
    destination = shutil.copytree(PACK, tmp_path / f"{identity}-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(fact_type.replace('identity: "entity_ref"', f'identity: "{identity}"', 1), encoding="utf-8")

    loaded = load_pack(destination, handlers=HANDLERS)

    assert loaded.registry.facts["fact:credential:*:link"].fact_type_id == "fact:credential:*:link"


def test_credential_fact_is_owned_by_ownership_without_writing_title_facts():
    loaded = load_pack(PACK, handlers=HANDLERS)

    fact = loaded.registry.facts["fact:credential:*:link"]
    model = loaded.registry.models["credential_command@1"]

    assert fact.owner_ref == "Ownership"
    assert model.owner_ref == "Ownership"
    assert model.writes_fact_types == ("fact:credential:*:link",)


def test_compiled_fact_retains_registered_event_schema_reference():
    loaded = load_pack(PACK, handlers=HANDLERS)

    assert loaded.registry.facts["fact:credential:*:link"].event_schema_ref == "credential_link_legacy_v1"


def test_compiled_fact_retains_declared_identity():
    loaded = load_pack(PACK, handlers=HANDLERS)

    assert loaded.registry.facts["fact:credential:*:link"].identity == "entity_ref"


def test_compiled_registry_indexes_facts_by_event_schema_reference():
    loaded = load_pack(PACK, handlers=HANDLERS)

    indexed = loaded.registry.facts_by_event_schema_ref["credential_link_legacy_v1"]

    assert tuple(fact.fact_type_id for fact in indexed) == ("fact:credential:*:link",)


def test_compiled_registry_resolves_event_type_to_all_exact_fact_type_candidates():
    loaded = load_pack(FACILITY_PACK, handlers={})

    candidates = loaded.registry.fact_types_for_event("gameplay.pool.adjusted", 1)

    assert tuple(fact.fact_type_id for fact in candidates) == (
        "fact:facility:gate-03:durability",
        "fact:facility:gate-03:integrity",
        "fact:facility:gate-03:latch-durability",
    )
    assert loaded.registry.fact_types_for_event("gameplay.pool.adjusted", 2) == ()


def test_compiled_registry_resolves_legacy_credential_schema_alias():
    loaded = load_pack(PACK, handlers=HANDLERS)

    candidates = loaded.registry.fact_types_for_event("gameplay.credential.issued", 1)

    assert tuple(fact.fact_type_id for fact in candidates) == ("fact:credential:*:link",)


def test_compiled_registry_resolves_event_instance_from_fact_type_stream():
    loaded = load_pack(FACILITY_PACK, handlers={})

    resolved = loaded.registry.resolve_event_fact_type(
        event_type="gameplay.pool.adjusted",
        schema_version=1,
        stream_id="fact:facility:gate-03:integrity",
        payload={"fact_type": "fact:facility:gate-03:integrity"},
    )

    assert resolved.fact_type.fact_type_id == "fact:facility:gate-03:integrity"
    assert resolved.fact_type_ref == "fact:facility:gate-03:integrity"


def test_compiled_registry_resolves_template_fact_type_scope_from_stream():
    loaded = load_pack(PACK, handlers=HANDLERS)

    resolved = loaded.registry.resolve_event_fact_type(
        event_type="gameplay.credential.issued",
        schema_version=1,
        stream_id="fact:credential:credential-17:link",
        payload={},
    )

    assert resolved.fact_type.fact_type_id == "fact:credential:*:link"
    assert resolved.fact_type_ref == "fact:credential:credential-17:link"


def test_compiled_registry_rejects_fact_type_payload_conflicting_with_stream():
    loaded = load_pack(FACILITY_PACK, handlers={})

    resolved = loaded.registry.resolve_event_fact_type(
        event_type="gameplay.pool.adjusted",
        schema_version=1,
        stream_id="fact:facility:gate-03:integrity",
        payload={"fact_type": "fact:facility:gate-03:durability"},
    )

    assert resolved is None


def test_compiled_registry_does_not_infer_fact_type_from_legacy_domain_stream():
    loaded = load_pack(FACILITY_PACK, handlers={})

    resolved = loaded.registry.resolve_event_fact_type(
        event_type="gameplay.pool.adjusted",
        schema_version=1,
        stream_id="gameplay:facility:gate-03",
        payload={"fact_type": "fact:facility:gate-03:integrity"},
    )

    assert resolved is None


def test_facility_gate_pack_registers_pool_and_machine_fact_types():
    loaded = load_pack(FACILITY_PACK, handlers={})

    assert loaded.registry.facts["fact:facility:gate-03:durability"].primitive == "pool"
    assert loaded.registry.facts["fact:facility:gate-03:latch-durability"].primitive == "pool"
    assert loaded.registry.facts["fact:facility:gate-03:integrity"].primitive == "pool"
    assert loaded.registry.facts["fact:facility:gate-03:latch"].primitive == "machine"
    assert loaded.pool_defs["fact:facility:gate-03:integrity"]["initial"] == "100"


def test_pack_rejects_fact_type_with_unregistered_event_schema_ref(tmp_path):
    destination = shutil.copytree(PACK, tmp_path / "unknown-event-schema-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(
        fact_type.replace('event_schema_ref: "credential_link_legacy_v1"',
                          'event_schema_ref: "unregistered_schema@v9"', 1),
        encoding="utf-8",
    )

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations
                if violation.code == "facttype_schema_unknown"]
    assert len(matching) == 1
    assert matching[0].target == "fact:credential:*:link"


def test_pack_rejects_distribution_fact_without_refold_model(tmp_path):
    destination = shutil.copytree(FACILITY_PACK, tmp_path / "facility-pack")
    fact_type_path = destination / "fact_types/gate_integrity.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(
        fact_type.replace('primitive: "pool"\n', 'primitive: "pool"\n  aggregation: "distribution"\n', 1),
        encoding="utf-8",
    )

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers={})

    matching = [violation for violation in error.value.violations
                if violation.code == "facttype_refold_missing"]
    assert len(matching) == 1
    assert matching[0].target == "fact:facility:gate-03:integrity"


@pytest.mark.parametrize("fact_type_id", ["fact:credential:link", "fact:credential::link"])
def test_pack_rejects_fact_type_without_scope_using_scope_diagnostic(tmp_path, fact_type_id):
    destination = shutil.copytree(PACK, tmp_path / "scope-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(
        fact_type.replace("fact:credential:*:link", fact_type_id, 1),
        encoding="utf-8",
    )

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations
                if violation.code == "facttype_scope_missing"]
    assert [violation.target for violation in matching] == [fact_type_id]


@pytest.mark.parametrize("fact_type_id", [
    "fact:cred-ential:*:link",
    "fact:c:*:link",
    "fact:credential:*:l",
    "fact:credential:*:Link",
    "fact:credential:*:link!",
    f"fact:credential:{'x' * 108}:link",
])
def test_pack_rejects_fact_type_with_invalid_domain_or_name(tmp_path, fact_type_id):
    destination = shutil.copytree(PACK, tmp_path / "invalid-name-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(
        fact_type.replace("fact:credential:*:link", fact_type_id, 1),
        encoding="utf-8",
    )

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations
                if violation.code == "facttype_naming_invalid"]
    assert [violation.target for violation in matching] == [fact_type_id]


def test_pack_rejects_process_kind_on_non_process_fact_type(tmp_path):
    destination = shutil.copytree(FACILITY_PACK, tmp_path / "process-kind-pack")
    fact_type_path = destination / "fact_types/gate_latch.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(
        fact_type.replace('  primitive: "machine"\n',
                          '  primitive: "machine"\n  process_kind: "temporal"\n', 1),
        encoding="utf-8",
    )

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers={})

    matching = [violation for violation in error.value.violations
                if violation.code == "facttype_process_kind_invalid"]
    assert [violation.target for violation in matching] == ["fact:facility:gate-03:latch"]


@pytest.mark.parametrize(("field", "value", "primitive"), [
    pytest.param("aggregation", '"sum"', "machine", id="aggregation"),
    pytest.param("refold_model_ref", '"resolver@1"', "machine", id="refold-model"),
    pytest.param("bond_types", '["title"]', "machine", id="bond-types"),
    pytest.param("place_kind", '"location"', "machine", id="place-kind"),
])
def test_pack_rejects_primitive_incompatible_fact_type_fields(
    tmp_path, field, value, primitive,
):
    destination = shutil.copytree(PACK, tmp_path / f"machine-{field}-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(fact_type.replace(
        '  primitive: "machine"\n', f'  primitive: "{primitive}"\n  {field}: {value}\n', 1,
    ), encoding="utf-8")

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations
                if violation.code == "facttype_field_primitive_invalid"]
    assert [violation.target for violation in matching] == ["fact:credential:*:link"]


def test_pack_rejects_fact_type_without_primitive_using_missing_diagnostic(tmp_path):
    destination = shutil.copytree(PACK, tmp_path / "primitive-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    assert '  primitive: "machine"\n' in fact_type
    fact_type_path.write_text(fact_type.replace('  primitive: "machine"\n', "", 1), encoding="utf-8")

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations
                if violation.code == "primitive_missing"]
    assert [violation.target for violation in matching] == ["fact:credential:*:link"]


@pytest.mark.parametrize("declaration_location", ["manifest", "contents"])
def test_pack_rejects_package_defined_primitives(tmp_path, declaration_location):
    destination = shutil.copytree(PACK, tmp_path / "custom-primitive-pack")
    manifest_path = destination / "pack.yaml"
    manifest = manifest_path.read_text(encoding="utf-8")
    if declaration_location == "manifest":
        manifest = manifest.replace("schema_version: 1\n", "schema_version: 1\nprimitives: [custom]\n", 1)
    else:
        manifest = manifest.replace("contents:\n", "contents:\n  primitives: [custom]\n", 1)
    manifest_path.write_text(manifest, encoding="utf-8")

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations
                if violation.code == "pack_defines_primitive"]
    assert [violation.target for violation in matching] == ["primitives"]


def test_pack_rejects_unknown_fact_primitive_with_dedicated_diagnostic(tmp_path):
    destination = shutil.copytree(PACK, tmp_path / "unknown-primitive-pack")
    fact_type_path = destination / "fact_types/credential_link.yaml"
    fact_type = fact_type_path.read_text(encoding="utf-8")
    fact_type_path.write_text(fact_type.replace('primitive: "machine"', 'primitive: "custom"', 1), encoding="utf-8")

    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    matching = [violation for violation in error.value.violations
                if violation.code == "primitive_unknown"]
    assert [violation.target for violation in matching] == ["fact:credential:*:link"]


_POOL_DECLARATION = dedent("""\
    stamina:
      description: "Stamina used during a movement window"
      decimals: 2
      bound_lower: "0"
      bound_upper: 100
      initial: "75.5"
      integration:
        mode: "rate"
        rate_per_tick: "-0.05"
      hysteresis:
        - state: "exhausted"
          enter_below: "20"
          exit_above: "30"
    """)


def _pack_with_pool(tmp_path, declaration):
    destination = shutil.copytree(PACK, tmp_path / "pool-pack")
    manifest = destination / "pack.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'contents:\n', 'contents:\n  pool_defs: ["stamina"]\n'
        ),
        encoding="utf-8",
    )
    pool_defs = destination / "pool_defs"
    pool_defs.mkdir()
    (pool_defs / "stamina.yaml").write_text(declaration, encoding="utf-8")
    return destination


def test_pack_loads_immutable_pool_definitions(tmp_path):
    destination = _pack_with_pool(tmp_path, _POOL_DECLARATION)
    loaded = load_pack(destination, handlers=HANDLERS)
    assert loaded.content_hash == load_pack(destination, handlers=HANDLERS).content_hash
    stamina = loaded.pool_defs["stamina"]
    assert stamina["decimals"] == 2
    assert stamina["integration"]["rate_per_tick"] == "-0.05"
    assert stamina["hysteresis"][0]["state"] == "exhausted"
    with pytest.raises(TypeError):
        stamina["initial"] = "0"
    assert not load_pack(PACK, handlers=HANDLERS).pool_defs


@pytest.mark.parametrize(("old", "new", "code"), [
    ("  decimals: 2\n", "", "pack_pool_scale_invalid"),
    ("decimals: 2", "decimals: true", "pack_pool_scale_invalid"),
    ('initial: "75.5"', 'initial: "75.501"', "pack_pool_scale_invalid"),
    ('initial: "75.5"', 'initial: "7e1"', "pack_pool_number_invalid"),
    ('initial: "75.5"', 'initial: "101"', "pool_initial_out_of_bounds"),
    ('bound_lower: "0"', 'bound_lower: "110"', "pool_bounds_invalid"),
    ('mode: "rate"', 'mode: "none"', "pack_pool_integration_invalid"),
    ('exit_above: "30"', 'exit_above: "20"', "pool_threshold_invalid"),
])
def test_pack_rejects_invalid_pool_definition(tmp_path, old, new, code):
    destination = _pack_with_pool(tmp_path, _POOL_DECLARATION.replace(old, new))
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    matching = [violation for violation in error.value.violations if violation.code == code]
    assert [(v.target, Path(v.file).name, v.line) for v in matching] == [("stamina", "stamina.yaml", 1)]


_ENTITY_TYPE_DECLARATION = dedent("""\
    deed:
      slots:
        - fact_type_pattern: "fact:credential:*:link"
    """)


def _pack_with_entity_type(tmp_path, declaration):
    destination = shutil.copytree(PACK, tmp_path / "entity-pack")
    manifest = destination / "pack.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'contents:\n', 'contents:\n  entity_types: ["deed"]\n'
        ),
        encoding="utf-8",
    )
    entity_types = destination / "entity_types"
    entity_types.mkdir()
    (entity_types / "deed.yaml").write_text(declaration, encoding="utf-8")
    return destination


def test_pack_loads_entity_type_slots_from_registered_facts(tmp_path):
    destination = _pack_with_entity_type(tmp_path, _ENTITY_TYPE_DECLARATION)
    loaded = load_pack(destination, handlers=HANDLERS)
    (slot,) = loaded.entity_types["deed"]["slots"]
    assert slot["fact_type_pattern"] in loaded.registry.facts
    with pytest.raises(TypeError):
        slot["fact_type_pattern"] = "fact:credential:*:missing"

    declaration = destination / "entity_types" / "deed.yaml"
    declaration.write_text(_ENTITY_TYPE_DECLARATION.replace("deed:", "record:"), encoding="utf-8")
    reloaded = load_pack(destination, handlers=HANDLERS)
    assert "record" in reloaded.entity_types
    assert loaded.content_hash != reloaded.content_hash
    assert not load_pack(PACK, handlers=HANDLERS).entity_types


@pytest.mark.parametrize(("declaration", "code"), [
    pytest.param("deed: {}", "pack_entity_slots_invalid", id="missing-slots"),
    pytest.param("deed: {slots: [{}]}", "pack_entity_slot_invalid", id="invalid-slot"),
    pytest.param(
        _ENTITY_TYPE_DECLARATION.replace(":link", ":missing"),
        "pack_entity_slot_fact_unknown", id="unknown-fact",
    ),
    pytest.param(
        _ENTITY_TYPE_DECLARATION + '    - fact_type_pattern: "fact:credential:*:link"\n',
        "pack_entity_slot_duplicate", id="duplicate-slot",
    ),
])
def test_pack_rejects_invalid_entity_type_slots(tmp_path, declaration, code):
    destination = _pack_with_entity_type(tmp_path, declaration)
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    matching = [violation for violation in error.value.violations if violation.code == code]
    assert [(v.target, Path(v.file).name, v.line) for v in matching] == [("deed", "deed.yaml", 1)]


_IMPACT_PROFILE_DECLARATION = dedent("""\
    "deed@1":
      target_entity_type: "deed"
      atomicity: "atomic"
      layers:
        - order: 10
          fact_type: "fact:credential:*:link"
          resolver: "credential_command@1"
    """)


def _pack_with_impact_profile(tmp_path, declaration):
    destination = _pack_with_entity_type(tmp_path, _ENTITY_TYPE_DECLARATION)
    manifest = destination / "pack.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'contents:\n', 'contents:\n  impact_profiles: ["deed"]\n'
        ),
        encoding="utf-8",
    )
    profile_directory = destination / "impact_profiles"
    profile_directory.mkdir()
    (profile_directory / "deed.yaml").write_text(declaration, encoding="utf-8")
    return destination


def test_pack_loads_impact_profile_for_registered_slots(tmp_path):
    destination = _pack_with_impact_profile(tmp_path, _IMPACT_PROFILE_DECLARATION)
    loaded = load_pack(destination, handlers=HANDLERS)
    profile = loaded.impact_profiles["deed@1"]
    assert profile["target_entity_type"] in loaded.entity_types
    assert profile["layers"][0]["resolver"] in loaded.registry.models
    with pytest.raises(TypeError):
        profile["layers"][0]["order"] = 20
    assert not load_pack(PACK, handlers=HANDLERS).impact_profiles


_PIPELINE_DECLARATION = dedent("""\
    deed_pipeline:
      profile_ref: "impact_profile/deed@1"
      atomic: true
      host_requirement: "single"
      steps:
        - fact_type_pattern: "fact:credential:*:link"
          resolver: "credential_command@1"
        - fact_type_pattern: "fact:credential:*:mark"
          resolver: "credential_command@1"
    """)


def _pack_with_pipeline(tmp_path, declaration, *, second_host="paralls", scopes=("*", "*")):
    profile = _IMPACT_PROFILE_DECLARATION.replace('"atomic"', '"obligation"') + (
        '    - order: 20\n'
        '      fact_type: "fact:credential:*:mark"\n'
        '      resolver: "credential_command@1"\n'
    )
    destination = _pack_with_impact_profile(tmp_path, profile)
    facts = destination / "fact_types" / "credential_link.yaml"
    original = facts.read_text(encoding="utf-8")
    facts.write_text(
        original + original.replace(":link", ":mark").replace('"paralls"', f'"{second_host}"'),
        encoding="utf-8",
    )
    manifest = destination / "pack.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        'before: []', 'before: [["fact:credential:*:link", "fact:credential:*:mark"]]'
    ).replace('contents:\n', 'contents:\n  pipelines: ["deed"]\n'), encoding="utf-8")
    entity = destination / "entity_types" / "deed.yaml"
    entity.write_text(
        _ENTITY_TYPE_DECLARATION + '    - fact_type_pattern: "fact:credential:*:mark"\n',
        encoding="utf-8",
    )
    model = destination / "models" / "credential_command.yaml"
    model.write_text(model.read_text(encoding="utf-8").replace(
        '["fact:credential:*:link"]', '["fact:credential:*:link", "fact:credential:*:mark"]'
    ), encoding="utf-8")
    (destination / "pipelines").mkdir()
    pipeline = destination / "pipelines" / "deed.yaml"
    pipeline.write_text(declaration, encoding="utf-8")
    if scopes != ("*", "*"):
        for path in (manifest, facts, entity, model, destination / "impact_profiles" / "deed.yaml", pipeline):
            path.write_text(path.read_text(encoding="utf-8").replace(
                "fact:credential:*:link", f"fact:credential:{scopes[0]}:link",
            ).replace("fact:credential:*:mark", f"fact:credential:{scopes[1]}:mark"), encoding="utf-8")
    return destination


def test_pack_loads_ordered_atomic_pipeline_with_one_revision_vector(tmp_path):
    pack = load_pack(_pack_with_pipeline(tmp_path, _PIPELINE_DECLARATION), handlers=HANDLERS)
    pipeline = pack.pipelines["deed_pipeline"]
    assert pipeline.atomic
    assert pipeline.profile_ref == "impact_profile/deed@1"
    assert tuple(step.fact_type_pattern for step in pipeline.steps) == (
        "fact:credential:*:link", "fact:credential:*:mark",
    )
    revision_vector = {"stream:link": 3, "stream:mark": 2}
    bound = pipeline.bind_inputs(
        scopes=("deed:1", "deed:1"),
        revision_vectors=(revision_vector, {"stream:mark": 2, "stream:link": 3}),
    )
    revision_vector["stream:link"] = 4
    assert bound == {"stream:link": 3, "stream:mark": 2}
    with pytest.raises(TypeError):
        bound["stream:link"] = 4


@pytest.mark.parametrize(("scopes", "second", "code"), [
    pytest.param(("deed:1", "deed:2"), {"stream:link": 3}, "pipeline_cross_scope_atomic", id="cross-scope"),
    pytest.param(("deed:1", "deed:1"), {"stream:link": 4}, "pipeline_revision_vector_mismatch", id="stale-vector"),
    pytest.param(("deed:1", "deed:1"), {}, "pipeline_revision_vector_mismatch", id="missing-stream"),
])
def test_pipeline_rejects_cross_scope_batch_and_mismatched_vectors(tmp_path, scopes, second, code):
    pack = load_pack(_pack_with_pipeline(tmp_path, _PIPELINE_DECLARATION), handlers=HANDLERS)
    with pytest.raises(ValueError, match=code):
        pack.pipelines["deed_pipeline"].bind_inputs(
            scopes=scopes, revision_vectors=({"stream:link": 3}, second),
        )


def test_pack_rejects_atomic_pipeline_across_hosts(tmp_path):
    destination = _pack_with_pipeline(tmp_path, _PIPELINE_DECLARATION, second_host="ue")
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    assert [v.code for v in error.value.violations] == ["impact_atomic_cross_host"]


def test_pack_rejects_atomic_pipeline_with_distinct_declared_scopes(tmp_path):
    destination = _pack_with_pipeline(tmp_path, _PIPELINE_DECLARATION, scopes=("alpha", "beta"))
    with pytest.raises(RegistrationRejected, match="pipeline_cross_scope_atomic"):
        load_pack(destination, handlers=HANDLERS)


def test_pack_requires_recovery_for_obligation_pipeline_across_hosts(tmp_path):
    obligation = _PIPELINE_DECLARATION.replace('atomic: true\n  host_requirement: "single"', 'atomic: false')
    destination = _pack_with_pipeline(tmp_path, obligation, second_host="ue")
    with pytest.raises(RegistrationRejected, match="pipeline_recovery_action_invalid"):
        load_pack(destination, handlers=HANDLERS)
    (destination / "pipelines" / "deed.yaml").write_text(
        obligation.replace("  steps:", '  recovery_action: "reconcile"\n  steps:'), encoding="utf-8",
    )
    pipeline = load_pack(destination, handlers=HANDLERS).pipelines["deed_pipeline"]
    assert pipeline.atomic is False
    assert pipeline.recovery_action == "reconcile"
    inputs = {"stream:link": 3}
    assert pipeline.bind_inputs(scopes=("deed:1", "deed:2"), revision_vectors=(inputs, inputs)) == inputs


def test_pack_rejects_pipeline_steps_that_differ_from_impact_profile(tmp_path):
    declaration = _PIPELINE_DECLARATION.replace(
        'fact_type_pattern: "fact:credential:*:mark"', 'fact_type_pattern: "fact:credential:*:link"',
    )
    destination = _pack_with_pipeline(tmp_path, declaration)
    with pytest.raises(RegistrationRejected, match="pipeline_profile_steps_mismatch"):
        load_pack(destination, handlers=HANDLERS)


@pytest.mark.parametrize(("old", "new", "code"), [
    pytest.param(
        'target_entity_type: "deed"', 'target_entity_type: "record"',
        "impact_target_entity_unknown", id="unknown-entity",
    ),
    pytest.param(
        'fact:credential:*:link', 'fact:credential:*:missing',
        "impact_layer_facttype_unknown", id="unknown-fact",
    ),
    pytest.param(
        'resolver: "credential_command@1"', 'resolver: "missing@1"',
        "impact_layer_resolver_unknown", id="unknown-resolver",
    ),
    pytest.param(
        'atomicity: "atomic"', 'atomicity: "other"',
        "impact_atomicity_invalid", id="invalid-atomicity",
    ),
    pytest.param(
        'resolver: "credential_command@1"',
        'resolver: "credential_command@1"\n      owner_ref: "Credential"',
        "impact_layer_owner_mismatch", id="owner-override",
    ),
])
def test_pack_rejects_invalid_impact_profile(tmp_path, old, new, code):
    declaration = _IMPACT_PROFILE_DECLARATION.replace(old, new)
    destination = _pack_with_impact_profile(tmp_path, declaration)
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    matching = [violation for violation in error.value.violations if violation.code == code]
    assert [(v.target, Path(v.file).parent.name, v.line) for v in matching] == [
        ("deed@1", "impact_profiles", 1)
    ]


def test_pack_requires_obligation_when_impact_layers_cross_hosts(tmp_path):
    destination = _pack_with_impact_profile(tmp_path, _IMPACT_PROFILE_DECLARATION)
    fact_types = destination / "fact_types" / "credential_link.yaml"
    facts = fact_types.read_text(encoding="utf-8")
    fact_types.write_text(
        facts + facts.replace(":link", ":mark").replace('"paralls"', '"ue"'),
        encoding="utf-8",
    )
    manifest = destination / "pack.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'before: []', 'before: [["fact:credential:*:link", "fact:credential:*:mark"]]'
        ),
        encoding="utf-8",
    )
    entity_file = destination / "entity_types" / "deed.yaml"
    entity_file.write_text(
        _ENTITY_TYPE_DECLARATION + '    - fact_type_pattern: "fact:credential:*:mark"\n',
        encoding="utf-8",
    )
    model_file = destination / "models" / "credential_command.yaml"
    model = model_file.read_text(encoding="utf-8")
    model_file.write_text(
        model.replace('["fact:credential:*:link"]', '["fact:credential:*:link", "fact:credential:*:mark"]'),
        encoding="utf-8",
    )
    declaration = _IMPACT_PROFILE_DECLARATION + (
        '    - order: 20\n'
        '      fact_type: "fact:credential:*:mark"\n'
        '      resolver: "credential_command@1"\n'
    )
    profile_file = destination / "impact_profiles" / "deed.yaml"
    profile_file.write_text(declaration, encoding="utf-8")
    with pytest.raises(RegistrationRejected, match="impact_atomic_cross_host"):
        load_pack(destination, handlers=HANDLERS)

    obligation = declaration.replace('"atomic"', '"obligation"')
    profile_file.write_text(obligation, encoding="utf-8")
    assert load_pack(destination, handlers=HANDLERS).impact_profiles["deed@1"]["atomicity"] == "obligation"

    profile_file.write_text(obligation.replace("order: 20", "order: 5"), encoding="utf-8")
    with pytest.raises(RegistrationRejected, match="impact_layer_conflicts_order"):
        load_pack(destination, handlers=HANDLERS)


_AGGREGATION_DECLARATION = dedent("""\
    "deed_refold@1":
      mode: "distribution"
      refold_model_ref: "credential_command@1"
      refold_triggers: ["split", "merge", "fidelity_change", "scope_change"]
    """)


def _pack_with_aggregation_model(tmp_path, declaration):
    destination = shutil.copytree(PACK, tmp_path / "aggregation-pack")
    manifest = destination / "pack.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'contents:\n', 'contents:\n  aggregation_models: ["deed_refold"]\n'
        ),
        encoding="utf-8",
    )
    aggregation = destination / "aggregation_models"
    aggregation.mkdir()
    (aggregation / "deed_refold.yaml").write_text(declaration, encoding="utf-8")
    return destination


def test_pack_loads_aggregation_modes_and_registered_refold(tmp_path):
    declaration = _AGGREGATION_DECLARATION + (
        'quantity:\n  mode: "sum"\n'
        'queue:\n  mode: "ordered"\n'
        'independent:\n  mode: "none"\n'
    )
    destination = _pack_with_aggregation_model(tmp_path, declaration)
    loaded = load_pack(destination, handlers=HANDLERS)
    model = loaded.aggregation_models["deed_refold@1"]
    assert model["refold_model_ref"] in loaded.registry.models
    assert model["refold_triggers"] == ("split", "merge", "fidelity_change", "scope_change")
    assert loaded.aggregation_models["quantity"]["mode"] == "sum"
    assert loaded.aggregation_models["queue"]["mode"] == "ordered"
    assert loaded.aggregation_models["independent"]["mode"] == "none"
    with pytest.raises(TypeError):
        model["mode"] = "none"
    assert not load_pack(PACK, handlers=HANDLERS).aggregation_models


@pytest.mark.parametrize(("old", "new", "code"), [
    pytest.param('mode: "distribution"', 'mode: "unknown"', "pack_aggregation_mode_invalid", id="mode"),
    pytest.param('  refold_model_ref: "credential_command@1"\n', "", "pack_aggregation_refold_missing", id="missing-refold"),
    pytest.param('"credential_command@1"', '"missing@1"', "pack_aggregation_refold_unknown", id="unknown-refold"),
    pytest.param('"scope_change"', '"split"', "pack_aggregation_triggers_invalid", id="duplicate-trigger"),
    pytest.param('mode: "distribution"', 'mode: "sum"', "pack_aggregation_refold_unexpected", id="sum-refold"),
])
def test_pack_rejects_invalid_aggregation_model(tmp_path, old, new, code):
    destination = _pack_with_aggregation_model(tmp_path, _AGGREGATION_DECLARATION.replace(old, new))
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    matching = [violation for violation in error.value.violations if violation.code == code]
    assert [(v.target, Path(v.file).name, v.line) for v in matching] == [
        ("deed_refold@1", "deed_refold.yaml", 1)
    ]



_COST_BINDING_DECLARATION = dedent("""\
    "spirit_cost_abilities@1":
      applies_to: ["skill:charge", "skill:shout"]
      cost_model: "credential_command@1"
    """)


def _pack_with_cost_binding(tmp_path, declaration):
    destination = shutil.copytree(PACK, tmp_path / "binding-pack")
    manifest = destination / "pack.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'contents:\n', 'contents:\n  bindings: ["spirit_cost"]\n'
        ),
        encoding="utf-8",
    )
    bindings = destination / "bindings"
    bindings.mkdir()
    (bindings / "spirit_cost.yaml").write_text(declaration, encoding="utf-8")
    return destination


def test_pack_loads_cost_model_binding(tmp_path):
    destination = _pack_with_cost_binding(tmp_path, _COST_BINDING_DECLARATION)
    loaded = load_pack(destination, handlers=HANDLERS)
    binding = loaded.bindings["spirit_cost_abilities@1"]
    assert binding["cost_model"] in loaded.registry.models
    assert binding["applies_to"] == ("skill:charge", "skill:shout")
    with pytest.raises(TypeError):
        binding["applies_to"] = ()
    assert not load_pack(PACK, handlers=HANDLERS).bindings


@pytest.mark.parametrize(("old", "new", "code"), [
    pytest.param('"credential_command@1"', '"unknown@1"', "pack_binding_model_unknown", id="unknown-model"),
    pytest.param('["skill:charge", "skill:shout"]', '[]', "pack_binding_targets_invalid", id="empty-targets"),
    pytest.param('"skill:charge"', '"charge"', "pack_binding_targets_invalid", id="unqualified-target"),
    pytest.param('"skill:shout"', '"skill:charge"', "pack_binding_targets_invalid", id="duplicate-target"),
])
def test_pack_rejects_invalid_cost_model_binding(tmp_path, old, new, code):
    destination = _pack_with_cost_binding(tmp_path, _COST_BINDING_DECLARATION.replace(old, new))
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    matching = [violation for violation in error.value.violations if violation.code == code]
    assert [(v.target, Path(v.file).name, v.line) for v in matching] == [
        ("spirit_cost_abilities@1", "spirit_cost.yaml", 1)
    ]



def _write_overlay(tmp_path, base, extra_contents="", parent_id="credential_reference"):
    child = tmp_path / "overlay"
    child.mkdir()
    (child / "pack.yaml").write_text(
        dedent(f"""\
        pack_id: "credential_overlay"
        pack_version: "2.0.0"
        schema_version: 1
        parent_pack:
          pack_id: "{parent_id}"
          pack_version: "1.0.0"
        """) + extra_contents,
        encoding="utf-8",
    )
    return child, {(parent_id, "1.0.0"): base}


def test_pack_resolves_parent_entries_as_whole_values_and_pins_path(tmp_path):
    parent = _pack_with_pool(tmp_path, _POOL_DECLARATION)
    child, parents = _write_overlay(
        tmp_path, parent, 'contents:\n  pool_defs: ["overrides"]\n',
    )
    (child / "pool_defs").mkdir()
    (child / "pool_defs/overrides.yaml").write_text(
        _POOL_DECLARATION.replace('  description: "Stamina used during a movement window"\n', "")
        .replace('initial: "75.5"', 'initial: "65"')
        + _POOL_DECLARATION.replace("stamina:", "willpower:"),
        encoding="utf-8",
    )

    loaded = load_pack(child, handlers=HANDLERS, parent_packs=parents)
    original = load_pack(parent, handlers=HANDLERS)
    assert loaded.pool_defs["stamina"]["initial"] == "65"
    assert "description" not in loaded.pool_defs["stamina"]
    assert "willpower" in loaded.pool_defs
    assert "fact:credential:*:link" in loaded.registry.facts
    assert loaded.legacy_rule == original.legacy_rule
    assert [pin.pack_id for pin in loaded.resolved_packs] == ["credential_reference", "credential_overlay"]
    assert loaded.resolved_packs[0].content_hash == original.content_hash
    assert loaded.content_hash != original.content_hash
    assert load_pack(
        child, handlers=HANDLERS, parent_packs=parents, expected_content_hash=loaded.content_hash,
    ).content_hash == loaded.content_hash

    manifest = parent / "pack.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        'condition_revision: 1', 'condition_revision: 2',
    ), encoding="utf-8")
    with pytest.raises(RegistrationRejected, match="pack_content_hash_mismatch"):
        load_pack(child, handlers=HANDLERS, parent_packs=parents, expected_content_hash=loaded.content_hash)


def test_pack_does_not_inherit_missing_fields_in_overridden_entry(tmp_path):
    parent = _pack_with_pool(tmp_path, _POOL_DECLARATION)
    child, parents = _write_overlay(tmp_path, parent, 'contents:\n  pool_defs: ["stamina"]\n')
    (child / "pool_defs").mkdir()
    (child / "pool_defs/stamina.yaml").write_text(
        'stamina:\n  initial: "65"\n', encoding="utf-8",
    )
    with pytest.raises(RegistrationRejected, match="pack_pool_scale_invalid"):
        load_pack(child, handlers=HANDLERS, parent_packs=parents)


def test_pack_overlay_can_narrow_an_inherited_learner_set(tmp_path):
    parent = shutil.copytree(PACK, tmp_path / "parent")
    fact_path = Path("fact_types/credential_link.yaml")
    parent_fact = (parent / fact_path).read_text(encoding="utf-8")
    audience = '["role:credential_authority"]'
    (parent / fact_path).write_text(
        parent_fact.replace(audience, '["role:credential_authority", "role:reviewer"]'),
        encoding="utf-8",
    )
    child, parents = _write_overlay(tmp_path, parent, 'contents:\n  fact_types: ["credential_link"]\n')
    (child / "fact_types").mkdir()
    (child / fact_path).write_text(parent_fact, encoding="utf-8")

    loaded = load_pack(child, handlers=HANDLERS, parent_packs=parents)
    assert loaded.registry.facts["fact:credential:*:link"].visibility["learnable_by"] == (
        "role:credential_authority",
    )


def test_pack_rejects_unresolved_or_wrong_parent_pin(tmp_path):
    child, parents = _write_overlay(tmp_path, PACK, parent_id="wrong")
    with pytest.raises(RegistrationRejected, match="pack_parent_unknown"):
        load_pack(child, handlers=HANDLERS)
    with pytest.raises(RegistrationRejected, match="pack_parent_identity_mismatch"):
        load_pack(child, handlers=HANDLERS, parent_packs=parents)


def test_pack_rejects_cycle_in_parent_chain(tmp_path):
    parent = shutil.copytree(PACK, tmp_path / "parent")
    child, parents = _write_overlay(tmp_path, parent)
    manifest = parent / "pack.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "parent_pack: null",
            'parent_pack: {pack_id: "credential_overlay", pack_version: "2.0.0"}',
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistrationRejected, match="pack_cycle_in_parents"):
        load_pack(child, handlers=HANDLERS, parent_packs={**parents, ("credential_overlay", "2.0.0"): child})


@pytest.mark.parametrize(("old", "new", "code"), [
    pytest.param('    class: "private"\n', '    class: "public"\n',
                 "pack_overrides_visibility_requirement", id="visibility"),
    pytest.param('owner_ref: "Ownership"', 'owner_ref: "Credential"',
                 "pack_overrides_fact_authority", id="owner"),
    pytest.param('unknown_policy: "reject"', 'unknown_policy: "degrade"',
                 "pack_overrides_unknown_policy", id="unknown-policy"),
])
def test_pack_overlay_rejects_changes_to_inherited_safety_contracts(tmp_path, old, new, code):
    child, parents = _write_overlay(tmp_path, PACK, 'contents:\n  fact_types: ["credential_link"]\n')
    (child / "fact_types").mkdir()
    base_fact = (PACK / "fact_types/credential_link.yaml").read_text(encoding="utf-8")
    assert old in base_fact
    (child / "fact_types/credential_link.yaml").write_text(base_fact.replace(old, new), encoding="utf-8")
    with pytest.raises(RegistrationRejected, match=code):
        load_pack(child, handlers=HANDLERS, parent_packs=parents)



_COMMAND_CATALOG_DECLARATION = dedent("""\
    ownership.record_deed:
      version: 1
      handled_by: "Ownership"
      payload_schema: "record_deed@v1"
      requires_authority: true
      idempotency_shape: "command_id"
    """)


def _pack_with_command_catalog(tmp_path, declaration):
    destination = shutil.copytree(PACK, tmp_path / "command-pack")
    manifest = destination / "pack.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'contents:\n', 'contents:\n  command_catalog: ["deed"]\n'
        ),
        encoding="utf-8",
    )
    catalog = destination / "command_catalog"
    catalog.mkdir()
    (catalog / "deed.yaml").write_text(declaration, encoding="utf-8")
    return destination


@pytest.mark.parametrize("shape", [
    "command_id",
    "command_id + step",
    "principal_ref + idempotency_key",
    "effect_id + scheduled_world_tick",
])
def test_pack_loads_command_catalog_with_registered_domain_and_handler(tmp_path, shape):
    destination = _pack_with_command_catalog(
        tmp_path, _COMMAND_CATALOG_DECLARATION.replace('"command_id"', f'"{shape}"'),
    )
    loaded = load_pack(destination, handlers=HANDLERS, owner_domains={"Ownership": "ownership"})
    command = loaded.command_catalog["ownership.record_deed"]
    assert command["idempotency_shape"] == shape
    assert command["handled_by"] == "Ownership"
    with pytest.raises(TypeError):
        command["version"] = 2
    assert not load_pack(PACK, handlers=HANDLERS).command_catalog


@pytest.mark.parametrize(("old", "new", "code"), [
    pytest.param("ownership.record_deed", "inventory.record_deed", "pack_command_domain_unknown", id="domain"),
    pytest.param("ownership.record_deed", "record_deed", "pack_command_name_invalid", id="name"),
    pytest.param('"Ownership"', '"Credential"', "pack_command_owner_unknown", id="owner"),
    pytest.param('"Ownership"', '["Ownership"]', "pack_command_owner_unknown", id="multiple-owners"),
    pytest.param("version: 1", "version: true", "pack_command_version_invalid", id="version"),
    pytest.param('"record_deed@v1"', '""', "pack_command_payload_schema_invalid", id="schema"),
    pytest.param("requires_authority: true", "requires_authority: 1", "pack_command_authority_invalid", id="authority"),
    pytest.param('"command_id"', '"unknown_key"', "pack_command_idempotency_shape_invalid", id="idempotency"),
])
def test_pack_rejects_invalid_command_catalog_entry(tmp_path, old, new, code):
    destination = _pack_with_command_catalog(tmp_path, _COMMAND_CATALOG_DECLARATION.replace(old, new))
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS, owner_domains={"Ownership": "ownership"})
    assert [(Path(v.file).name, v.line) for v in error.value.violations if v.code == code] == [("deed.yaml", 1)]


def test_pack_cannot_declare_its_own_command_domain(tmp_path):
    destination = _pack_with_command_catalog(tmp_path, _COMMAND_CATALOG_DECLARATION)
    manifest = destination / "pack.yaml"
    with manifest.open("a", encoding="utf-8") as stream:
        stream.write('owner_domains: {Ownership: "ownership"}\n')
    with pytest.raises(RegistrationRejected, match="pack_command_domain_unknown"):
        load_pack(destination, handlers=HANDLERS)



def test_pack_overlay_cannot_drop_inherited_command_authority(tmp_path):
    parent = _pack_with_command_catalog(tmp_path, _COMMAND_CATALOG_DECLARATION)
    child, parents = _write_overlay(tmp_path, parent, 'contents:\n  command_catalog: ["deed"]\n')
    (child / "command_catalog").mkdir()
    (child / "command_catalog/deed.yaml").write_text(
        _COMMAND_CATALOG_DECLARATION.replace("requires_authority: true", "requires_authority: false"),
        encoding="utf-8",
    )
    with pytest.raises(RegistrationRejected, match="pack_overrides_command_authority"):
        load_pack(child, handlers=HANDLERS, parent_packs=parents, owner_domains={"Ownership": "ownership"})


def _copy_pack_for_owner(tmp_path, owner_id):
    destination = tmp_path / "owner-pack"
    shutil.copytree(PACK, destination)
    manifest_path = destination / "pack.yaml"
    manifest = manifest_path.read_text(encoding="utf-8").replace(
        '["Ownership"]', f'["{owner_id}"]'
    )
    manifest_path.write_text(manifest, encoding="utf-8")

    fact_path = destination / "fact_types/credential_link.yaml"
    fact = fact_path.read_text(encoding="utf-8").replace('"Ownership"', f'"{owner_id}"')
    fact_path.write_text(fact, encoding="utf-8")

    model_path = destination / "models/credential_command.yaml"
    model = model_path.read_text(encoding="utf-8").replace('"Ownership"', f'"{owner_id}"')
    model_path.write_text(model, encoding="utf-8")
    return destination


def test_legacy_credential_owner_pack_remains_loadable(tmp_path):
    destination = tmp_path / "legacy-credential-pack"
    shutil.copytree(PACK, destination)

    for relative_path in (
        "pack.yaml",
        "fact_types/credential_link.yaml",
        "models/credential_command.yaml",
    ):
        path = destination / relative_path
        path.write_text(
            path.read_text(encoding="utf-8").replace('"Ownership"', f'"{owner_id}"'),
            encoding="utf-8",
        )

    return destination


@pytest.mark.parametrize("owner_id", [
    "Body", "Equipment", "Inventory", "Ownership", "Production", "Morale",
    "Presence", "LifeState", "Survival", "Status", "Transport", "Population",
    "Command", "Organization", "Government", "Information", "Economy",
    "Social", "Politics", "Territory", "Objective", "Campaign",
])
def test_pack_can_reference_a_registered_owner(tmp_path, owner_id):
    loaded = load_pack(_copy_pack_for_owner(tmp_path, owner_id), handlers=HANDLERS)

    assert loaded.registry.facts["fact:credential:*:link"].owner_ref == owner_id
    assert loaded.registry.models["credential_command@1"].owner_ref == owner_id


def test_legacy_credential_owner_pack_remains_loadable(tmp_path):
    loaded = load_pack(_copy_pack_for_owner(tmp_path, "Credential"), handlers=HANDLERS)

    assert loaded.registry.facts["fact:credential:*:link"].owner_ref == "Credential"


@pytest.mark.parametrize("owner_id", [
    "UnknownOwner", "Combat", "Economy / Market", "Production / Facility", "ProductionFacility",
])
def test_pack_cannot_register_an_unknown_owner(tmp_path, owner_id):
    destination = _copy_pack_for_owner(tmp_path, owner_id)
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)

    assert "facttype_owner_unknown" in {violation.code for violation in error.value.violations}


@pytest.mark.parametrize("suffix,code", [
    ('"bad": 0.1\n', "pack_float_forbidden"),
    ('"bad": &shared {"value": 1}\n"alias": *shared\n', "pack_yaml_feature_forbidden"),
    ('"bad": !!str "value"\n', "pack_yaml_feature_forbidden"),
    ('"script": "execute"\n', "pack_contains_logic"),
])
def test_forbidden_yaml_never_returns_a_partially_loaded_pack(tmp_path, suffix, code):
    destination = tmp_path / "pack"
    shutil.copytree(PACK, destination)
    path = destination / "models/credential_command.yaml"
    path.write_text(path.read_text() + suffix, encoding="utf-8")
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    assert code in {v.code for v in error.value.violations}
    assert all(v.target and v.file and v.line >= 1 and v.hint for v in error.value.violations)


def test_independent_errors_are_reported_together_with_locations(tmp_path):
    destination = tmp_path / "pack"
    shutil.copytree(PACK, destination)
    path = destination / "models/credential_command.yaml"
    path.write_text(path.read_text() + '"bad": 0.1\n"script": "execute"\n', encoding="utf-8")
    with pytest.raises(RegistrationRejected) as error:
        load_pack(destination, handlers=HANDLERS)
    codes = {v.code for v in error.value.violations}
    assert {"pack_float_forbidden", "pack_contains_logic"} <= codes


def test_undeclared_content_and_runtime_reload_are_rejected(tmp_path):
    destination = tmp_path / "pack"
    shutil.copytree(PACK, destination)
    (destination / "extra.yaml").write_text('"extra": 1\n', encoding="utf-8")
    with pytest.raises(RegistrationRejected, match="pack_content_undeclared"):
        load_pack(destination, handlers=HANDLERS)
    with pytest.raises(RegistrationRejected, match="pack_runtime_reload_forbidden"):
        load_pack(PACK, handlers=HANDLERS, running=True)
