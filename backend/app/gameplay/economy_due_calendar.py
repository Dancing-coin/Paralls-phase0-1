"""Authored Economy due-calendar source and Population opening caller.

This module is designed and implemented for stage three.  A calendar entry is
content, not a clock: the Population cadence remains the sole advancement
authority and the Economy owner remains the sole obligation writer.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import yaml
from typing import Iterable

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.world_runtime.temporal_contracts import verify_temporal_authorization


@dataclass(frozen=True)
class EconomyDueCalendarEntry:
    calendar_ref: str
    period_ref: str
    due_tick: int
    timeline_id: str
    source_revision: str
    valid_from_tick: int
    valid_until_tick: int
    source_digest: str = ""

    def __post_init__(self) -> None:
        if (not self.calendar_ref or not self.period_ref or not self.timeline_id
                or not self.source_revision
                or any(type(value) is not int for value in (self.due_tick, self.valid_from_tick, self.valid_until_tick))
                or self.due_tick < 0 or self.valid_from_tick < 0
                or self.valid_until_tick < self.valid_from_tick
                or not self.valid_from_tick <= self.due_tick <= self.valid_until_tick):
            raise ValueError("economy_due_calendar_entry_invalid")


class EconomyDueCalendarRegistry:
    """Versioned authored entries; unknown or ambiguous refs fail closed."""

    def __init__(self, entries: Iterable[EconomyDueCalendarEntry]):
        self._entries: dict[tuple[str, str], EconomyDueCalendarEntry] = {}
        for entry in entries:
            key = (entry.calendar_ref, entry.period_ref)
            if key in self._entries:
                raise ValueError("economy_due_calendar_duplicate")
            self._entries[key] = entry

    @classmethod
    def from_entries(cls, entries: Iterable[dict[str, object]]) -> "EconomyDueCalendarRegistry":
        return cls(EconomyDueCalendarEntry(**entry) for entry in entries)

    @classmethod
    def from_directory(cls, directory: str | Path) -> "EconomyDueCalendarRegistry":
        root = Path(directory)
        if not root.is_dir():
            raise ValueError("economy_due_calendar_directory_missing")
        entries: list[EconomyDueCalendarEntry] = []
        for path in sorted(root.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("economy_due_calendar_source_invalid")
            required = {"calendar_ref", "calendar_revision", "period_ref", "due_tick", "timeline_id",
                        "valid_from_tick", "valid_until_tick"}
            if set(raw) != required:
                raise ValueError("economy_due_calendar_fields_invalid")
            canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
            entries.append(EconomyDueCalendarEntry(
                calendar_ref=str(raw["calendar_ref"]), period_ref=str(raw["period_ref"]),
                due_tick=raw["due_tick"], timeline_id=str(raw["timeline_id"]),
                source_revision=str(raw["calendar_revision"]), valid_from_tick=raw["valid_from_tick"],
                valid_until_tick=raw["valid_until_tick"],
                source_digest="sha256:" + hashlib.sha256(canonical).hexdigest(),
            ))
        if not entries:
            raise ValueError("economy_due_calendar_registry_empty")
        registry = cls(entries)
        registry._directory = root
        return registry

    def resolve(self, *, calendar_ref: str, period_ref: str, timeline_id: str, at_tick: int) -> EconomyDueCalendarEntry:
        entry = self._entries.get((calendar_ref, period_ref))
        if entry is None:
            raise KeyError("economy_due_calendar_missing")
        if entry.timeline_id != timeline_id or not entry.valid_from_tick <= at_tick <= entry.valid_until_tick:
            raise ValueError("economy_due_calendar_scope_invalid")
        return entry

    def reload(self) -> "EconomyDueCalendarRegistry":
        directory = getattr(self, "_directory", None)
        return type(self).from_directory(directory) if directory is not None else self


class PopulationEconomyTaxCaller:
    """Population-confirmed caller for the existing Economy tax opener."""

    def __init__(self, *, store: GameplayEventStore, authority: EconomyAuthorityService,
                 registry: EconomyDueCalendarRegistry, population_driver):
        self.store, self.authority, self.registry, self.population_driver = store, authority, registry, population_driver

    def _pins(self) -> tuple[int, str, dict[str, object], str, dict[str, int]]:
        driver = self.population_driver
        if driver.world_runtime.is_paused():
            raise ValueError("economy_cadence_unconfirmed")
        pins = getattr(getattr(driver, "publish_window", None), "confirmed_time_pins", None)
        pins = pins() if callable(pins) else pins
        tick = getattr(driver, "current_tick", None)
        timeline = getattr(getattr(getattr(driver, "clock", None), "timeline", None), "timeline_id", None)
        if not isinstance(pins, dict) or type(tick) is not int or not isinstance(timeline, str):
            raise ValueError("economy_cadence_unconfirmed")
        if not verify_temporal_authorization(pins=pins, expected_participant="actor_gameplay.economy_domain",
                                              expected_cutoff=tick, expected_timeline=timeline, grant_key="economy"):
            raise ValueError("economy_temporal_authorization_rejected")
        cadence_id = getattr(getattr(driver.world_runtime, "latest_confirmation", None), "cadence_id", None)
        if not isinstance(cadence_id, str):
            cadence_id = getattr(getattr(driver.world_runtime, "last_population_confirmation", None), "cadence_id", None)
        receipt = self.store.get_by_idempotency("world_runtime.cadence", f"population-runtime:{cadence_id}") if cadence_id else None
        if receipt is None or not receipt.committed or not receipt.committed_event_ids:
            raise ValueError("economy_cadence_receipt_invalid")
        transaction = self.store.get_transaction(receipt.transaction_id)
        if (transaction is None or transaction.idempotency_record.principal_ref != "world_runtime.cadence"
                or tuple(event.event_id for event in transaction.events) != tuple(receipt.committed_event_ids)):
            raise ValueError("economy_cadence_receipt_invalid")
        event = self.store.get_event(receipt.committed_event_ids[0])
        payload = event.payload
        cadence, stored_pins, digest = payload.get("cadence"), payload.get("time_pins"), payload.get("record_digest")
        expected_digest = "sha256:" + hashlib.sha256(json.dumps(
            {key: value for key, value in payload.items() if key != "record_digest"},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if (event.event_type != "population.cadence.admitted"
                or event.stream_id != f"population-cadence:{driver.world_runtime.mode.world_ref}"
                or event.transaction_id != transaction.transaction_id or event.visibility_policy != "project"
                or not isinstance(cadence, dict) or cadence.get("cadence_id") != cadence_id
                or cadence.get("window_end") != tick or stored_pins != pins or digest != expected_digest):
            raise ValueError("economy_cadence_receipt_invalid")
        revocation_stream = f"population-cadence-revocation:{driver.world_runtime.mode.world_ref}"
        revocation_revision = self.store.get_stream_head(revocation_stream)
        if any(item.event_type == "population.cadence.revoked" and item.payload.get("cadence_id") == cadence_id
               for item in self.store.read_stream(revocation_stream)):
            raise ValueError("economy_cadence_revoked")
        return tick, timeline, pins, cadence_id, {
            event.stream_id: event.stream_revision, revocation_stream: revocation_revision,
        }

    def open(self, *, tax_due_event_id: str, command_id: str, idempotency_key: str,
             causation_id: str, correlation_id: str):
        try:
            tick, timeline, pins, cadence_id, read_set = self._pins()
            source = self.store.get_event(tax_due_event_id)
            if source.stream_id != "gameplay:economy" or source.event_type != "gameplay.economy.tax_due_recorded":
                raise ValueError("economy_tax_source_invalid")
            calendar_ref = source.payload.get("due_calendar_ref")
            period_ref = source.payload.get("period_ref")
            if not isinstance(calendar_ref, str) or not isinstance(period_ref, str):
                raise ValueError("economy_due_calendar_missing")
            entry = self.registry.resolve(calendar_ref=calendar_ref, period_ref=period_ref,
                                          timeline_id=timeline, at_tick=tick)
            current = self.registry.reload().resolve(calendar_ref=calendar_ref, period_ref=period_ref,
                                                      timeline_id=timeline, at_tick=tick)
            if current != entry:
                raise ValueError("economy_due_calendar_changed")
            read_set["gameplay:economy"] = self.store.get_stream_head("gameplay:economy")
            expected_revision = self.store.get_stream_head("gameplay:economy")
            result = self.authority.open_tax_obligation(
                command_id=command_id, tax_due_event_id=tax_due_event_id, due_tick=entry.due_tick,
                idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id,
                expected_revision=expected_revision, due_calendar_ref=entry.calendar_ref,
                calendar_source_revision=entry.source_revision, calendar_timeline_id=entry.timeline_id,
                calendar_source_digest=entry.source_digest,
                temporal_pins=pins,
                temporal_read_set_revisions=read_set,
                cadence_id=cadence_id,
            )
            return result
        except KeyError as exc:
            return self.authority._rejected_append(command_id, str(exc).strip("'\"") or "economy_tax_source_missing")
        except (TypeError, ValueError) as exc:
            return self.authority._rejected_append(command_id, str(exc))


__all__ = ["EconomyDueCalendarEntry", "EconomyDueCalendarRegistry", "PopulationEconomyTaxCaller"]
