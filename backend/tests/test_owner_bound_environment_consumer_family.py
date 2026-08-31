from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

import pytest

from app.gameplay.closed_generic_gameplay_families import (
    OwnerBoundEnvironmentConsumerContent,
    OwnerBoundEnvironmentConsumerIntent,
)
from app.gameplay.patch_runtime import (
    CapabilityBindingRequest,
    GameplayPatchManifest,
    GameplayPatchRegistry,
    OutcomeDeclarationAuthorInput,
    PackageDefinition,
    PackageIdentity,
    PlatformExtension,
    TypedReadRequirement,
)
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.survival_runtime import SurvivalAuthority
from closed_generic_manifest_fixtures import load_manifest
from test_infra_weather_front_survival_cold import _seed, PROFILE_REF


def _digest(value: object) -> str:
    return "sha256:" + sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _manifest(
    *,
    package_revision: str,
    definition_ref: str,
    source_event_family_ref: str,
    target_state_definition_ref: str,
    policy_revision_ref: str,
    weather_ref: str | None = None,
    effect_ref: str | None = None,
    state_ref: str | None = None,
    magnitude: int | None = None,
    stack_key: str | None = None,
    stack_policy: str | None = None,
    stack_limit: int | None = None,
    expiry_policy: str | None = None,
    expires_after_ticks: int | None = None,
) -> GameplayPatchManifest:
    if effect_ref is None or state_ref is None:
        defaults = {
            "event:weather-front-rain@1": ("effect:hydration", "state:hydrated"),
            "event:weather-front-drought@1": ("effect:dehydration_exposure", "state:dehydrated"),
            "event:weather-front-frost@1": ("effect:cold_exposure", "state:cold"),
            "event:weather-front-heat@1": ("effect:heat_exposure", "state:overheated"),
        }
        default_effect_ref, default_state_ref = defaults[source_event_family_ref]
        effect_ref = effect_ref or default_effect_ref
        state_ref = state_ref or default_state_ref
    lifecycle_defaults = {
        "event:weather-front-rain@1": (100, "hydration", "refresh", 1, "scheduled", 1),
        "event:weather-front-drought@1": (100, "dehydration", "add", 2, "scheduled", 1),
        "event:weather-front-frost@1": (100, "cold", "add", 2, "scheduled", 1),
        "event:weather-front-heat@1": (100, "heat", "add", 2, "scheduled", 1),
    }
    default_magnitude, default_stack_key, default_stack_policy, default_stack_limit, default_expiry_policy, default_expires_after_ticks = lifecycle_defaults[source_event_family_ref]
    content = {
        "source_event_family_ref": source_event_family_ref,
        "target_state_definition_ref": target_state_definition_ref,
        "policy_revision_ref": policy_revision_ref,
        "effect_ref": effect_ref,
        "state_ref": state_ref,
        "magnitude": magnitude if magnitude is not None else default_magnitude,
        "stack_key": stack_key or default_stack_key,
        "stack_policy": stack_policy or default_stack_policy,
        "stack_limit": stack_limit if stack_limit is not None else default_stack_limit,
        "expiry_policy": expiry_policy or default_expiry_policy,
        "expires_after_ticks": expires_after_ticks if expires_after_ticks is not None else default_expires_after_ticks,
    }
    if weather_ref is not None:
        content["weather_ref"] = weather_ref
    definition = PackageDefinition(
        definition_ref=definition_ref,
        definition_schema_ref="schema:owner-bound-environment-consumer@1",
        source_package_revision=package_revision,
        typed_content=content,
    )
    declaration_payload = {
        "declaration_ref": f"declaration:{package_revision.split(':', 1)[1]}",
        "outcome_family_ref": "outcome:owner-bound-environment-consumer@1",
        "definition_refs": (definition.definition_ref,),
        "eligibility_refs": ("predicate:environment-source@1",),
        "policy_revision_ref": policy_revision_ref,
        "source_package_revision": package_revision,
    }
    declaration = OutcomeDeclarationAuthorInput(
        **declaration_payload,
        declaration_digest=_digest(declaration_payload),
    ).normalized()
    request = CapabilityBindingRequest(
        binding_ref=f"binding:{package_revision.split(':', 1)[1]}",
        capability_ref="capability:owner-bound-environment-consumer@1",
        source_package_revision=package_revision,
        declaration_ref=declaration.declaration_ref,
        typed_read_requirements=(
            TypedReadRequirement(
                requirement_ref=f"requirement:{package_revision.split(':', 1)[1]}",
                predicate_family_ref="predicate:environment-source@1",
                subject_slot_ref="slot:profile-region@1",
            ),
        ),
        proposal_effect_types=("effect:owner-bound-environment-consumer@1",),
    )
    extension = PlatformExtension(
        platform_schema_version="1.0",
        package_identity=PackageIdentity(
            package_id=f"package:{package_revision.split(':', 1)[1].split('@', 1)[0]}",
            package_version="1.0.0",
            package_revision=package_revision,
        ),
        package_definitions=(definition,),
        outcome_declarations=(declaration.model_dump(mode="json"),),
        capability_binding_requests=(request,),
        dependency_and_conflict_refs=(),
        replay_reader_refs=(),
        verification_profile_refs=(),
    )
    manifest = GameplayPatchManifest.model_validate(
        {
            "manifest_schema_version": 2,
            "patch_id": extension.package_identity.package_id,
            "patch_version": "1.0.0",
            "patch_revision_id": package_revision,
            "content_digest": "sha256:" + "0" * 64,
            "author_id": "author:repo",
            "trust_policy_ref": "trust:repo",
            "dependencies": (),
            "state_group_ids": (),
            "state_group_migrations": (),
            "event_schemas": (),
            "rules": (),
            "requested_capabilities": (),
            "economic_outcomes": (),
            "granted_effect_types": (),
            "verification_profiles": (),
            "platform_extension": extension.model_dump(mode="json"),
        }
    )
    return manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})


