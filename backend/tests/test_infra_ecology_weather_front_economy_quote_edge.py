from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.replay import GameplayProjectionReplay

def test_weather_front_updates_only_existing_economy_quote_through_owner_spine():
    store=GameplayEventStore(); ecology=EcologyHazardAuthority(store=store); stream=ecology.ecology_stream_id(region_ref="region:q")
    assert store.append_batch(build_atomic_event_batch(command_id="weather",principal_ref="authority:ecology",stream_id=stream,expected_revision=0,event_specs=[("gameplay.ecology.weather_front.propagated",{"source_region_ref":"region:s","target_region_ref":"region:q","weather_ref":"weather:storm","tick":1})],idempotency_key="weather",causation_id="c",correlation_id="r")).committed
    economy=EconomyAuthorityService(store=store); assert economy.publish_dynamic_quote(command_id="quote",quote_payload={"quote_ref":"quote:q","version":1,"status":"active","unit_price_minor":100},idempotency_key="quote",causation_id="c",correlation_id="r").committed
    source, admission=ecology.admit_weather_front_to_economy_quote(region_ref="region:q",quote_ref="quote:q")
    result=economy.settle_weather_front_quote(source=source,admission=admission,idempotency_key="weather:quote")
    committed_event=store.get_event(result.committed_event_ids[0])
    assert result.committed and committed_event.payload["ecology_weather_source"]==source and EconomyAuthorityService(store=store)._projector.rebuild(store.read_events()).dynamic_quotes["quote:q"]["unit_price_minor"]==110
    forged=economy.settle_weather_front_quote(source=source,admission=object(),idempotency_key="forged")
    assert not forged.committed and forged.failure and forged.failure.error_code=="weather_quote_admission_required"

def test_weather_front_quote_forged_admission_is_zero_write():
    store=GameplayEventStore(); economy=EconomyAuthorityService(store=store); before=store.export_snapshot()
    result=economy.settle_weather_front_quote(source={},admission=object(),idempotency_key="forged")
    assert not result.committed and result.failure and result.failure.error_code=="weather_quote_source_invalid"
    assert store.export_snapshot()==before


