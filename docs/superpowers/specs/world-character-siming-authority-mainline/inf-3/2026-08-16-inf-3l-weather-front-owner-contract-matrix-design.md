# INF-3L Weather-Front Owner-Contract Matrix

Status: `implemented and verified 2026-08-16`

## Purpose

INF-3 already contains three independently verified weather-front consumer
edges, but their admission checks are distributed. INF-3L records the exact
existing target-owner contracts in the immutable governed authority catalog and
makes the previously ungated Construction and Economy owners validate their
row before constructing their existing batches.

This forms a finite, source-controlled matrix over existing owners. It is not
a caller registry, a generic fanout engine, a cross-domain coordinator, or a
new Ecology writer.

## Owner Contract Matrix

| Contract | Existing target owner | Target stream/event | Scope, receipt, replay |
| --- | --- | --- | --- |
| `inf:weather-front-construction-maintenance@1` | `ConstructionProductionAuthority` | `gameplay:construction_production:{facility_ref}` / `gameplay.construction_production.maintenance_obligation_created` | project; one owner `append_batch()` result; existing `GameplayProjectionReplay` |
| `inf:weather-front-organization-supply@1` | `OrganizationAuthority` | `gameplay:organization:{organization_ref}` / `gameplay.organization.commerce_commitment_accepted` | project; one owner result; Organization commitment projection |
| `inf:weather-front-economy-quote@1` | `EconomyAuthorityService` | `gameplay:economy` / `gameplay.economy.dynamic_quote_published` | project; one owner result; `EconomyProjector` |

The Construction row supports only its existing one-facility and two-facility
same-owner implementations. The matrix does not authorize a third facility,
an unbounded consumer list, or a new target owner.

## Enforcement

After each target owner has validated opaque Ecology admission, source event,
source and target revisions, privacy and exact idempotency handling, it calls
`GovernedAuthorityContractCatalog.require_operation()` immediately before its
existing fragment or formal quote batch. A mismatch returns the target owner's
structured rejection before `GameplayEventStore.append_batch()`.

Ecology still emits only project-visible source evidence. It does not select a
facility, organization, quote, price, stream, event family, receipt, or target
writer. The target owner remains responsible for all business validation.

## Non-goals

- arbitrary consumer registration, fanout, multi-hop autonomous propagation,
  retry or compensation;
- arbitrary price policy, payment settlement, or construction work;
- a second event store, bus, scheduler, runtime, population/NPC/social truth
  owner, branch promotion, SOC-1, GAME-1, P6 or P7.