def _authority(*manifests: GameplayPatchManifest, store) -> SurvivalAuthority:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install_many(manifests)
    registry.activate(tuple(manifest.patch_revision_id for manifest in manifests))
    return SurvivalAuthority(store=store, package_registry=registry)


def _append_weather_front(store, weather_event_id: str, *, tick: int, key: str) -> str:
    weather_event = store.get_event(weather_event_id)
    result = store.append_batch(
        build_atomic_event_batch(
            command_id=f"command:{key}",
            principal_ref="authority:ecology",
            stream_id=weather_event.stream_id,
            expected_revision=store.get_stream_head(weather_event.stream_id),
            event_specs=(
                (
                    "gameplay.ecology.weather_front.propagated",
                    {
                        **weather_event.payload,
                        "tick": tick,
                    },
                ),
            ),
            idempotency_key=key,
            causation_id=f"cause:{key}",
            correlation_id=f"corr:{key}",
        )
    )
    assert result.committed
    return result.committed_event_ids[0]


def test_owner_bound_environment_consumer_content_requires_explicit_lifecycle_slots() -> None:
    content = OwnerBoundEnvironmentConsumerContent.model_validate(
        {
            "source_event_family_ref": "event:weather-front-rain@1",
            "weather_ref": "weather:rain",
            "target_state_definition_ref": "definition:survival-hydrated@1",
            "policy_revision_ref": "policy:weather-front-survival-hydration@1",
            "effect_ref": "effect:hydration",
            "state_ref": "state:hydrated",
            "magnitude": 100,
            "stack_key": "hydration",
            "stack_policy": "refresh",
            "stack_limit": 1,
            "expiry_policy": "scheduled",
            "expires_after_ticks": 1,
        }
    )

    assert content.stack_key == "hydration"
    assert content.stack_policy == "refresh"
    assert content.stack_limit == 1
    assert content.expires_after_ticks == 1

    with pytest.raises(Exception):
        OwnerBoundEnvironmentConsumerContent.model_validate(
            {
                "source_event_family_ref": "event:weather-front-rain@1",
                "weather_ref": "weather:rain",
                "target_state_definition_ref": "definition:survival-hydrated@1",
                "policy_revision_ref": "policy:weather-front-survival-hydration@1",
                "effect_ref": "effect:hydration",
                "state_ref": "state:hydrated",
            }
        )