def test_weather_front_quote_catalog_mismatch_rejects_before_append(monkeypatch):
    store=GameplayEventStore(); ecology=EcologyHazardAuthority(store=store); stream=ecology.ecology_stream_id(region_ref="region:q")
    assert store.append_batch(build_atomic_event_batch(command_id="weather",principal_ref="authority:ecology",stream_id=stream,expected_revision=0,event_specs=[("gameplay.ecology.weather_front.propagated",{"source_region_ref":"region:s","target_region_ref":"region:q","weather_ref":"weather:storm","tick":1})],idempotency_key="weather",causation_id="c",correlation_id="r")).committed
    economy=EconomyAuthorityService(store=store); assert economy.publish_dynamic_quote(command_id="quote",quote_payload={"quote_ref":"quote:q","version":1,"status":"active","unit_price_minor":100},idempotency_key="quote",causation_id="c",correlation_id="r").committed
    source, admission=ecology.admit_weather_front_to_economy_quote(region_ref="region:q",quote_ref="quote:q")
    before=store.export_snapshot()

    def reject_contract(**_kwargs):
        raise GovernedAuthorityContractError("governed_authority_contract_stream_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_contract)
    result=economy.settle_weather_front_quote(source=source,admission=admission,idempotency_key="weather:quote:catalog")

    assert not result.committed and result.failure
    assert result.failure.error_code=="governed_authority_contract_stream_mismatch"
    assert store.export_snapshot()==before

def test_weather_front_quote_stale_ecology_head_is_zero_write():
    store=GameplayEventStore(); ecology=EcologyHazardAuthority(store=store); stream=ecology.ecology_stream_id(region_ref="region:q")
    assert store.append_batch(build_atomic_event_batch(command_id="weather",principal_ref="authority:ecology",stream_id=stream,expected_revision=0,event_specs=[("gameplay.ecology.weather_front.propagated",{"source_region_ref":"region:s","target_region_ref":"region:q","weather_ref":"weather:storm","tick":1})],idempotency_key="weather",causation_id="c",correlation_id="r")).committed
    economy=EconomyAuthorityService(store=store); assert economy.publish_dynamic_quote(command_id="quote",quote_payload={"quote_ref":"quote:q","version":1,"status":"active","unit_price_minor":100},idempotency_key="quote",causation_id="c",correlation_id="r").committed
    source,admission=ecology.admit_weather_front_to_economy_quote(region_ref="region:q",quote_ref="quote:q"); before=store.get_stream_head("gameplay:economy")
    assert store.append_batch(build_atomic_event_batch(command_id="advance",principal_ref="authority:ecology",stream_id=stream,expected_revision=1,event_specs=[("gameplay.ecology.environment.recorded",{"record_ref":"environment:q"})],idempotency_key="advance",causation_id="c",correlation_id="r")).committed
    result=economy.settle_weather_front_quote(source=source,admission=admission,idempotency_key="stale")
    assert not result.committed and result.failure and result.failure.error_code=="weather_quote_source_invalid"
    assert store.get_stream_head("gameplay:economy")==before

def test_weather_quote_admission_cannot_be_reused_for_another_quote():
    store=GameplayEventStore(); ecology=EcologyHazardAuthority(store=store); stream=ecology.ecology_stream_id(region_ref="region:q")
    assert store.append_batch(build_atomic_event_batch(command_id="weather",principal_ref="authority:ecology",stream_id=stream,expected_revision=0,event_specs=[("gameplay.ecology.weather_front.propagated",{"source_region_ref":"region:s","target_region_ref":"region:q","weather_ref":"weather:storm","tick":1})],idempotency_key="weather",causation_id="c",correlation_id="r")).committed
    economy=EconomyAuthorityService(store=store)
    for ref in ("quote:q","quote:other"): assert economy.publish_dynamic_quote(command_id=ref,quote_payload={"quote_ref":ref,"version":1,"status":"active","unit_price_minor":100},idempotency_key=ref,causation_id="c",correlation_id="r").committed
    source,admission=ecology.admit_weather_front_to_economy_quote(region_ref="region:q",quote_ref="quote:q"); source={**source,"quote_ref":"quote:other"}; before=store.get_stream_head("gameplay:economy")
    result=economy.settle_weather_front_quote(source=source,admission=admission,idempotency_key="cross")
    assert not result.committed and result.failure and result.failure.error_code=="weather_quote_admission_required"
    assert store.get_stream_head("gameplay:economy")==before

def test_weather_quote_duplicate_is_idempotent_and_replayable():
    store=GameplayEventStore(); ecology=EcologyHazardAuthority(store=store); stream=ecology.ecology_stream_id(region_ref="region:q")
    assert store.append_batch(build_atomic_event_batch(command_id="weather",principal_ref="authority:ecology",stream_id=stream,expected_revision=0,event_specs=[("gameplay.ecology.weather_front.propagated",{"source_region_ref":"region:s","target_region_ref":"region:q","weather_ref":"weather:storm","tick":1})],idempotency_key="weather",causation_id="c",correlation_id="r")).committed
    economy=EconomyAuthorityService(store=store); assert economy.publish_dynamic_quote(command_id="quote",quote_payload={"quote_ref":"quote:q","version":1,"status":"active","unit_price_minor":100},idempotency_key="quote",causation_id="c",correlation_id="r").committed
    source,admission=ecology.admit_weather_front_to_economy_quote(region_ref="region:q",quote_ref="quote:q"); first=economy.settle_weather_front_quote(source=source,admission=admission,idempotency_key="weather:quote"); duplicate=economy.settle_weather_front_quote(source=source,admission=admission,idempotency_key="weather:quote")
    replay=GameplayProjectionReplay(projector_id="inf3j",projector_version="1"); full=replay.full_replay(store.read_events()); tail=replay.checkpoint_plus_tail_replay(replay.create_checkpoint(()),store.read_events())
    assert first.committed and duplicate.idempotency_status=="duplicate_replayed" and full.succeeded and tail.succeeded and full.projection_hash==tail.projection_hash

def test_weather_quote_duplicate_key_cannot_replay_a_different_admitted_source():
    store=GameplayEventStore(); ecology=EcologyHazardAuthority(store=store); economy=EconomyAuthorityService(store=store)
    for region_ref, quote_ref in (("region:q", "quote:q"), ("region:other", "quote:other")):
        stream=ecology.ecology_stream_id(region_ref=region_ref)
        assert store.append_batch(build_atomic_event_batch(command_id=f"weather:{region_ref}",principal_ref="authority:ecology",stream_id=stream,expected_revision=0,event_specs=[("gameplay.ecology.weather_front.propagated",{"source_region_ref":"region:s","target_region_ref":region_ref,"weather_ref":"weather:storm","tick":1})],idempotency_key=f"weather:{region_ref}",causation_id="c",correlation_id="r")).committed
        assert economy.publish_dynamic_quote(command_id=quote_ref,quote_payload={"quote_ref":quote_ref,"version":1,"status":"active","unit_price_minor":100},idempotency_key=quote_ref,causation_id="c",correlation_id="r").committed
    first_source, first_admission=ecology.admit_weather_front_to_economy_quote(region_ref="region:q",quote_ref="quote:q")
    second_source, second_admission=ecology.admit_weather_front_to_economy_quote(region_ref="region:other",quote_ref="quote:other")
    assert economy.settle_weather_front_quote(source=first_source,admission=first_admission,idempotency_key="weather:quote").committed
    before=store.export_snapshot()
    result=economy.settle_weather_front_quote(source=second_source,admission=second_admission,idempotency_key="weather:quote")
    assert not result.committed and result.failure and result.failure.error_code=="weather_quote_idempotency_conflict"
    assert store.export_snapshot()==before

def test_authority_only_weather_front_cannot_admit_a_project_quote_update():
    store=GameplayEventStore(); ecology=EcologyHazardAuthority(store=store); stream=ecology.ecology_stream_id(region_ref="region:q")
    batch=build_atomic_event_batch(command_id="private-weather",principal_ref="authority:ecology",stream_id=stream,expected_revision=0,event_specs=[("gameplay.ecology.weather_front.propagated",{"source_region_ref":"region:s","target_region_ref":"region:q","weather_ref":"weather:storm","tick":1})],idempotency_key="private-weather",causation_id="c",correlation_id="r")
    private_batch=batch.model_copy(update={"events":[batch.events[0].model_copy(update={"visibility_policy":"authority_only"})]},deep=True)
    assert store.append_batch(private_batch).committed
    source, admission=ecology.admit_weather_front_to_economy_quote(region_ref="region:q",quote_ref="quote:q")
    before=store.export_snapshot()
    assert source is None and admission=="weather_front_quote_source_missing"
    result=EconomyAuthorityService(store=store).settle_weather_front_quote(source={},admission=admission,idempotency_key="private-weather:quote")
    assert not result.committed and result.failure and result.failure.error_code=="weather_quote_source_invalid"
    assert store.export_snapshot()==before
