# INF-4Z Complete Population World-Mode Design

Status: `implemented bounded; supply and inspection use existing owners; work and generic civilization inputs remain rejected`

## Purpose and inherited baseline

INF-4Z specifies complete batch population world modes without inventing a
population owner. It extends the verified deterministic `PopulationPlanner`,
`ContinuityMergeAuthority`, `ProfileActivationAuthority`, branch buffer,
`ReferenceDataset` and `CalibrationInput`. Existing preview digest isolation is
not proof of fixed-base branch replay, household scheduling, aggregate truth or
civilization integration.

## Boundaries and inputs

Game, simulation and preview modes share CharacterProfile identity, event
history, active semantic/policy revisions and domain authorities; modes alter
only caller-selected cadence, batch budget, activation policy and report scope.
Inputs are frozen scoped social views, admitted INF-4X household/organization
schedule views and approved calibration data. `CivilizationCapability` input is
explicitly unsupported until INF-4Y admission; complete population batching does
not author, infer, or require civilization progression. Each admitted input has
provenance/revision/digest. LLMs, Siming, Godot, clients and creators
propose plans/evidence only. The planner never owns character, household,
organization, social, economic or civilization facts.

## Planning, branch and event contract

`PopulationWorldPlan` pins mode profile, base checkpoint/event boundary,
active revisions, source vectors, seed, budget, ordered profile candidates,
activation locks, command idempotency keys and report scope. It emits only
existing owner intents; owner receipts are canonical. Planning/defer/requeue/
summary events may be recorded only if they do not claim independent population
truth. A plan with an unknown/missing source capability is rejected before an
owner call.

`game`, `simulation` and `preview` are immutable caller-selected policy labels:
each plan carries only the selected profile's cadence and budget, and planning
does not accept or advance a `SimulationClock`. A `preview` world plan is never
eligible for `ContinuityMergeAuthority.merge_world_plan`; that boundary returns
`preview_requires_branch` with zero production writes. Preview execution stays
inside `BranchPreviewAuthority`'s non-production buffer.

`BranchPreviewRequest` fixes production checkpoint plus tail boundary, source
digests, ruleset/policy revisions, seed and branch id. `BranchEventBuffer` is
non-production, has its own replay projections/reports, never calls production
`append_batch`, and is discarded rather than merged. `ReferenceDataset` and
`CalibrationInput` remain revisioned, scoped assumptions; they cannot overwrite
world facts or bypass authority. `ReferenceDataset.license_ref` remains legacy
caller metadata only. The separately verified INF-4Z-A
`ReferenceDataAuthority` owns authoritative license admission on
`gameplay:reference_data:{dataset_ref}` and exposes only a frozen,
authority-scoped `ReferenceDatasetView` with event refs, stream vector,
revision, digest and allowed scopes. `preview_authorized()` accepts only that
current permitted view, rejecting revoked, forged, stale and scope-mismatched
inputs without production writes. It does not admit external ingestion, branch
promotion, generic work, or any population truth.

## Admission blocker and recovery condition

The historical P3C `ContinuityMergeAuthority.merge(PopulationBatchPlan)`
free-form writer is retired as part of this gate. It formerly selected a stream
and event type from caller payload and appended under `population.authority`,
so it could not satisfy the required existing-owner mapping. It now has only a
zero-write compatibility result; production callers must use a documented
owner-bound method or remain rejected.

The general INF-4Z path remains stopped before any additional focused test or runtime change.
The retired code path formerly derived a target stream and event type from
free-form `BatchIntentCandidate.payload` and committed them under
`population.authority`. That was not a named existing domain owner, an
owner-authorized fragment, or a canonical owner receipt; the implementation no
longer retains that unreachable writer. No approved mapping
currently binds an INF-4Z intent kind (including the existing `work` example)
to all of: target authority principal, fragment builder, canonical stream,
event family, expected revision vector, scoped projection, privacy rule, and
owner receipt reader. Therefore a production batch cannot safely call the
current merge path as a general INF-4Z capability. Bounded `supply` and
`inspection` rows are admitted separately through existing owner fragments.