@pytest.mark.parametrize(
    ("manifest_key", "source_weather_ref", "expected_effect_ref", "expected_state_ref", "expected_due_tick"),
    [
        (
            "owner-bound-environment-consumer-rain-v1",
            "weather:rain",
            "effect:hydration",
            "state:hydrated",
            5,
        ),
        (
            "owner-bound-environment-consumer-drought-v1",
            "weather:drought",
            "effect:dehydration_exposure",
            "state:dehydrated",
            5,
        ),
    ],
)
def test_owner_bound_environment_consumer_committed_manifests_drive_two_content_instances(
    manifest_key: str,
    source_weather_ref: str,
    expected_effect_ref: str,
    expected_state_ref: str,
    expected_due_tick: int,
) -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref=source_weather_ref)
    authority = _authority(load_manifest(manifest_key), store=store)

    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id=f"command:{manifest_key}",
            correlation_id=f"corr:{manifest_key}",
        )
    )

    assert result.committed, result.failure
    events = store.read_stream(f"gameplay:survival:{PROFILE_REF}")
    assert [event.event_type for event in events] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]
    assert events[0].payload["state"]["effect_ref"] == expected_effect_ref
    assert events[0].payload["state"]["state_ref"] == expected_state_ref
    assert events[1].payload["due_tick"] == expected_due_tick


@pytest.mark.parametrize(
    ("manifest_key", "source_weather_ref", "expected_stacks"),
    [
        ("owner-bound-environment-consumer-rain-v1", "weather:rain", [1, 1]),
        ("owner-bound-environment-consumer-drought-v1", "weather:drought", [1, 2]),
    ],
)
def test_owner_bound_environment_consumer_uses_manifest_lifecycle_for_repeated_sources(
    manifest_key: str,
    source_weather_ref: str,
    expected_stacks: list[int],
) -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref=source_weather_ref)
    authority = _authority(load_manifest(manifest_key), store=store)

    first = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id=f"command:{manifest_key}:1",
            correlation_id=f"corr:{manifest_key}:1",
        )
    )
    second_weather_id = _append_weather_front(
        store,
        weather_id,
        tick=5,
        key=f"{manifest_key}:second",
    )
    second = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=second_weather_id,
            region_assignment_event_id=assignment_id,
            command_id=f"command:{manifest_key}:2",
            correlation_id=f"corr:{manifest_key}:2",
        )
    )

    assert first.committed
    assert second.committed
    applied = [
        event
        for event in store.read_stream(f"gameplay:survival:{PROFILE_REF}")
        if event.event_type == "gameplay.survival.state_applied"
    ]
    assert [event.payload["state"]["stacks"] for event in applied] == expected_stacks


@pytest.mark.parametrize(
    ("manifest", "source_weather_ref", "expected_state_ref"),
    [
        (
            _manifest(
                package_revision="package:environment-rain@1",
                definition_ref="definition:environment-rain@1",
                source_event_family_ref="event:weather-front-rain@1",
                target_state_definition_ref="definition:survival-hydrated@1",
                policy_revision_ref="policy:weather-front-survival-hydration@1",
            ),
            "weather:rain",
            "state:hydrated",
        ),
        (
            _manifest(
                package_revision="package:environment-drought@1",
                definition_ref="definition:environment-drought@1",
                source_event_family_ref="event:weather-front-drought@1",
                target_state_definition_ref="definition:survival-dehydrated@1",
                policy_revision_ref="policy:weather-front-survival-dehydration@1",
            ),
            "weather:drought",
            "state:dehydrated",
        ),
        (
            _manifest(
                package_revision="package:environment-cold@1",
                definition_ref="definition:environment-cold@1",
                source_event_family_ref="event:weather-front-frost@1",
                target_state_definition_ref="definition:survival-cold@1",
                policy_revision_ref="policy:weather-front-survival-cold@1",
            ),
            "weather:frost",
            "state:cold",
        ),
        (
            _manifest(
                package_revision="package:environment-heat@1",
                definition_ref="definition:environment-heat@1",
                source_event_family_ref="event:weather-front-heat@1",
                target_state_definition_ref="definition:survival-overheated@1",
                policy_revision_ref="policy:weather-front-survival-heat@1",
            ),
            "weather:heat",
            "state:overheated",
        ),
    ],
)
def test_owner_bound_environment_consumer_derives_multiple_state_rows_from_committed_weather_source(
    manifest: GameplayPatchManifest, source_weather_ref: str, expected_state_ref: str
) -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref=source_weather_ref)
    authority = _authority(manifest, store=store)

    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-family",
            correlation_id="corr:environment-family",
        )
    )

    assert result.committed
    assert authority.projector().states[(PROFILE_REF, expected_state_ref)].state_ref == expected_state_ref
    applied = next(
        event
        for event in store.read_stream(f"gameplay:survival:{PROFILE_REF}")
        if event.event_type == "gameplay.survival.state_applied"
    )
    assert applied.payload["family_ref"] == "owner_bound_environment_consumer@1"
    assert applied.payload["package_revision"] == manifest.patch_revision_id
    assert applied.payload["declaration_ref"].startswith("declaration:")
    assert applied.payload["descriptor_ref"] == "descriptor:owner-bound-environment-consumer@1"


