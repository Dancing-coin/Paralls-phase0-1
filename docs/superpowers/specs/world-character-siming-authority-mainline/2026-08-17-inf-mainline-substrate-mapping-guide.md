# INF Mainline and Substrate Mapping Guide

Status: `active terminology and execution guide`

## Purpose

INF work uses two coordinates. They are complementary, not two competing work
plans. This guide is the canonical interpretation when a package name appears
as both an INF domain label and a reusable-contract label.

## Coordinate A: Mainline Domain

| Domain | Mainline responsibility |
| --- | --- |
| `INF-1` | effect/state lifecycle and semantic owner routing |
| `INF-2` | scheduled obligation lifecycle and settlement |
| `INF-3` | ecology evolution and ecology-to-owner consequences |
| `INF-4` | batch/branch simulation and promotion boundary |

## Coordinate B: Reusable Contract Substrate

| Canonical package name | Primary domain | Reusable responsibility | Current state |
| --- | --- | --- | --- |
| `INF-C1 (INF-1)` | `INF-1` | typed state-transition proposal | implemented and independently verified |
| `INF-C2 (INF-2)` | `INF-2` | closed obligation lifecycle contract | implemented and independently verified |
| `INF-C3 (INF-2)` | `INF-2` | owner-fragment batch and append-derived receipt recipe | implemented and independently verified |
| `INF-C4 (INF-3)` | `INF-3` | finite ecology consumer admission check | implemented and independently verified |
| `INF-C5 (INF-4)` | `INF-4` | deterministic fixed-base branch replay contract | implemented and independently verified |

`INF-Cn` is the canonical package label in new prose, reports, prompts and
Harness descriptions. The parenthesized `INF-n` identifies the mainline domain
that owns the primary integration.

## Historical File Names

Existing file paths such as `inf-1/...inf-1c1...`, `inf-2/...inf-2c2...` and
`inf-2/...inf-2c3...` remain valid evidence locators. They do not create a
second package sequence. Do not infer that `INF-2C2` means "the second phase of
INF-2"; it is the historical filename for canonical package `INF-C2 (INF-2)`.

Do not rename existing evidence files solely for terminology cleanup. New
documents should use the canonical label in headings and state their primary
domain explicitly.

## Execution Rule

Before adding a new domain owner row, first check the substrate table:

1. Confirm whether the needed reusable layer is already complete.
2. If it is not complete, finish that layer with RED tests, focused Harness,
   replay/privacy/revision/zero-write evidence and docs synchronization.
3. If it is complete, add only an existing-owner row with an explicit owner,
   stream, event family, scoped projection, revision/idempotency rule, receipt
   and replay reader.

As of this guide, C1-C5 are complete. No repeat implementation of INF-2 C2/C3
or INF-3 C4 is authorized. Further domain rows still require their own
existing-owner contract and independent evidence.

## Authority Boundary

All formal writes remain:

`existing authority -> GameplayCommandEnvelope / SettlementPlan -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection`.

The substrate packages are pure/read-only contract layers. They never create a
second runtime, event store, scheduler, truth owner or generic writer.
