# INF-4R Population World-Mode And Civilization-Interface Expansion Design

Status: `verified bounded INF-4R social-input admission; INF-4Y separately admits one capability-gated supply input; all other follow-on inputs remain blocked`

Date: `2026-08-12`

## Purpose and truth boundaries

INF-4R extends existing CharacterProfile-based batch planning into bounded
world-mode cadence using `WorldModeProfile`, `PopulationPlanner`,
`ContinuityMergeAuthority`, and `ProfileActivationAuthority`. The first
executable slice consumes only the existing `SocialFactAuthority.view_for`
relationship/knowledge read view. Household/organization schedules, innovation
proposals, and civilization capability data are not inputs in this package. It
does not create population, NPC, family, organization, social, or civilization
truth stores.

Production writing remains:

```text
caller-selected world mode -> pure population plan -> existing owner intents
-> owner-authorized settlement -> GameplayEventStore.append_batch
-> outbox/replay -> scoped projections
```

Branches retain the INF-4 isolated buffer rule. A branch may produce reports
and proposals but cannot append production events, become population truth, or
activate a civilization capability.

## Models and event contracts

The first input contract freezes the exact `SocialFactAuthority.view_for`
result, its source revision vector, recipient scope, and observation time next
to `WorldModeProfile`. It is read-only and must not infer mutable social state.
At this INF-4R boundary, `HouseholdScheduleInput`, `OrganizationScheduleInput`,
`PopulationAggregateProjection`, `InnovationProposal`, and
`CivilizationCapabilityView` were blocked follow-on proposals. INF-4X has
since admitted the first two from their existing owners. INF-4Y separately
admits one authority-scoped, active/effective capability view only for the
documented `supply -> OrganizationAuthority` edge; it remains unavailable to
this generic planner method and cannot become population truth.

The planner emits ordered, deduplicated owner intents with expected revisions,
activation-lock refs, idempotency keys, and fixed seed. Production events stay
in their existing owner streams. Population-only events may record planning,
defer, requeue, and summary/checkpoint references; they do not assert a new
household, organization, social relationship, or civilization truth.

Civilization capability gating is blocked except for the separately documented
INF-4Y authority-scoped `supply` edge. Its owner, stream, event, receipt,
revision and redaction map are fixed in
`2026-08-12-inf-4y-civilization-capability-read-interface-design.md`.
Population planning may never create, upgrade, or modify a capability.

## Scheduling, failure, privacy, and replay

World modes select explicit caller-driven cadence and budget. They cannot
advance the shared clock, silently wake profiles, or downgrade domain rules.
Interactive activation locks defer only affected plans; release requires the
pinned revision. Unknown profile, inaccessible social view, stale social source
vector, unlicensed calibration data, duplicate key with altered digest, or an
owner decline yields zero production writes. Unmapped household, organization,
and capability inputs are rejected as unsupported rather than accepted without
a named, admitted authority. The only exception is the separately verified
INF-4Y `supply` binding.

The first planner filters the named social input to its recipient scope. It does
not yet provide aggregate, organization, creator-debug, or civilization views.
Full and checkpoint-tail replay reproduce ordered intents, lock/defer decisions,
and owner receipts for that scope. Branch replay uses its isolated base. Reader
migration and compensation are deferred until their owner event maps exist.

## Harness, non-goals, completion

`infra-population-world-mode` separately checks the frozen social input,
source revision zero-write, deterministic digest/order, recipient scope,
unsupported household/organization/unmapped-capability inputs, and merge-time stale
legacy generic-merge zero-write, and social-source replay without a legacy
append. It records evidence at
`.harness/verification/infra-population-world-mode-report.json`. Existing
population branch replay remains separately proved by
`infra-population-branch-preview`.

The profile does not establish full simulation. It uses only a typed
`FrozenSocialPlanningInput` built from `SocialFactAuthority.view_for` and
reuses the existing `PopulationPlanner`. The historical
`ContinuityMergeAuthority.merge(PopulationBatchPlan)` is a zero-write
compatibility fence, not an owner settlement path; formal writes require the
separately admitted owner-bound world-plan methods. No new writer or truth
owner is introduced.

The originally planned broader profile checks mode cadence,
deterministic batch order, `SocialFactAuthority` input scope/redaction,
lock/pending merge, idempotency, revision conflict zero-write, unsupported
household/organization/capability input zero-write, isolated branch replay,
production full/checkpoint-tail replay, and requeue.

Non-goals: innovation proposals, civilization capability gating beyond the
separately admitted `supply` edge, generated permanent population truth, household/social
authority, civilization authority, free-running NPC simulation, external dataset
ingestion, direct creator/LLM/Siming writes, or P6/P7. Completion covers only
the named SocialFactAuthority input and owner verticals with independent evidence.