@pytest.mark.parametrize(
    ("manifest", "source_weather_ref", "expected_effect_ref", "expected_state_ref"),
    [
        (
            _manifest(
                package_revision="package:environment-rain@1",
                definition_ref="definition:environment-rain@1",
                source_event_family_ref="event:weather-front-rain@1",
                target_state_definition_ref="definition:survival-hydrated@1",
                policy_revision_ref="policy:weather-front-survival-hydration@1",
                effect_ref="effect:rain-recovery@1",
                state_ref="state:hydrated@1",
            ),
            "weather:rain",
            "effect:rain-recovery@1",
            "state:hydrated@1",
        ),
        (
            _manifest(
                package_revision="package:environment-drought@1",
                definition_ref="definition:environment-drought@1",
                source_event_family_ref="event:weather-front-drought@1",
                target_state_definition_ref="definition:survival-dehydrated@1",
                policy_revision_ref="policy:weather-front-survival-dehydration@1",
                effect_ref="effect:drought-strain@1",
                state_ref="state:dehydrated@1",
            ),
            "weather:drought",
            "effect:drought-strain@1",
            "state:dehydrated@1",
        ),
    ],
)
def test_owner_bound_environment_consumer_uses_typed_content_effect_and_state_slots(
    manifest: GameplayPatchManifest,
    source_weather_ref: str,
    expected_effect_ref: str,
    expected_state_ref: str,
) -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref=source_weather_ref)
    authority = _authority(manifest, store=store)

    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-genericity",
            correlation_id="corr:environment-genericity",
        )
    )

    assert result.committed
    applied = next(
        event
        for event in store.read_stream(f"gameplay:survival:{PROFILE_REF}")
        if event.event_type == "gameplay.survival.state_applied"
    )
    assert applied.payload["state"]["effect_ref"] == expected_effect_ref
    assert applied.payload["state"]["state_ref"] == expected_state_ref


def test_owner_bound_environment_consumer_accepts_two_distinct_committed_contents_through_one_adapter() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:rain")
    authority = _authority(
        _manifest(
            package_revision="package:environment-rain@1",
            definition_ref="definition:environment-rain@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
            weather_ref="weather:rain",
        ),
        _manifest(
            package_revision="package:environment-drought@1",
            definition_ref="definition:environment-drought@1",
            source_event_family_ref="event:weather-front-drought@1",
            target_state_definition_ref="definition:survival-dehydrated@1",
            policy_revision_ref="policy:weather-front-survival-dehydration@1",
            weather_ref="weather:drought",
        ),
        store=store,
    )

    rain_result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-rain",
            correlation_id="corr:environment-rain",
        )
    )

    assert rain_result.committed


