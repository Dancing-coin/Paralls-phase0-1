from hashlib import sha256

import pytest

from app.gameplay.resource_template_admission import (
    ResourceTemplateAdmission,
    ResourceTemplateAdmissionError,
    ResourceTemplateEntry,
    ResourceTemplateSource,
)


def _source(**changes):
    digest = "sha256:" + sha256(b"published-template-v1").hexdigest()
    data = dict(
        template_ref="character-template:scout",
        template_revision="7",
        issuer_ref="character-template-publisher",
        fact_owner_ref="character-template-owner",
        actor_scope=("character:scout-1",),
        world_scope=("world:main",),
        timeline_scope=("timeline:main",),
        valid_from_world_tick=10,
        valid_until_world_tick=100,
        source_digest=digest,
        binding_revision="binding:7",
        read_principals=("resource-consumer",),
        receipt_kind="character_template_publication",
        receipt_key="character-template:scout@7",
        revocation_owner_ref="character-template-owner",
        resources=(
            ResourceTemplateEntry(resource_id="core.stamina", maximum=20, capacity=20, base_capacity=20, initial=20, recovery_amount=2, recovery_period_world_ticks=5, lock_issuer_ref="ability-owner", lock_lifecycle_revision="lock:1"),
            ResourceTemplateEntry(resource_id="core.mana", maximum=12, capacity=12, base_capacity=12, initial=12, recovery_amount=1, recovery_period_world_ticks=5, lock_issuer_ref="ability-owner", lock_lifecycle_revision="lock:1"),
            ResourceTemplateEntry(resource_id="core.action_points", maximum=6, capacity=6, base_capacity=6, initial=6, recovery_amount=1, recovery_period_world_ticks=10, lock_issuer_ref="ability-owner", lock_lifecycle_revision="lock:1"),
        ),
    )
    data.update(changes)
    return ResourceTemplateSource(**data)


def _admit(source=None, **changes):
    args = dict(actor_ref="character:scout-1", world_ref="world:main", timeline_ref="timeline:main", now_world_tick=20, caller_principal="resource-consumer", binding_revision="binding:7")
    args.update(changes)
    return ResourceTemplateAdmission().admit(source or _source(), **args)


def test_admits_explicit_core_template_and_freezes_source():
    frozen = _admit()
    assert frozen.source.template_revision == "7"
    assert frozen.source.relation_kind == "independent"
    assert frozen.source.relation_policy_ref == "resource-relation:independent@1"
    assert {entry.resource_id for entry in frozen.source.resources} == {"core.stamina", "core.mana", "core.action_points"}


@pytest.mark.parametrize("kwargs,reason", [
    ({"source": None}, "resource_template_source_missing"),
    ({"caller_principal": "untrusted"}, "resource_template_read_denied"),
    ({"actor_ref": "character:other"}, "resource_template_scope_denied"),
    ({"now_world_tick": 101}, "resource_template_expired"),
    ({"binding_revision": "binding:6"}, "resource_template_binding_revision_conflict"),
])
def test_admission_fail_closed(kwargs, reason):
    source = kwargs.pop("source", _source())
    args = dict(actor_ref="character:scout-1", world_ref="world:main", timeline_ref="timeline:main", now_world_tick=20, caller_principal="resource-consumer", binding_revision="binding:7")
    args.update(kwargs)
    with pytest.raises(ResourceTemplateAdmissionError, match=reason):
        ResourceTemplateAdmission().admit(source, **args)


def test_relation_policy_rejects_unknown_endpoint_policy() -> None:
    with pytest.raises(ValueError, match="relation_policy_invalid"):
        _source(relation_kind="independent", relation_policy_ref="resource-relation:coupled@1")


def test_relation_policy_rejects_unknown_relation_kind() -> None:
    with pytest.raises(ValueError):
        _source(relation_kind="transmuting")


@pytest.mark.parametrize("kind", ["coupled", "fused"])
def test_unimplemented_relation_does_not_admit_conversion(kind: str) -> None:
    with pytest.raises(ValueError):
        _source(relation_kind=kind)


def test_relation_does_not_extend_registered_resource_endpoints() -> None:
    source = _source().model_dump(mode="json")
    source["resources"][0]["resource_id"] = "mental:focus"
    with pytest.raises(ValueError):
        ResourceTemplateSource.model_validate(source)


def test_revalidate_rejects_changed_published_source():
    frozen = _admit()
    changed = _source(template_revision="8", binding_revision="binding:8")
    with pytest.raises(ResourceTemplateAdmissionError, match="source_changed"):
        ResourceTemplateAdmission().revalidate(frozen, changed, now_world_tick=21, binding_revision="binding:8")


def test_template_rejects_initial_above_maximum():
    with pytest.raises(ValueError, match="initial_exceeds"):
        ResourceTemplateEntry(resource_id="core.stamina", maximum=1, capacity=1, base_capacity=1, initial=2, recovery_amount=1, recovery_period_world_ticks=1, lock_issuer_ref="owner", lock_lifecycle_revision="1")


def test_template_rejects_capacity_below_declared_maximum():
    with pytest.raises(ValueError, match="capacity_below_maximum"):
        ResourceTemplateEntry(resource_id="core.stamina", maximum=10, capacity=5, base_capacity=5,
                              initial=5, recovery_amount=1, recovery_period_world_ticks=1,
                              lock_issuer_ref="owner", lock_lifecycle_revision="1")


@pytest.mark.parametrize("field,value", [("maximum", "20"), ("initial", 20.0), ("recovery_amount", True), ("recovery_period_world_ticks", "5")])
def test_template_rejects_non_integer_policy_values(field, value):
    values = dict(resource_id="core.stamina", maximum=20, capacity=20, base_capacity=20, initial=20, recovery_amount=2,
                  recovery_period_world_ticks=5, lock_issuer_ref="owner",
                  lock_lifecycle_revision="1")
    values[field] = value
    with pytest.raises(ValueError):
        ResourceTemplateEntry(**values)


@pytest.mark.parametrize("now_world_tick", ["20", 20.0, True, -1])
def test_admission_rejects_non_integer_or_negative_world_tick(now_world_tick):
    with pytest.raises(ResourceTemplateAdmissionError, match="world_tick_invalid"):
        _admit(now_world_tick=now_world_tick)


def test_revalidation_rejects_non_integer_world_tick():
    frozen = _admit()
    with pytest.raises(ResourceTemplateAdmissionError, match="world_tick_invalid"):
        ResourceTemplateAdmission().revalidate(frozen, frozen.source, now_world_tick=True,
                                               binding_revision="binding:7")
