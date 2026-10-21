"""Event projection cuts and scoped admitted-participant recovery envelopes.

Only the explicitly declared settlement participants have reconstruction contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent, ProjectionCheckpoint, ReplayResult
from app.gameplay.replay import GameplayProjectionReplay


@dataclass(frozen=True)
class ProjectionReplayCut:
    status: Literal["consistent", "incomplete"]
    checkpoint: ProjectionCheckpoint | None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectionReplayTail:
    status: Literal["verified", "incomplete", "divergent"]
    result: ReplayResult | None
    diagnostics: tuple[str, ...] = ()


def capture_replay_cut(*, store: GameplayEventStore, replay: GameplayProjectionReplay,
                       expected_owner_revisions: dict[str, int]) -> ProjectionReplayCut:
    """Read a whole-spine cut without publishing a mixed-revision checkpoint."""
    before_sequence = store.get_last_global_sequence()
    before_heads = store.get_stream_heads()
    if any(before_heads.get(ref, 0) != revision for ref, revision in expected_owner_revisions.items()):
        return ProjectionReplayCut("incomplete", None, ("owner_revision_mismatch",))
    events = store.read_events()
    try:
        checkpoint = replay.create_checkpoint(events)
    except ValueError:
        return ProjectionReplayCut("incomplete", None, ("event_replay_unavailable",))
    after_heads = store.get_stream_heads()
    after_sequence = store.get_last_global_sequence()
    if (before_sequence != after_sequence or before_heads != after_heads
            or checkpoint.last_global_sequence != before_sequence
            or checkpoint.source_revision_vector != before_heads):
        return ProjectionReplayCut("incomplete", None, ("cut_changed_during_capture",))
    return ProjectionReplayCut("consistent", checkpoint)


def replay_cut_tail(*, cut: ProjectionReplayCut, replay: GameplayProjectionReplay,
                    events: list[GameplayEvent], to_global_sequence: int,
                    expected_result_digest: str | None = None) -> ProjectionReplayTail:
    """Validate full-spine tail completeness before invoking the existing decoder."""
    if cut.status != "consistent" or cut.checkpoint is None:
        return ProjectionReplayTail("incomplete", None, ("checkpoint_incomplete",))
    start = cut.checkpoint.last_global_sequence
    if to_global_sequence < start:
        return ProjectionReplayTail("incomplete", None, ("event_tail_bounds_invalid",))
    tail: dict[int, GameplayEvent] = {}
    seen_ids: dict[str, GameplayEvent] = {}
    seen_sequences: dict[int, GameplayEvent] = {}
    checkpoint_ids = set(cut.checkpoint.applied_event_ids)
    for event in events:
        if ((event.global_sequence in seen_sequences and seen_sequences[event.global_sequence] != event)
                or (event.event_id in seen_ids and seen_ids[event.event_id] != event)):
            return ProjectionReplayTail("divergent", None, ("event_tail_conflict",))
        seen_sequences[event.global_sequence] = event
        seen_ids[event.event_id] = event
        if event.global_sequence <= start:
            if event.event_id not in checkpoint_ids:
                return ProjectionReplayTail("divergent", None, ("event_before_checkpoint_unknown",))
            continue
        if event.event_id in checkpoint_ids:
            return ProjectionReplayTail("divergent", None, ("event_tail_conflict",))
        tail[event.global_sequence] = event
    if set(tail) != set(range(start + 1, to_global_sequence + 1)):
        return ProjectionReplayTail("incomplete", None, ("event_tail_gap",))
    result = replay.checkpoint_plus_tail_replay(cut.checkpoint, [tail[seq] for seq in sorted(tail)])
    if not result.succeeded:
        return ProjectionReplayTail("incomplete", None, (result.failure.error_code,))
    if expected_result_digest is not None and result.projection_hash != expected_result_digest:
        return ProjectionReplayTail("divergent", None, ("result_digest_mismatch",))
    return ProjectionReplayTail("verified", result)


# The scoped envelope complements the existing event projection checkpoint. It
# carries recovery inputs and references; it cannot execute a domain operation.
import hashlib
import json
from collections.abc import Callable

_SCOPED_PROJECTOR = "world_runtime.replay@1"
_REQUIRED = {"versions", "batches", "population", "status", "migration", "external_dependencies", "random_context"}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _projection():
    return GameplayProjectionReplay(projector_id="world_runtime.scoped_events", projector_version="1")


def _source(store):
    # Batch inputs and population recovery records do not advance global_sequence.
    # Include every persisted recovery record and receipt in the observation fence.
    value = store.export_snapshot()
    value["projection_checkpoints"] = sorted(
        (row for row in value["projection_checkpoints"] if row["projector_id"] != _SCOPED_PROJECTOR),
        key=lambda row: row["checkpoint_id"])
    return value


def _replay_readable_event(event):
    return event.schema_version == 1 or (
        event.event_type in {
            "gameplay.government.public_milling_notice_recorded",
            "gameplay.character.life_state_changed",
        }
        and event.schema_version == 2
    )


def _manifest(value, batch_refs):
    if not isinstance(value, dict) or not _REQUIRED.issubset(value):
        raise ValueError("replay_participant_missing")
    allowed = _REQUIRED | {"schema_version", "timeline", "profile", "mapping",
        "confirmed_tick", "window_ticks", "owner_revisions", "random_context", "inventory", "social",
        "social_delivery", "presence", "economy_temporal", "ecology_temporal", "resource", "equipment",
        "inventory_domain", "economy_random", "life_state"}
    if set(value) - allowed:
        raise ValueError("replay_participant_scope_mismatch")
    versions = dict(participant_manifest=1, batch_input=1, batch_operation=1,
                    population_recovery=1, status_events=1, migration_events=1)
    actual_versions = value.get("versions")
    # Captures written before the Economy temporal participant existed remain
    # readable when they do not claim that participant. New captures always
    # carry its explicit decoder version.
    accepted_versions = []
    optional_versions = ("economy_temporal", "ecology_temporal", "social_delivery", "presence", "resource", "equipment",
                         "inventory_domain", "economy_random", "life_state")
    for mask in range(1 << len(optional_versions)):
        candidate = dict(versions)
        for index, key in enumerate(optional_versions):
            if mask & (1 << index):
                candidate[key] = 1
        accepted_versions.append(candidate)
    if value.get("schema_version") != 1 or actual_versions not in accepted_versions:
        raise ValueError("replay_decoder_unsupported")
    if ("resource" in value) != ("resource" in actual_versions):
        raise ValueError("replay_resource_participant_version_missing")
    if ("equipment" in value) != ("equipment" in actual_versions):
        raise ValueError("replay_equipment_participant_version_missing")
    if ("inventory_domain" in value) != ("inventory_domain" in actual_versions):
        raise ValueError("replay_inventory_domain_participant_version_missing")
    if ("economy_random" in value) != ("economy_random" in actual_versions):
        raise ValueError("replay_economy_random_participant_version_missing")
    if ("life_state" in value) != ("life_state" in actual_versions):
        raise ValueError("replay_life_state_participant_version_missing")
    if any(value[name].get("schema_version") != 1 for name in ("population", "status", "migration")):
        raise ValueError("replay_decoder_unsupported")
    if (not value["versions"] or not value["population"] or not value["status"]
            or not value["migration"] or set(value["batches"]) != set(batch_refs)):
        raise ValueError("replay_participant_missing")
    return json.loads(json.dumps(value))


@dataclass(frozen=True)
class ScopedReplayCheckpoint:
    status: Literal["consistent", "incomplete"]
    checkpoint: ProjectionCheckpoint | None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplayTail:
    status: Literal["verified", "incomplete", "divergent"]
    payload: dict | None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScopedReplayResult:
    status: Literal["verified", "incomplete", "divergent"]
    result: dict | None
    diagnostics: tuple[str, ...] = ()


def _observe(store, participants, refs):
    before = _hash(_source(store))
    manifest = _manifest(participants(), refs)
    events = store.read_events()
    if any(not _replay_readable_event(event) for event in events):
        raise ValueError("replay_decoder_unsupported")
    projection = _projection().create_checkpoint(events)
    again = _manifest(participants(), refs)
    if before != _hash(_source(store)) or manifest != again:
        raise ValueError("cut_changed_during_capture")
    return manifest, events, projection


def capture_scoped_checkpoint(*, store, checkpoint_ref, batch_refs, participants: Callable[[], dict]):
    if not checkpoint_ref or not batch_refs or len(set(batch_refs)) != len(batch_refs):
        return ScopedReplayCheckpoint("incomplete", None, ("replay_scope_invalid",))
    try:
        # Same lock as append and checkpoint persistence. Application state is
        # serialized by RuntimeExecution; the second observation catches reentrant
        # mutations as well as non-event input changes.
        with store._lock:
            manifest, events, projection = _observe(store, participants, batch_refs)
            payload = dict(version=1, batch_refs=sorted(batch_refs), participants=manifest,
                           event_checkpoint=projection.model_dump(mode="json"),
                           prefix=[_hash(e.model_dump(mode="json")) for e in events])
            checkpoint = ProjectionCheckpoint(
                checkpoint_id=checkpoint_ref, projector_id=_SCOPED_PROJECTOR, projector_version="1",
                projection_schema_version=1, source_revision_vector=projection.source_revision_vector,
                last_global_sequence=projection.last_global_sequence, state=payload,
                applied_event_ids=projection.applied_event_ids, projection_hash=_hash(payload))
            prior = store.get_projection_checkpoint(checkpoint_ref)
            if prior is not None and prior != checkpoint:
                raise ValueError("replay_checkpoint_identity_conflict")
            store.save_projection_checkpoint(checkpoint)
            return ScopedReplayCheckpoint("consistent", checkpoint)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        return ScopedReplayCheckpoint("incomplete", None, (str(exc),))


def _load(store, ref):
    saved = store.get_projection_checkpoint(ref)
    if saved is None:
        raise ValueError("replay_checkpoint_missing")
    if (saved.projector_id != _SCOPED_PROJECTOR or saved.projector_version != "1"
            or saved.projection_schema_version != 1 or saved.state.get("version") != 1):
        raise ValueError("replay_decoder_unsupported")
    if saved.projection_hash != _hash(saved.state):
        raise ValueError("replay_checkpoint_digest_conflict")
    _manifest(saved.state["participants"], saved.state["batch_refs"])
    projection = ProjectionCheckpoint.model_validate(saved.state["event_checkpoint"])
    if (projection.last_global_sequence != saved.last_global_sequence
            or projection.source_revision_vector != saved.source_revision_vector
            or projection.applied_event_ids != saved.applied_event_ids):
        raise ValueError("replay_checkpoint_digest_conflict")
    return saved, projection


def _result_digest(projection, manifest):
    return _hash(dict(state=projection.state, revisions=projection.source_revision_vector,
                      sequence=projection.last_global_sequence, participants=manifest))


def capture_scoped_tail(*, store, checkpoint_ref, participants: Callable[[], dict]):
    try:
        with store._lock:
            saved, projection = _load(store, checkpoint_ref)
            manifest, events, target = _observe(store, participants, saved.state["batch_refs"])
            start = saved.last_global_sequence
            if (len(events) < start or [_hash(e.model_dump(mode="json")) for e in events[:start]] != saved.state["prefix"]):
                raise ValueError("replay_prefix_conflict")
            payload = dict(version=1, checkpoint_digest=saved.projection_hash,
                           from_sequence=start, to_sequence=target.last_global_sequence,
                           from_revisions=projection.source_revision_vector,
                           to_revisions=target.source_revision_vector,
                           events=[event.model_dump(mode="json") for event in events[start:]],
                           participants=manifest, result_digest=_result_digest(target, manifest))
            payload["digest"] = _tail_hash(payload)
            return ReplayTail("verified", payload)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        return ReplayTail("incomplete", None, (str(exc),))


def _ordered_events(rows):
    by_seq, by_id = {}, {}
    for row in rows:
        event = GameplayEvent.model_validate(row)
        if ((event.global_sequence in by_seq and by_seq[event.global_sequence] != event)
                or (event.event_id in by_id and by_id[event.event_id] != event)):
            raise ValueError("event_tail_conflict")
        by_seq[event.global_sequence] = event
        by_id[event.event_id] = event
    return [by_seq[seq] for seq in sorted(by_seq)]


def _tail_hash(tail):
    value = {key: val for key, val in tail.items() if key != "digest"}
    value["events"] = [event.model_dump(mode="json") for event in _ordered_events(value["events"])]
    return _hash(value)


def replay_scoped_tail(*, store, checkpoint_ref, tail, expected_result_digest=None,
                       inventory_authority=None, social_authority=None, social_delivery_authority=None,
                       presence_authority=None):
    try:
        with store._lock:
            saved, projection = _load(store, checkpoint_ref)
            if tail.get("version") != 1:
                raise ValueError("replay_decoder_unsupported")
            manifest = _manifest(tail["participants"], saved.state["batch_refs"])
            saved_manifest = saved.state["participants"]
            if ("inventory" in saved_manifest) != ("inventory" in manifest):
                raise ValueError("replay_participant_scope_conflict")
            # A tail must replay the exact checkpoint participant set.  Checking
            # only status actors and inventory allows a producer to silently
            # omit or add another admitted participant while preserving the
            # aggregate digest shape.
            if set(manifest) != set(saved_manifest):
                raise ValueError("replay_participant_scope_conflict")
            if (set(manifest["status"]["actors"]) != set(saved.state["participants"]["status"]["actors"])
                    or any(manifest["timeline"][key] != saved.state["participants"]["timeline"][key]
                           for key in ("timeline_id", "world_scope_ref", "advancement_owner_ref"))):
                raise ValueError("replay_participant_scope_conflict")
            if manifest["versions"] != saved.state["participants"]["versions"]:
                raise ValueError("replay_decoder_unsupported")
            if tail["digest"] != _tail_hash(tail):
                raise ValueError("replay_tail_digest_conflict")
            if (tail["checkpoint_digest"] != saved.projection_hash
                    or tail["from_sequence"] != saved.last_global_sequence
                    or tail["from_revisions"] != projection.source_revision_vector):
                raise ValueError("replay_checkpoint_digest_conflict")
            end = tail["to_sequence"]
            events = _ordered_events(tail["events"])
            if [e.global_sequence for e in events] != list(range(saved.last_global_sequence + 1, end + 1)):
                raise ValueError("event_tail_gap")
            if any(not _replay_readable_event(event) for event in events):
                raise ValueError("replay_decoder_unsupported")
            source = store.read_events()[:end]
            prefix = source[:saved.last_global_sequence]
            if ([_hash(e.model_dump(mode="json")) for e in prefix] != saved.state["prefix"]
                    or source[saved.last_global_sequence:] != events):
                raise ValueError("replay_source_conflict")
            from .replay_participants import (
                validate_equipment_checkpoint_tail, validate_inventory_checkpoint_tail,
                validate_life_state_checkpoint_tail, validate_resource_checkpoint_tail,
                validate_saved_participants,
            )
            validate_saved_participants(
                store, saved.state["participants"], saved.state["batch_refs"],
                boundary_sequence=saved.last_global_sequence,
                inventory_authority=inventory_authority, social_authority=social_authority,
                social_delivery_authority=social_delivery_authority, presence_authority=presence_authority,
            )
            rebuilt = validate_saved_participants(
                store, manifest, saved.state["batch_refs"], boundary_sequence=end,
                inventory_authority=inventory_authority, social_authority=social_authority,
                social_delivery_authority=social_delivery_authority, presence_authority=presence_authority,
            )
            validate_resource_checkpoint_tail(store, saved_manifest.get("resource"),
                manifest.get("resource"), saved.last_global_sequence, end)
            validate_life_state_checkpoint_tail(store, saved_manifest.get("life_state"),
                manifest.get("life_state"), saved.last_global_sequence, end)
            validate_equipment_checkpoint_tail(store, saved_manifest.get("equipment"),
                manifest.get("equipment"), saved.last_global_sequence, end)
            validate_inventory_checkpoint_tail(store, inventory_authority,
                saved_manifest.get("inventory_domain"), manifest.get("inventory_domain"),
                saved.last_global_sequence, end)
            result = replay_cut_tail(cut=ProjectionReplayCut("consistent", projection),
                                     replay=_projection(), events=events, to_global_sequence=end)
            if result.status != "verified":
                return ScopedReplayResult(result.status, None, result.diagnostics)
            full = _projection().full_replay(source)
            if not full.succeeded:
                raise ValueError("replay_decoder_unsupported")
            digest = _result_digest(result.result, manifest)
            full_digest = _result_digest(full, rebuilt)
            if (digest != full_digest or digest != tail["result_digest"]
                    or result.result.source_revision_vector != tail["to_revisions"]
                    or expected_result_digest is not None and digest != expected_result_digest):
                raise ValueError("replay_result_digest_conflict")
            return ScopedReplayResult("verified", dict(result_digest=digest, full_digest=full_digest,
                participants=manifest, event_projection=result.result.model_dump(mode="json")))
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        code = str(exc)
        divergent = any(word in code for word in ("conflict", "mismatch"))
        return ScopedReplayResult("divergent" if divergent else "incomplete", None, (code,))
