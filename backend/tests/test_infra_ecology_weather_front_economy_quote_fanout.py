import pytest

from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch


def _seed() -> tuple[GameplayEventStore, EcologyHazardAuthority, EconomyAuthorityService]:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    stream = ecology.ecology_stream_id(region_ref="region:q")
    assert store.append_batch(
        build_atomic_event_batch(
            command_id="fanout:weather",
            principal_ref="authority:ecology",
            stream_id=stream,
            expected_revision=0,
            event_specs=[("gameplay.ecology.weather_front.propagated", {"source_region_ref": "region:s", "target_region_ref": "region:q", "weather_ref": "weather:storm", "tick": 1})],
            idempotency_key="fanout:weather",
            causation_id="cause:fanout:weather",
            correlation_id="corr:fanout:weather",
        )
    ).committed
    economy = EconomyAuthorityService(store=store)
    for quote_ref in ("quote:a", "quote:b"):
        assert economy.publish_dynamic_quote(
            command_id=f"fanout:{quote_ref}",
            quote_payload={"quote_ref": quote_ref, "version": 1, "status": "active", "unit_price_minor": 100},
            idempotency_key=f"fanout:{quote_ref}",
            causation_id="cause:fanout:quote",
            correlation_id="corr:fanout:quote",
        ).committed
    return store, ecology, economy


def _admission(ecology: EcologyHazardAuthority):
    source, admission = ecology.admit_weather_front_to_economy_quote_fanout(
        region_ref="region:q", quote_refs=("quote:b", "quote:a")
    )
    assert source is not None and admission is not None
    return source, admission


def test_weather_front_quote_fanout_updates_two_existing_quotes_in_one_owner_batch() -> None:
    store, ecology, economy = _seed()
    source, admission = _admission(ecology)
    before_count = len(store.read_events())
    result = economy.settle_weather_front_quote_fanout(source=source, admission=admission, idempotency_key="fanout:settle")

    assert result.committed
    assert len(result.committed_event_ids) == 2
    assert len(store.read_events()) == before_count + 2
    assert [event.event_type for event in store.read_events()[-2:]] == [
        "gameplay.economy.dynamic_quote_published",
        "gameplay.economy.dynamic_quote_published",
    ]
    quotes = EconomyProjector().rebuild(store.read_events()).dynamic_quotes
    assert quotes["quote:a"]["unit_price_minor"] == 110
    assert quotes["quote:b"]["unit_price_minor"] == 110
    assert all(event.payload["ecology_weather_source"] == source for event in store.read_events()[-2:])


def test_weather_front_quote_fanout_requires_exact_opaque_two_quote_admission() -> None:
    store, ecology, economy = _seed()
    source, _admission_value = _admission(ecology)
    before = store.export_snapshot()
    result = economy.settle_weather_front_quote_fanout(source=source, admission=object(), idempotency_key="fanout:forged")
    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "weather_quote_fanout_admission_required"
    assert store.export_snapshot() == before

    source["quote_refs"] = ("quote:a", "quote:a")
    invalid = economy.settle_weather_front_quote_fanout(source=source, admission=object(), idempotency_key="fanout:duplicate-target")
    assert not invalid.committed
    assert invalid.failure is not None and invalid.failure.error_code == "weather_quote_fanout_source_invalid"
    assert store.export_snapshot() == before


def test_weather_front_quote_fanout_rejects_stale_source_missing_target_and_catalog_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    store, ecology, economy = _seed()
    source, admission = _admission(ecology)
    stream = ecology.ecology_stream_id(region_ref="region:q")
    assert store.append_batch(
        build_atomic_event_batch(
            command_id="fanout:advance",
            principal_ref="authority:ecology",
            stream_id=stream,
            expected_revision=1,
            event_specs=[("gameplay.ecology.environment.recorded", {"record_ref": "environment:q"})],
            idempotency_key="fanout:advance",
            causation_id="cause:fanout:advance",
            correlation_id="corr:fanout:advance",
        )
    ).committed
    before = store.export_snapshot()
    stale = economy.settle_weather_front_quote_fanout(source=source, admission=admission, idempotency_key="fanout:stale")
    assert not stale.committed
    assert stale.failure is not None and stale.failure.error_code == "weather_quote_fanout_source_invalid"
    assert store.export_snapshot() == before

    store, ecology, economy = _seed()
    source, admission = ecology.admit_weather_front_to_economy_quote_fanout(
        region_ref="region:q", quote_refs=("quote:a", "quote:missing")
    )
    assert source is not None and admission is not None
    missing = economy.settle_weather_front_quote_fanout(source=source, admission=admission, idempotency_key="fanout:missing")
    assert not missing.committed
    assert missing.failure is not None and missing.failure.error_code == "weather_quote_fanout_target_missing"

    store, ecology, economy = _seed()
    source, admission = _admission(ecology)
    before = store.export_snapshot()

    def reject_contract(**_kwargs: object) -> None:
        raise GovernedAuthorityContractError("governed_authority_contract_stream_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", staticmethod(reject_contract))
    rejected = economy.settle_weather_front_quote_fanout(source=source, admission=admission, idempotency_key="fanout:catalog")
    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "governed_authority_contract_stream_mismatch"
    assert store.export_snapshot() == before


def test_weather_front_quote_fanout_duplicate_and_canonical_pair_order_are_replayable() -> None:
    store, ecology, economy = _seed()
    source, admission = _admission(ecology)
    first = economy.settle_weather_front_quote_fanout(source=source, admission=admission, idempotency_key="fanout:duplicate")
    before = store.export_snapshot()
    duplicate = economy.settle_weather_front_quote_fanout(source=source, admission=admission, idempotency_key="fanout:duplicate")
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert store.export_snapshot() == before

    replay = GameplayProjectionReplay(projector_id="inf3n", projector_version="1")
    full = replay.full_replay(store.read_events())
    tail = replay.checkpoint_plus_tail_replay(replay.create_checkpoint(()), store.read_events())
    assert full.succeeded and tail.succeeded and full.projection_hash == tail.projection_hash


def test_weather_front_quote_fanout_private_source_is_zero_write() -> None:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    stream = ecology.ecology_stream_id(region_ref="region:q")
    batch = build_atomic_event_batch(
        command_id="fanout:private-weather",
        principal_ref="authority:ecology",
        stream_id=stream,
        expected_revision=0,
        event_specs=[("gameplay.ecology.weather_front.propagated", {"source_region_ref": "region:s", "target_region_ref": "region:q", "weather_ref": "weather:storm", "tick": 1})],
        idempotency_key="fanout:private-weather",
        causation_id="cause:fanout:private-weather",
        correlation_id="corr:fanout:private-weather",
    )
    private = batch.model_copy(update={"events": [batch.events[0].model_copy(update={"visibility_policy": "authority_only"})]}, deep=True)
    assert store.append_batch(private).committed
    source, admission = ecology.admit_weather_front_to_economy_quote_fanout(region_ref="region:q", quote_refs=("quote:a", "quote:b"))
    before = store.export_snapshot()
    result = EconomyAuthorityService(store=store).settle_weather_front_quote_fanout(source=source or {}, admission=admission, idempotency_key="fanout:private")
    assert source is None and admission == "weather_front_quote_fanout_source_missing"
    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "weather_quote_fanout_source_invalid"
    assert store.export_snapshot() == before
