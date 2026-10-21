"""Bounded Population advancement-owner activation, using the existing authority store.

Each Status owner commits independently. The prepared record freezes recovery inputs;
it is not a transaction across owners. Advancement is fenced until completion.
"""
from dataclasses import asdict, replace
from fractions import Fraction
from hashlib import sha256
import json

from app.gameplay.status_tags import StatusTagTemporalContext
from .temporal_contracts import ClockMapping, SimulationTime, TemporalProfile


def _dump(value):
    return json.loads(json.dumps(asdict(value), default=str))


def _profile(value):
    value = dict(value, step_duration=Fraction(value["step_duration"]),
                 supported_clock_mappings=tuple(value["supported_clock_mappings"]),
                 compatibility_constraints=tuple(value["compatibility_constraints"]))
    return TemporalProfile(**value)


def _mapping(value):
    return ClockMapping(**dict(value, ratio=Fraction(value["ratio"]),
                               valid_source_interval=tuple(value["valid_source_interval"])))


def _stream(driver):
    return f"temporal-activation:{driver.clock.timeline.timeline_id}"


def _append(driver, key, kind, payload):
    store = driver.world_runtime.store
    command = f"{_stream(driver)}:{key}:{kind}"
    stream = _stream(driver)
    digest = "sha256:" + sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    result = store.append_batch({
        "transaction_id": f"tx:{command}", "command_id": command,
        "expected_stream_revisions": {stream: store.get_stream_head(stream)},
        "pinned_revisions": {},
        "events": [{"event_id": f"evt:{command}", "event_type": f"world_runtime.time_migration.{kind}",
                    "schema_version": 1, "stream_id": stream, "stream_revision": 0, "global_sequence": 0,
                    "transaction_id": f"tx:{command}", "command_id": command,
                    "causation_id": key, "correlation_id": key, "visibility_policy": "authority_only",
                    "payload": payload}],
        "idempotency_record": {"principal_ref": "world_runtime.time_migration",
                               "idempotency_key": command, "payload_digest": digest},
        "outbox_entries": [], "result_digest": digest, "projection_refresh_hints": []})
    if not result.committed:
        raise ValueError(result.failure.error_code if result.failure else "temporal_migration_commit_failed")
    return result


def _context(driver, profile, mapping, tick):
    coordinate = Fraction(tick) / profile.step_duration
    if coordinate.denominator != 1:
        raise ValueError("temporal_activation_precision_invalid")
    return StatusTagTemporalContext(
        now=SimulationTime(driver.clock.timeline.timeline_id, int(coordinate), Fraction(tick)),
        mapping=mapping, profile_revision=profile.revision, source_revision=mapping.revision,
        evidence_freshness=0, step_duration=profile.step_duration)


def restore_clock(driver):
    """Restore committed coordinates before comparing the latest cadence pins."""
    records = driver.world_runtime.store.read_stream(_stream(driver))
    saved_pins = getattr(driver.publish_window, "confirmed_time_pins", None)
    if callable(saved_pins):
        saved_pins = saved_pins()
    if saved_pins is not None and saved_pins.get("step_duration") != "1/1":
        if not records or not any(event.event_type.endswith(".committed") for event in records):
            raise ValueError("population_time_migration_required")
    for event in records:
        if event.event_type != "world_runtime.time_migration.committed":
            continue
        request = event.payload["request"]
        profile, mapping = _profile(request["profile"]), _mapping(request["mapping"])
        coordinate = Fraction(driver.current_tick) / profile.step_duration
        if coordinate.denominator != 1:
            raise ValueError("temporal_activation_precision_invalid")
        driver.clock.temporal_profile = profile
        driver.mapping = mapping
        driver.clock.tick = int(coordinate)
        driver.clock.timeline = replace(
            driver.clock.timeline, current_step=int(coordinate), profile_ref=profile.profile_id,
            profile_revision=profile.revision,
            authoritative_revision=request["expected_timeline_revision"] + 1)
    driver.migration_pending = bool(records and records[-1].event_type.endswith(".prepared"))
    if saved_pins is not None and saved_pins.get("step_duration") != "1/1":
        if any(saved_pins.get(key) != value for key, value in driver._time_pins(driver.current_tick).items()):
            raise ValueError("population_time_mapping_stale")


def _bindings(consumer, driver, request):
    old = _profile(request["old_profile"])
    old_mapping = _mapping(request["old_mapping"])
    for actor in request["actors"]:
        binding = consumer.bindings.get(actor)
        if binding is None or (binding.profile_revision, binding.mapping_revision,
                               binding.step_duration) != (
                old.revision, old_mapping.revision, f"{old.step_duration.numerator}/{old.step_duration.denominator}"):
            raise ValueError("status_time_binding_mismatch")
        pins = driver._time_pins(driver.current_tick)
        consumer.bindings[actor] = binding.model_copy(update={
            key: pins[key] for key in binding.model_fields if key in pins})