Before implementation resumes, a separate admission amendment must name one
bounded existing-owner consumer row for each intent kind that INF-4Z is allowed
to submit. The row must use `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch() -> outbox/replay -> scoped projection`, must
reject unknown/changed mappings without writes, and must leave the planner as a
proposal-only component. The fixed-base branch request must likewise name the
checkpoint reader/upcaster version, tail boundary encoding, and the
source/ruleset/policy digest vector it validates. Until those contracts are
approved, no additional intent mapping, branch promotion, or completion claim
may be implemented. The current bounded evidence is
`infra-population-world-mode-complete`, whose independent
`legacy_population_merge_zero_write` assertion proves the compatibility API
cannot append an event or outbox entry from caller-selected stream/event data.

## Bounded admitted row

The admitted INF-4Z consumer rows are:

- owner: `actor_gameplay.organization_domain`
- stream: `gameplay:organization:{organization_ref}`
- fragment: `OrganizationAuthority.build_commerce_commitment_fragment`
- event: `gameplay.organization.commerce_commitment_accepted`
- receipt: existing `GameplayEventStore.append_batch()` result with owner provenance
- projection/replay: existing outbox and `GameplayProjectionReplay`

- owner: `actor_gameplay.government_domain`
- stream: `gameplay:government:{organization_ref}`
- fragment: `GovernmentAuthority.build_commercial_inspection_fragment`
- event: `gameplay.government.inspection_recorded`
- receipt: existing `GameplayEventStore.append_batch()` result with Government owner provenance
- scoped projection: one committed `world.government.inspection.scoped_projection`
  outbox entry addressed exactly to `PopulationWorldPlan.report_scope`; its payload is
  limited to `inspection_ref`, `organization_ref`, `jurisdiction_ref`, and `passed`.
  It must not disclose the inspection `evidence_ref` or source-plan payload.
- replay: existing `GameplayProjectionReplay`; full and checkpoint-tail replay retain
  the same committed Government event projection hash.

`work` remains zero-write because no equivalent existing owner fragment and
receipt contract has been admitted. `OrganizationAuthority.AttendanceEvidence`
is presently a value-object validator, not a canonical completed-evidence event
with an owner-scoped read projection. For `production-completed`, the admitted
issuer is instead `actor_gameplay.production_domain`; the existing canonical
`run_finished` event does not retain actor, assignment, or work-order linkage,
so it cannot be reinterpreted as completed labor evidence. Although
`EconomyAuthority.build_commerce_wage_accrual_fragment` exists, it accepts only
opaque evidence refs and does not pin a completed-evidence source stream,
revision vector, or privacy scope. A future narrow row must first add a
Production-owned completed-evidence event/view before the planner can submit
the economy fragment.

The first source prerequisite is now independently verified: Production writes
`gameplay.construction_production.work_completion_evidence_recorded` on its
existing facility stream only after its own committed run finish and immutable
worker-contribution linkage. It provides a recipient-scoped revisioned view;
this source package does not admit a planner input or Economy write.

## Correctness, privacy, replay, rollback, Harness and completion

Stable ordering, deterministic seeds, caller budgets, no hidden clock advance
and activation-lock pending merge are mandatory. Invalid identity/base,
unapproved data, stale projection, source visibility denial, owner refusal,
overlap or changed duplicate command returns zero production writes. Views and
reports preserve source redaction; aggregate reports cannot become social truth.
Full/tail production replay and fixed-base branch replay reproduce plans,
receipts and reports. Migrations use reader/upcaster versions; production
correction/compensation stays owner-specific, branches are discarded.

`infra-population-world-mode-complete` separately asserts each admitted mode's
cadence/budget, deterministic owner mapping, duplicate idempotency replay,
revision conflict zero-write, privacy-scope zero-write, activation-lock pending
zero-write, no-write unsupported inputs, production full/tail replay,
fixed-base branch replay, calibration/source digest validation, branch tail
boundary rejection, and preview non-promotion. The current bounded evidence
does not claim generic defer/requeue or any unadmitted consumer mapping; those
remain blocked until an existing owner fragment/receipt contract is approved.
Non-goals: a population truth store, background NPC daemon, synthetic social
truth, capability authoring, P6/P7. Completion is contingent on all admitted
sources and owner-specific consumer paths, not one preview scenario.
