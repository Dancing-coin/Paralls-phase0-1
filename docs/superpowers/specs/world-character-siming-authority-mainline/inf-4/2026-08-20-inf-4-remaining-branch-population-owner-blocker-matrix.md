# INF-4 Remaining Branch, Population, And Social Owner Blocker Matrix

Status: `documentation-only remainder; INF-4AK is implemented separately; no new branch/population candidate is formed`

## Scope And Method

This matrix records the current INF-4 remainder after the finite implemented
rows. It reads the existing branch-preview, Production, Economy, Government,
Organization, Social, activation, and civilization-owner evidence only. It is
not an owner-discovery pass and does not convert an illustrative branch,
fixture, profile, or existing narrow row into a new business fact.

Excluded fixed rows are references, not templates for expansion:

- exact Organization supply and Government passed/failed-inspection promotions;
- exact committed Production completed-evidence to Economy wage accrual
  (including the bounded INF-4T branch-requested invocation);
- released schedule-gated supply, released Survival expiry, and activation-owned
  profile-region assignment; and
- isolated branch-local planned supply/inspection projections and fixed-base
  replay.

No row below creates a truth owner, generic promotion, router, registry,
coordinator, payroll, compensation, unified settlement, second runtime, store,
bus, clock, or scheduler. Unknown, multiple, unadmitted, missing/private/stale
evidence, binding conflict, revision conflict, duplicate, and changed-duplicate
requests remain zero-write before an existing owner can construct a fragment or
call `GameplayEventStore.append_batch()`.

## Evidence Classification That Must Not Be Collapsed

| Evidence kind | Current meaning | It is not |
| --- | --- | --- |
| Branch candidate request | A creator-debug request/candidate in the isolated `gameplay:branch_preview:{branch_ref}` buffer, pinned by the fixed base/source/calibration digests and replayed only in that buffer. | Production completion, a target-owner command, a receipt, or actual domain truth. `BranchPreviewAuthority.promote()` deliberately returns `branch_promotion_unsupported`. |
| Committed Production completed-evidence | `ConstructionProductionAuthority` commits the worker-scoped `gameplay.construction_production.work_completion_evidence_recorded` evidence after its own committed run-finished linkage, and exposes a revisioned actor-scoped view. | A generic work fact, a branch fact, a population/NPC fact, or permission for another target outcome. |
| Preview/proposal | A pure population plan, frozen social/household/organization/capability input, or branch-local projected planned commitment/inspection. | A mutable household, social, civilization, organization, population, NPC, payroll, or production event. |
| Actual domain truth | Only an existing domain owner’s admitted event on its own fixed stream, appended through the canonical envelope/settlement/store path and projected/replayed under that owner’s contract. | A planner report, preview digest, candidate name, or a generic promotion result. |

## Blocker Matrix