@pytest.mark.parametrize(
    ("manifest_key", "source_weather_ref", "expected_effect_ref", "expected_state_ref"),
    [
        (
            "owner-bound-environment-consumer-drought-v1",
            "weather:drought",
            "effect:dehydration_exposure",
            "state:dehydrated",
        ),
        (
            "owner-bound-environment-consumer-frost-v1",
            "weather:frost",
            "effect:cold_exposure",
            "state:cold",
        ),
    ],
)
def test_owner_bound_environment_consumer_loads_two_committed_manifests_from_disk_through_one_adapter(
    manifest_key: str,
    source_weather_ref: str,
    expected_effect_ref: str,
    expected_state_ref: str,
) -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref=source_weather_ref)
    manifest = load_manifest(manifest_key)
    authority = _authority(manifest, store=store)

    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id=f"command:{manifest_key}:disk",
            correlation_id=f"corr:{manifest_key}:disk",
        )
    )

    assert result.committed, result.failure
    applied = next(
        event
        for event in store.read_stream(f"gameplay:survival:{PROFILE_REF}")
        if event.event_type == "gameplay.survival.state_applied"
    )
    assert applied.payload["state"]["effect_ref"] == expected_effect_ref
    assert applied.payload["state"]["state_ref"] == expected_state_ref
    assert applied.payload["package_revision"] == manifest.patch_revision_id
    assert applied.payload["content_digest"] == manifest.content_digest


def test_owner_bound_environment_consumer_rejects_content_weather_mismatch_before_write() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:rain")
    before = store.export_snapshot()
    authority = _authority(
        _manifest(
            package_revision="package:environment-mismatch@1",
            definition_ref="definition:environment-mismatch@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
            weather_ref="weather:drought",
        ),
        store=store,
    )

    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-weather-mismatch",
            correlation_id="corr:environment-weather-mismatch",
        )
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "owner_bound_environment_consumer_source_conflict"
    assert store.export_snapshot() == before


def test_owner_bound_environment_consumer_rejects_unadmitted_effect_state_pair_without_write() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:rain")
    before = store.export_snapshot()
    authority = _authority(
        _manifest(
            package_revision="package:environment-forged@1",
            definition_ref="definition:environment-forged@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
            effect_ref="effect:forged@1",
            state_ref="state:forged@1",
        ),
        store=store,
    )

    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-forged",
            correlation_id="corr:environment-forged",
        )
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "owner_bound_environment_consumer_content_invalid"
    assert store.export_snapshot() == before


def test_owner_bound_environment_consumer_rejects_unadmitted_weather_row_without_write() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:heat")
    before = tuple(store.read_events())

    authority = _authority(
        _manifest(
            package_revision="package:environment-rain@1",
            definition_ref="definition:environment-rain@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
        ),
        store=store,
    )
    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-family",
            correlation_id="corr:environment-family",
        )
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "owner_bound_environment_consumer_source_conflict"
    assert tuple(store.read_events()) == before


def test_owner_bound_environment_consumer_requires_admitted_package_binding() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:rain")
    before = tuple(store.read_events())

    result = SurvivalAuthority(store=store).settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-family",
            correlation_id="corr:environment-family",
        )
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "owner_bound_environment_consumer_package_inactive"
    assert tuple(store.read_events()) == before


def test_owner_bound_environment_consumer_rejects_ambiguous_matching_bindings_without_write() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:rain")
    before = tuple(store.read_events())
    authority = _authority(
        _manifest(
            package_revision="package:environment-rain@1",
            definition_ref="definition:environment-rain@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
        ),
        _manifest(
            package_revision="package:environment-rain-duplicate@1",
            definition_ref="definition:environment-rain-duplicate@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
        ),
        store=store,
    )

    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-family",
            correlation_id="corr:environment-family",
        )
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "owner_bound_environment_consumer_binding_ambiguous"
    assert tuple(store.read_events()) == before


