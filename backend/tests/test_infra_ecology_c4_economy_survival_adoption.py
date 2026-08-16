from __future__ import annotations

from app.gameplay.ecology_consumer_admission import EcologyConsumerAdmissionCheck
from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.survival_runtime import SurvivalAuthority
from test_infra_ecology_weather_front_economy_quote_fanout import _admission as fanout_admission
from test_infra_ecology_weather_front_economy_quote_fanout import _seed as fanout_seed
from test_infra_weather_front_survival_cold import _command as cold_command
from test_infra_weather_front_survival_cold import _seed as survival_seed
from test_infra_weather_front_survival_overheated import _heat_command


def _economy_quote_seed() -> tuple[GameplayEventStore, EconomyAuthorityService, dict[str, object], object]:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    stream = ecology.ecology_stream_id(region_ref="region:q")
    assert store.append_batch(
        build_atomic_event_batch(
            command_id="weather:c4:quote",
            principal_ref="authority:ecology",
            stream_id=stream,
            expected_revision=0,
            event_specs=[
                (
                    "gameplay.ecology.weather_front.propagated",
                    {
                        "source_region_ref": "region:s",
                        "target_region_ref": "region:q",
                        "weather_ref": "weather:storm",
                        "tick": 1,
                    },
                )
            ],
            idempotency_key="weather:c4:quote",
            causation_id="cause:c4:quote",
            correlation_id="corr:c4:quote",
        )
    ).committed
    economy = EconomyAuthorityService(store=store)
    assert economy.publish_dynamic_quote(
        command_id="quote:c4",
        quote_payload={"quote_ref": "quote:q", "version": 1, "status": "active", "unit_price_minor": 100},
        idempotency_key="quote:c4",
        causation_id="cause:c4:quote",
        correlation_id="corr:c4:quote",
    ).committed
    source, admission = ecology.admit_weather_front_to_economy_quote(
        region_ref="region:q", quote_ref="quote:q"
    )
    assert source is not None
    return store, economy, source, admission


def test_c4_adoption_economy_quote_invokes_closed_check(monkeypatch) -> None:
    store, economy, source, admission = _economy_quote_seed()
    original = EcologyConsumerAdmissionCheck.verify.__func__
    calls: list[dict[str, object]] = []

    def observe(cls, **kwargs):
        calls.append(kwargs)
        return original(cls, **kwargs)

    monkeypatch.setattr(EcologyConsumerAdmissionCheck, "verify", classmethod(observe))
    result = economy.settle_weather_front_quote(source=source, admission=admission, idempotency_key="c4:quote")

    assert result.committed
    assert len(calls) == 1
    assert calls[0]["contract_ref"] == "inf:weather-front-economy-quote@1"


def test_c4_adoption_economy_quote_fanout_invokes_closed_check(monkeypatch) -> None:
    store, ecology, economy = fanout_seed()
    source, admission = fanout_admission(ecology)
    original = EcologyConsumerAdmissionCheck.verify.__func__
    calls: list[dict[str, object]] = []

    def observe(cls, **kwargs):
        calls.append(kwargs)
        return original(cls, **kwargs)

    monkeypatch.setattr(EcologyConsumerAdmissionCheck, "verify", classmethod(observe))
    result = economy.settle_weather_front_quote_fanout(source=source, admission=admission, idempotency_key="c4:quote-fanout")

    assert result.committed
    assert len(calls) == 1
    assert calls[0]["contract_ref"] == "inf:weather-front-economy-quote-fanout@1"


def test_c4_adoption_survival_cold_invokes_closed_check(monkeypatch) -> None:
    store, weather_event_id, assignment_event_id = survival_seed()
    original = EcologyConsumerAdmissionCheck.verify.__func__
    calls: list[dict[str, object]] = []

    def observe(cls, **kwargs):
        calls.append(kwargs)
        return original(cls, **kwargs)

    monkeypatch.setattr(EcologyConsumerAdmissionCheck, "verify", classmethod(observe))
    result = SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=cold_command(store, weather_event_id, assignment_event_id, key="c4:cold")
    )

    assert result.committed
    assert len(calls) == 1
    assert calls[0]["contract_ref"] == "inf:weather-front-survival-cold@1"


def test_c4_adoption_survival_heat_invokes_closed_check(monkeypatch) -> None:
    store, weather_event_id, assignment_event_id = survival_seed(source_weather_ref="weather:heat")
    original = EcologyConsumerAdmissionCheck.verify.__func__
    calls: list[dict[str, object]] = []

    def observe(cls, **kwargs):
        calls.append(kwargs)
        return original(cls, **kwargs)

    monkeypatch.setattr(EcologyConsumerAdmissionCheck, "verify", classmethod(observe))
    result = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(store, weather_event_id, assignment_event_id, key="c4:heat")
    )

    assert result.committed
    assert len(calls) == 1
    assert calls[0]["contract_ref"] == "inf:weather-front-survival-heat@1"


def test_c4_adoption_economy_rejection_is_zero_write(monkeypatch) -> None:
    store, economy, source, admission = _economy_quote_seed()
    before = store.export_snapshot()

    def reject(cls, **kwargs):
        return cls(accepted=False, contract_ref=str(kwargs["contract_ref"]), error_code="c4:denied")

    monkeypatch.setattr(EcologyConsumerAdmissionCheck, "verify", classmethod(reject))
    result = economy.settle_weather_front_quote(source=source, admission=admission, idempotency_key="c4:quote:deny")

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "c4:denied"
    assert store.export_snapshot() == before


def test_c4_adoption_survival_rejection_is_zero_write(monkeypatch) -> None:
    store, weather_event_id, assignment_event_id = survival_seed(source_weather_ref="weather:heat")
    before = store.export_snapshot()

    def reject(cls, **kwargs):
        return cls(accepted=False, contract_ref=str(kwargs["contract_ref"]), error_code="c4:denied")

    monkeypatch.setattr(EcologyConsumerAdmissionCheck, "verify", classmethod(reject))
    result = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(store, weather_event_id, assignment_event_id, key="c4:heat:deny")
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "c4:denied"
    assert store.export_snapshot() == before


def test_c4_adoption_economy_full_and_checkpoint_tail_replay_match() -> None:
    store, economy, source, admission = _economy_quote_seed()
    assert economy.settle_weather_front_quote(
        source=source, admission=admission, idempotency_key="c4:quote:replay"
    ).committed

    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="inf-3p-c4-adoption", projector_version="1")
    checkpoint = replay.create_checkpoint(events[:-1])

    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(
        checkpoint, events[-1:]
    ).projection_hash