| Row / goal | Current committed evidence | Existing owner | Missing contract (no defaults) | Privacy / replay / idempotency / receipt risk | Can enter row-specific Owner-Admission design now? | Minimum user approval |
| --- | --- | --- | --- | --- | --- | --- |
| **INF-4-B1: branch candidate request -> actual target-owner consequence** | Isolated branch requests, accepted fixed-base branch replay, and redacted local planned `supply`/`inspection` projections exist. These are creator-debug evidence only. | `BranchPreviewAuthority` owns the isolated buffer only. Exact Organization/Government promotion operations already own their respective fixed rows; no generic target owner exists. | One exact target owner; exact target capability/outcome and event family; whether the proposed source is a branch-local outcome or a separately required committed Production/domain event; source/target subject binding; target stream and write revision; policy/package/declaration/binding/descriptor/catalog pins; terminal/reversal/correction/compensation rule. | Branch privacy is `creator_debug`, while production owner scopes are domain-defined. There is no branch-to-target receipt, shared replay reader, authority-derived key, or permitted branch/production history merge. Reusing an existing promotion key or receipt would be false provenance. | **No.** A branch request alone is not admissible source evidence. It may only be re-evaluated after the user names one source-to-one existing-owner outcome and explicitly decides whether a canonical committed non-branch source is required. | Name one exact existing target owner and one event outcome; select the sole legal source event/view and its revision/privacy/subject pins; decide branch role (request-only or no role); fix target stream/event/revision, idempotency, append-derived receipt, independent full/tail replay, and terminal/correction/compensation semantics. |
| **INF-4-B2: committed Production completed-evidence -> another target-owner outcome** | A committed worker-scoped `work_completion_evidence_recorded` event/view exists on the existing facility stream, derived from committed run-finished evidence and immutable contribution linkage. The exact Economy wage row is already implemented. | Production owns evidence; Economy owns the existing exact wage accrual. No additional target-owner consumer is identified by committed facts. | A new target owner and one exact non-wage outcome, or an explicit decision that the row is the already completed wage row (which would form no new work); source eligibility beyond the existing worker/run/assignment/work-order linkage; exact target event/vector/stream/write revision; policy and terminal semantics. | The evidence view is actor-scoped. Its Production source vector and projection hash cannot stand in for a target revision, target privacy projection, target idempotency key, append receipt, or target full/checkpoint-tail replay. Economy wage receipt/replay cannot be copied to another owner. | **No, not as a formed row.** The source is committed, but the required one-owner/one-outcome pairing is missing. It becomes eligible only after that pairing is approved. | Select one existing target owner and one exact outcome distinct from generic payroll/payment/transfer; approve evidence eligibility and subject binding, target privacy/stream/event/revisions, owner-derived idempotency, append receipt, target replay, and terminal/reversal/correction/compensation behavior. |
| **INF-4-B3: population or NPC lifecycle/domain truth** | CharacterProfile identity, activation facts, profile-region assignment, deterministic plan ordering, and scoped input projections are committed/bounded support facts. No committed event defines a requested population or NPC lifecycle outcome. | Existing profile registry/activation owner covers identity or activation-only facts; it is not a population/NPC truth owner. No admitted owner owns the proposed lifecycle, residence, employment, household, need, migration, or aggregate result. | Exact domain fact; its existing or separately approved domain owner; canonical source event/state; subject and jurisdiction/region binding; target stream/event/revision; visibility; event projection; idempotency; receipt; full/tail replay; terminal/correction/compensation. | Planner reports and activation streams carry limited scopes and cannot expose or synthesize NPC/private facts. No owner-local projection or receipt exists; batch key/replay only proves planning order, not a population truth transition. | **No.** There is neither a target truth owner nor a selected exact outcome. A row-specific contract cannot be designed by assigning defaults. | Approve one typed domain fact and its owner boundary first (or explicitly name an already existing owner that owns it), then its source/target event vector, subject/jurisdiction/privacy pins, revision/idempotency/receipt/replay, and terminal/correction/compensation semantics. This is a material domain-owner decision, not an INF-4 planner option. |
| **INF-4-B4: social, household, organization, or civilization actual-truth expansion** | `SocialFactAuthority` has scoped household membership read evidence; Organization has scoped schedule projections; civilization has a narrow active/effective capability view. These feed only approved finite existing-owner edges. | Social, Organization, and civilization owners retain their existing fact boundaries. `PopulationPlanner` is proposal-only and cannot author, infer, upgrade, or persist these facts. | The requested exact fact/outcome; source owner/event and eligibility; whether the selected owner already owns that new fact; target event/stream/write revision; recipient/jurisdiction privacy; policy/effective-time semantics; receipt/replay; duplicate and correction/terminal semantics. | Scoped views are redacted and revisioned for named consumers. Treating them as a broad social/civilization write permit leaks privacy and bypasses owner replay. Existing supply/inspection binding receipts cannot be used for another social or capability result. | **No.** Existing views do not identify a new single source-to-one-owner outcome. | Name one actual fact and one owning existing authority; approve the source view/event and privacy scope, exact target event/stream/revision, policy/effective-time rule, owner key and receipt, full/tail replay, and correction/terminal/compensation rule. |
| **INF-4-B5: group simulation / batch promotion to world truth** | `PopulationPlanner` produces ordered plans; `ContinuityMergeAuthority.merge(PopulationBatchPlan)` explicitly rejects with `legacy_population_merge_retired`; preview mode requires the isolated branch path. Existing world-plan consumers are a finite owner map only. | No group-simulation, batch-promotion, or aggregate-truth owner exists. Existing domain owners may settle only their individually admitted rows. | One exact domain outcome per target owner; owner-fragment mapping; source/evidence vector; grouping semantics and permitted cardinality; target event/stream/revision; privacy aggregation/redaction; per-owner idempotency/receipt/replay; terminal/reversal/correction/compensation. | A batch plan’s ordering digest and command keys cannot become a cross-owner receipt or one aggregate idempotency key. Its replay demonstrates planning, not target truth. Fanout would need independently admitted owner-local rows; a unified result would conceal receipts and privacy boundaries. | **No.** Generic or aggregate group simulation violates the one exact target-owner outcome requirement and has no owner-fragment map. | Do not approve “group simulation” as a blanket capability. Approve the first one-to-one domain outcome: source, one existing target owner, exact event vector, cardinality, privacy/redaction, revision/idempotency, append receipt, replay, and terminal/correction/compensation. Each further owner is a separate decision. |

