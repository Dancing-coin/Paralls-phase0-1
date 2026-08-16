# INF-3E Ecology Weather-Front Fanout Design

Status: `implemented and verified 2026-08-15; bounded Ecology-only fanout`

Evidence: `.harness/verification/infra-ecology-weather-front-fanout-report.json`;
focused/dependent suites, docs and continuation gates, `git diff --check`, and
full `python -m pytest -q` (`3059 passed`) passed on 2026-08-15.

## Scope

INF-3E adds one bounded, caller-driven, Ecology-only fanout operation to the
existing `EcologyHazardAuthority`. A root region may copy its committed
project-visible weather to one through three explicitly named, symmetric
adjacent regions in one atomic batch. No target belongs to another domain and
no path traversal is inferred.

## Contract

| Item | Contract |
| --- | --- |
| Owner | existing `authority:ecology` / `EcologyHazardAuthority` |
| Streams | root and target `gameplay:ecology:{region_ref}` streams only |
| Policy | closed `policy:ecology_weather_front_fanout@1`, `max_targets=3` |
| Events | existing `gameplay.ecology.weather_front.propagated`, `gameplay.ecology.environment.recorded` |
| Projection | existing regional projection plus event-derived `frontier_edges`; legacy `frontiers` remains a latest-per-source compatibility view |
| Receipt | result of the sole `GameplayEventStore.append_batch()` |

The exact expected revision vector must contain precisely the root and all
listed target streams. The root fragment contains one frontier event per
target; each target fragment contains only its existing environment record.
All fragments are authored by the existing Ecology owner and merge into one
append batch.

## Admission and Evidence

Input must be project-visible, root/target refs must be unique, target count
must be one through three, records must exist, and every root-target pair must
be canonically symmetric. Exact duplicates replay; changed duplicates, stale
vectors, non-neighbor/duplicate/over-budget targets and privacy failures are
zero-write. Focused tests and Harness selectors separately cover success,
projection, idempotency, rejection, outbox and full/checkpoint-tail replay.

## Non-goals

This is not arbitrary graph traversal, multi-round fanout, autonomous weather,
a consumer edge, hazard propagation, retry/compensation, or a non-Ecology
write. The two existing Construction consumer edges remain the only admitted
cross-domain Ecology edges.