def _finish(driver, consumer, request):
    old, new = _profile(request["old_profile"]), _profile(request["profile"])
    old_mapping, mapping = _mapping(request["old_mapping"]), _mapping(request["mapping"])
    tick = request["boundary_tick"]
    old_context = _context(driver, old, old_mapping, tick)
    new_context = _context(driver, new, mapping, tick)
    receipts = {}
    for actor in request["actors"]:
        receipt = consumer.service.migrate_time(
            actor_ref=actor, migration_id=request["migration_id"],
            expected_revision=request["expected_owner_revisions"][f"gameplay:status_tags:{actor}"],
            old_context=old_context, new_context=new_context,
            old_profile_revision=old.revision, new_profile_revision=new.revision,
            old_step_duration=old.step_duration, new_step_duration=new.step_duration,
            boundary_tick=tick)
        receipts[actor] = receipt.model_dump(mode="json")
    result = _append(driver, request["migration_id"], "committed", {"request": request, "owner_receipts": receipts})
    driver.activate_migration(new, mapping, boundary=request["boundary"])
    _bindings(consumer, driver, request)
    driver.migration_pending = False
    return result


def recover_migrations(driver, consumer):
    records = driver.world_runtime.store.read_stream(_stream(driver))
    for event in records:
        if event.event_type.endswith(".committed"):
            _bindings(consumer, driver, event.payload["request"])
    if records and records[-1].event_type.endswith(".prepared"):
        return _finish(driver, consumer, records[-1].payload)


def submit_migration(driver, consumer, *, migration_id, advancement_owner_ref, boundary,
                     expected_timeline_revision, expected_owner_revisions, profile, mapping):
    if not migration_id or mapping is None:
        raise ValueError("temporal_migration_mapping_required")
    identity = dict(migration_id=migration_id, advancement_owner_ref=advancement_owner_ref,
                    boundary=boundary, expected_timeline_revision=expected_timeline_revision,
                    expected_owner_revisions=dict(expected_owner_revisions),
                    profile=_dump(profile), mapping=_dump(mapping))
    records = driver.world_runtime.store.read_stream(_stream(driver))
    for event in records:
        request = event.payload["request"] if event.event_type.endswith(".committed") else event.payload
        if request["migration_id"] == migration_id:
            if any(request[key] != value for key, value in identity.items()):
                raise ValueError("temporal_migration_identity_reused")
            if event.event_type.endswith(".committed"):
                if driver.clock.temporal_profile.revision != request["profile"]["revision"]:
                    new, mapping = _profile(request["profile"]), _mapping(request["mapping"])
                    driver.activate_migration(new, mapping, boundary=request["boundary"])
                    _bindings(consumer, driver, request)
                    driver.migration_pending = False
                return driver.world_runtime.store.get_by_idempotency(
                    "world_runtime.time_migration", f"{_stream(driver)}:{migration_id}:committed")
        elif event.event_type.endswith(".committed"):
            raise ValueError("temporal_migration_sequence_not_admitted")
    if driver.migration_pending:
        if records[-1].payload["migration_id"] != migration_id:
            raise ValueError("temporal_migration_pending")
        return _finish(driver, consumer, records[-1].payload)
    old = driver.clock.temporal_profile
    old_mapping = driver.mapping
    if advancement_owner_ref != driver.clock.timeline.advancement_owner_ref:
        raise ValueError("simulation_clock_advancement_owner_mismatch")
    if expected_timeline_revision != driver.clock.timeline.authoritative_revision:
        raise ValueError("temporal_timeline_revision_stale")
    if boundary != "window" or driver.current_tick % driver.window_size or driver.world_runtime.is_paused():
        raise ValueError("temporal_activation_boundary_mismatch")
    if profile.revision == old.revision or mapping.revision == old_mapping.revision:
        raise ValueError("temporal_migration_revision_required")
    # This entry admits only a duration change, never a new dimension/policy/source.
    if replace(profile, revision=old.revision, step_duration=old.step_duration,
               rounding_policy=old.rounding_policy) != old or profile.rounding_policy != "ceil":
        raise ValueError("temporal_migration_profile_not_admitted")
    if replace(mapping, revision=old_mapping.revision, target_profile_revision=old_mapping.target_profile_revision,
               ratio=old_mapping.ratio) != old_mapping or mapping.target_profile_revision != profile.revision \
            or mapping.ratio != 1 / profile.step_duration:
        raise ValueError("temporal_migration_mapping_not_admitted")
    _context(driver, profile, mapping, driver.current_tick)
    if (Fraction(driver.window_size) / profile.step_duration).denominator != 1:
        raise ValueError("temporal_window_precision_invalid")
    actors = sorted(actor for actor, binding in consumer.bindings.items() if binding is not None)
    if len(actors) != 1 or set(expected_owner_revisions) != {f"gameplay:status_tags:{actor}" for actor in actors}:
        raise ValueError("temporal_migration_scope_invalid")
    for actor in actors:
        context = consumer.context(driver, actor)
        stream = f"gameplay:status_tags:{actor}"
        if driver.world_runtime.store.get_stream_head(stream) != expected_owner_revisions[stream]:
            raise ValueError("status_tag_revision_stale")
        projection = consumer.service.projector.rebuild(actor, driver.world_runtime.store.read_stream(stream))
        for instance in projection.active_instances.values():
            if instance.expiry:
                context.validate_reference(instance.expiry)
    request = dict(identity, old_profile=_dump(old), old_mapping=_dump(old_mapping),
                   actors=actors, boundary_tick=driver.current_tick)
    _append(driver, migration_id, "prepared", request)
    driver.migration_pending = True
    return _finish(driver, consumer, request)
