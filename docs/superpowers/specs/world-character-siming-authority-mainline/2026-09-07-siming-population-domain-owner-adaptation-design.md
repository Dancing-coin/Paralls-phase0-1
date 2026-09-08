# Siming Population Domain-Owner Adaptation Design

Status: `approved design; Task 1 admission matrix`

## Purpose

This document is the admission matrix for the first Siming population domain
adapters. It distinguishes a domain Owner contract that already exists from a
population capability that is approved to derive candidates and route through
that Owner. An existing domain contract is not automatically a population
capability: population admission still requires a committed, scope-filtered
projection, a fixed capability and Owner mapping, and replay/privacy metadata.

The matrix is read-only governance. It is not a generic population truth owner,
generic writer/router, second event bus/store, clock, scheduler, or background
LLM loop. `SimingRuntime.tick(...)` remains the only Siming decision and
dispatch path. Candidates are projections, never facts; an Owner receipt must
precede any later continuity input.

## Admission Matrix

| Population behavior | Source | Capability | Existing Owner | Initial status |
| --- | --- | --- | --- | --- |
| `organization_production_work_contribution` | committed Production evidence + Organization schedule projection | `population:organization-production-work-contribution:v1` | `OrganizationAuthority.accept_production_work_contribution` | `executable_next` |
| `inventory_output_custody` | certified Production output projection | `population:inventory-output-custody:v1` | `InventoryAuthorityService.settle_production_output_custody` | `planned` |
| `social_population_signal` | public population signal projection | `population:social-population-signal:v1` | `SocialFactAuthority.record_admitted_population_signal_materialization_proposal` | `planned` |
| `tax_pressure` | authority-derived Tax obligation summary with amount redacted | `population:tax-pressure:v1` | Economy/Tax Owner | `report_only` |
| `stormnight_action_window` | realtime action-window evidence | not admitted | `InvestigationConflictAuthority` | `not_population_behavior` |

The first three rows are ordered verticals, not a claim that all three are
runtime-enabled today. `tax_pressure` is report-only: authority-only amounts
and evidence stay redacted and no population candidate may debit or settle an
account. `stormnight_action_window` is an investigation/realtime concern and
is excluded from population cadence.

## Admission Rules

1. A source must be committed, revision-pinned, and within the declared
   population read scope before it can produce a candidate.
2. The candidate names one source-controlled capability and one existing Owner
   operation. Callers cannot provide a stream, event family, or replacement
   Owner.
3. The adapter must return the existing Owner's append-derived receipt. No
   generic writer or second event store is introduced.
4. Each executable row requires focused stale, duplicate, changed-duplicate,
   rejection, privacy, and full/checkpoint-tail replay evidence before it is
   promoted beyond its matrix status.

The existing three-actor cohort and Bakery supply fixtures remain unchanged.
This matrix therefore defines the next bounded admission step without claiming
complete population or civilization simulation.