def test_owner_bound_environment_consumer_rejects_tampered_activation_content_pin_without_write() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:rain")
    authority = _authority(
        _manifest(
            package_revision="package:environment-rain@1",
            definition_ref="definition:environment-rain@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
        ),
        store=store,
    )
    registry = authority._package_registry
    active = registry.active_patch_set
    assert active is not None
    registry._active = replace(
        active,
        capability_bindings=(
            replace(
                active.capability_bindings[0],
                family_content_digest="sha256:" + "f" * 64,
            ),
        ),
    )
    before = tuple(store.read_events())

    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-tampered-pin",
            correlation_id="corr:environment-tampered-pin",
        )
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "owner_bound_environment_consumer_binding_invalid"
    assert tuple(store.read_events()) == before


def test_owner_bound_environment_consumer_intent_rejects_caller_target_coordinates() -> None:
    with pytest.raises(Exception):
        OwnerBoundEnvironmentConsumerIntent.model_validate(
            {
                "weather_event_id": "event:weather",
                "region_assignment_event_id": "event:assignment",
                "command_id": "command:environment",
                "correlation_id": "corr:environment",
                "actor_ref": "caller",
                "state_ref": "state:caller",
            }
        )


def test_owner_bound_environment_consumer_replays_duplicate_and_matches_tail() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:rain")
    authority = _authority(
        _manifest(
            package_revision="package:environment-rain@1",
            definition_ref="definition:environment-rain@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
        ),
        store=store,
    )
    intent = OwnerBoundEnvironmentConsumerIntent(
        weather_event_id=weather_id,
        region_assignment_event_id=assignment_id,
        command_id="command:environment-family",
        correlation_id="corr:environment-family",
    )
    first = authority.settle_owner_bound_environment_consumer(intent=intent)
    before = tuple(store.read_events())

    duplicate = authority.settle_owner_bound_environment_consumer(intent=intent)
    changed = authority.settle_owner_bound_environment_consumer(
        intent=intent.model_copy(update={"correlation_id": "corr:environment:changed"})
    )
    full = authority.projector()
    tail = authority.projector(checkpoint_at=1)

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert tuple(store.read_events()) == before
    assert full.states == tail.states
    assert full.source_revision_vector == tail.source_revision_vector


def test_owner_bound_environment_consumer_replay_rejects_tampered_family_provenance() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:rain")
    authority = _authority(
        _manifest(
            package_revision="package:environment-replay-provenance@1",
            definition_ref="definition:environment-replay-provenance@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
        ),
        store=store,
    )
    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-replay-provenance",
            correlation_id="corr:environment-replay-provenance",
        )
    )
    assert result.committed, result.failure
    event_id = result.committed_event_ids[0]
    event = store.get_event(event_id)
    mutated = event.model_copy(
        update={"payload": {**event.payload, "content_digest": "sha256:" + "f" * 64}},
        deep=True,
    )
    store._events[store._events.index(event)] = mutated
    store._events_by_id[event_id] = mutated

    with pytest.raises(Exception, match="owner_bound_environment_consumer_replay_invalid"):
        authority.projector()


def test_owner_bound_environment_consumer_replay_rejects_broken_obligation_linkage() -> None:
    store, weather_id, assignment_id = _seed(source_weather_ref="weather:rain")
    authority = _authority(
        _manifest(
            package_revision="package:environment-replay-lifecycle@1",
            definition_ref="definition:environment-replay-lifecycle@1",
            source_event_family_ref="event:weather-front-rain@1",
            target_state_definition_ref="definition:survival-hydrated@1",
            policy_revision_ref="policy:weather-front-survival-hydration@1",
        ),
        store=store,
    )
    result = authority.settle_owner_bound_environment_consumer(
        intent=OwnerBoundEnvironmentConsumerIntent(
            weather_event_id=weather_id,
            region_assignment_event_id=assignment_id,
            command_id="command:environment-replay-lifecycle",
            correlation_id="corr:environment-replay-lifecycle",
        )
    )
    assert result.committed, result.failure
    obligation_id = result.committed_event_ids[1]
    event = store.get_event(obligation_id)
    mutated = event.model_copy(
        update={"payload": {**event.payload, "obligation_id": "obligation:forged"}},
        deep=True,
    )
    store._events[store._events.index(event)] = mutated
    store._events_by_id[obligation_id] = mutated

    with pytest.raises(Exception, match="owner_bound_environment_consumer_replay_invalid"):
        authority.projector()
