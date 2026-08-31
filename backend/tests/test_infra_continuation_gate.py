from __future__ import annotations

from app.gameplay.ecology_runtime import EcologyHazardAuthority


def test_inf3_continuation_gate_exposes_ecology_owner() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["owner"] == "authority:ecology"


def test_inf3_continuation_gate_exposes_one_canonical_ecology_stream() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["stream_pattern"] == "gameplay:ecology:{region_ref}"


def test_inf3_continuation_gate_exposes_canonical_record_kinds() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["record_kinds"] == ("region", "environment", "resource", "crop", "hazard")


def test_inf3_continuation_gate_exposes_canonical_event_family() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["event_types"] == (
        "gameplay.ecology.region.recorded",
        "gameplay.ecology.region.retired",
        "gameplay.ecology.environment.recorded",
        "gameplay.ecology.environment.retired",
        "gameplay.ecology.resource.recorded",
        "gameplay.ecology.resource.retired",
        "gameplay.ecology.crop.recorded",
        "gameplay.ecology.crop.retired",
        "gameplay.ecology.hazard.recorded",
        "gameplay.ecology.hazard.retired",
        "gameplay.ecology.weather_front.propagated",
    )


def test_inf3_continuation_gate_exposes_exact_registered_consumer_edges() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["enabled_consumer_edges"] == (
        "ecology-hazard:frost-to-construction-finish:v1",
        "ecology-process:seasonal-to-construction-maintenance:v1",
        "ecology-weather:front-to-construction-maintenance:v1",
        "ecology-weather:front-to-construction-maintenance-fanout:v1",
        "ecology-weather:front-to-organization-supply:v1",
        "ecology-weather:front-to-organization-supply-fanout:v1",
        "ecology-weather:front-to-economy-quote:v1",
        "ecology-weather:front-to-economy-quote-fanout:v1",
        "ecology-weather:front-to-water-resource-recovery:v1",
    )


def test_inf3_continuation_gate_keeps_weather_front_internal_to_ecology() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["regional_propagation"] == {
        "policy_ref": "policy:ecology_weather_front_step",
        "policy_revision": "1",
        "max_targets": 1,
        "max_chain_depth": 1,
        "scope": "project",
    }


def test_inf3_continuation_gate_exposes_closed_wave_fanout() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["regional_wave_fanout"] == {
        "policy_ref": "policy:ecology_weather_front_wave_fanout",
        "policy_revision": "1",
        "max_targets": 6,
        "max_chain_depth": 2,
        "scope": "project",
    }


def test_inf3_continuation_gate_requires_registered_hazard_admission_identity() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["consumer_admission_fence"] == "exact_ecology_registered_identity"


def test_inf3_continuation_gate_advances_only_to_inf4r() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["blocked_next_package"] == "INF-4R"


def test_inf3_continuation_gate_exposes_canonical_write_path() -> None:
    contract = EcologyHazardAuthority.canonical_contract()

    assert contract["write_path"] == (
        "authority -> GameplayCommandEnvelope/SettlementPlan -> "
        "GameplayEventStore.append_batch -> outbox/replay -> scoped projection"
    )