## INF-4AG Closure Note

The exact fulfilled INF-2AG public-workshop Contract -> provider Organization
activity record is implemented and verified separately. It is project-scoped
and contains no participant, recipient, relationship, reputation, population,
or public-announcement fact. It therefore does not relax any branch,
population, social, group, or public-notice blocker in this matrix.

## 2026-08-28 INF-4AN Rejected Ecology Notice Sibling

The new INF-3AA water-resource recovery fact was checked as a potential
Government public-notice source. It is `conflict_rejected`: unlike the existing
public-workshop and public-milling notices, it has no independent completed
service/activity or named Government consequence. A new notice would turn
owner-local Ecology corrections into an implicit generic Ecology-to-notice
capability. The formal disposition is recorded in
`2026-08-28-inf-4an-rain-water-resource-government-notice-conflict-disposition.md`.

## Durable Blocker And Design Entry Rule

The completed generic branch-promotion audit, the INF-4 owner-admission
candidate register, and the finite existing-owner map are durable evidence.
No fourth same-class owner discovery is warranted.

The only valid next design entry is a user-approved tuple:

```text
one committed canonical source event or state
-> one named existing target owner
-> one exact target outcome/event vector
```

That tuple must additionally name its source and target revisions, subject and
privacy bindings, policy pins, authority-derived idempotency, append-derived
receipt, independent full/checkpoint-tail replay, and terminal/reversal/
correction/compensation semantics. A branch candidate may remain a request or
audit pin only; it never fills a missing Production or domain-truth field.

Until those fields are approved, every matrix row remains `owner-contract
blocked` or `unimplemented`, and no implementation, manifest/catalog work,
RED tests, or Harness change follows from this document.

## Evidence Consulted

- `backend/app/population_continuity/branch_preview.py`
- `backend/app/population_continuity/batch.py`
- `backend/app/gameplay/construction_production_runtime.py`
- INF-4 README and plans, INF-4T generic-promotion audit/design, INF-4Z
  Production completed-evidence design, INF-4E/INF-4G branch boundary, and
  INF-C5 fixed-base replay contract
- current completion audit, remaining-scope dependency design, continuation
  checkpoint, and `docs/harness.md`

## 2026-08-31 Foundation Return Recheck

The completed closed-family Foundation adds reusable private-follow-on and
owner-bound package evidence only. It does not commit a jurisdiction,
participant, attendance, population, group, or new social-truth event for
INF-4. Branch candidates remain request-only and cannot replace Production or
domain truth. INF-4 B1-B5 retain their documented `owner-contract blocked` or
`unimplemented` dispositions; no promotion, population writer, or generic
social route follows from Foundation closure.
