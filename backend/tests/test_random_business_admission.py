from hashlib import sha256

import pytest

from app.gameplay.random_business_admission import (
    RandomBusinessAdmission,
    RandomBusinessAdmissionError,
    RandomBusinessRequest,
    RandomBusinessSource,
)


def _source(**changes):
    data = dict(
        demand_ref="random-demand:festival-draw",
        demand_revision="1",
        kind="lottery",
        issuer_ref="content-publisher:festival",
        fact_owner_ref="content-owner:festival",
        actor_scope=("character:scout-1",),
        world_scope=("world:main",),
        timeline_scope=("timeline:main",),
        valid_from_world_tick=10,
        valid_until_world_tick=100,
        candidate_registry_ref="loot-registry:festival",
        candidate_registry_revision="3",
        algorithm_revision="rng:sha256-v1",
        seed_policy_revision="seed-policy:world-window-v1",
        source_digest="sha256:" + sha256(b"festival-source-v1").hexdigest(),
        read_principals=("economy-random-caller",),
        receipt_lookup_ref="economy:random-receipts",
        revocation_owner_ref="content-owner:festival",
    )
    data.update(changes)
    return RandomBusinessSource(**data)


def _request(source=None, **changes):
    source = source or _source()
    data = dict(
        operation_ref="draw:festival:1",
        effect_ref="effect:festival-reward",
        target_ref="character:scout-1",
        draw_index=0,
        seed="private-seed:1",
        source_digest=source.source_digest,
    )
    data.update(changes)
    return RandomBusinessRequest(**data)


def _admit(source=None, **kwargs):
    source = source or _source()
    return RandomBusinessAdmission().admit(
        source,
        _request(source),
        actor_ref=kwargs.get("actor_ref", "character:scout-1"),
        world_ref=kwargs.get("world_ref", "world:main"),
        timeline_ref=kwargs.get("timeline_ref", "timeline:main"),
        now_world_tick=kwargs.get("now_world_tick", 20),
        caller_principal=kwargs.get("caller_principal", "economy-random-caller"),
    )


def test_admits_and_freezes_published_random_source():
    frozen = _admit()
    assert frozen.source.algorithm_revision == "rng:sha256-v1"
    assert frozen.request.seed == "private-seed:1"


@pytest.mark.parametrize("kwargs,reason", [
    ({"actor_ref": "character:other"}, "scope_denied"),
    ({"now_world_tick": 101}, "expired"),
    ({"caller_principal": "untrusted"}, "read_denied"),
])
def test_admission_rejects_invalid_scope_or_time(kwargs, reason):
    with pytest.raises(RandomBusinessAdmissionError, match=reason):
        _admit(**kwargs)


def test_digest_and_changed_source_are_rejected():
    source = _source()
    with pytest.raises(RandomBusinessAdmissionError, match="digest_conflict"):
        RandomBusinessAdmission().admit(
            source,
            _request(source, source_digest="sha256:" + "0" * 64),
            actor_ref="character:scout-1", world_ref="world:main",
            timeline_ref="timeline:main", now_world_tick=20,
            caller_principal="economy-random-caller",
        )
    frozen = _admit(source)
    with pytest.raises(RandomBusinessAdmissionError, match="source_changed"):
        RandomBusinessAdmission().revalidate(frozen, _source(demand_revision="2"), now_world_tick=21)


def test_request_target_must_match_admitted_actor_scope():
    source = _source()
    with pytest.raises(RandomBusinessAdmissionError, match="target_conflict"):
        RandomBusinessAdmission().admit(
            source,
            _request(source, target_ref="character:other"),
            actor_ref="character:scout-1",
            world_ref="world:main",
            timeline_ref="timeline:main",
            now_world_tick=20,
            caller_principal="economy-random-caller",
        )


@pytest.mark.parametrize("field,value", [("valid_from_world_tick", "10"), ("valid_until_world_tick", 100.0)])
def test_random_source_rejects_non_integer_world_ticks(field, value):
    values = dict(_source().model_dump())
    values[field] = value
    with pytest.raises(ValueError):
        RandomBusinessSource(**values)


@pytest.mark.parametrize("now_world_tick", ["20", 20.0, True, -1])
def test_admission_rejects_non_integer_or_negative_world_tick(now_world_tick):
    with pytest.raises(RandomBusinessAdmissionError, match="world_tick_invalid"):
        _admit(now_world_tick=now_world_tick)


def test_revalidation_rejects_non_integer_world_tick():
    frozen = _admit()
    with pytest.raises(RandomBusinessAdmissionError, match="world_tick_invalid"):
        RandomBusinessAdmission().revalidate(frozen, frozen.source, now_world_tick=True)
