# INF Remaining Scope Dependency Design

Status: `已批准的 INF 窄纵切完成并验证；八月 INF 主线仍未完成`

Date: `2026-08-12`

## Purpose

This record orders the remaining scope after the verified INF-1 through INF-4
verticals. It prevents broad phrases such as "complete INF", "full ecology",
or "complete group simulation" from concealing missing owners, write paths, or
evidence.

## Verified narrow verticals

| Package | Scope | Required predecessors | Cannot own |
| --- | --- | --- | --- |
| INF-1R | semantic proposal to `ConstructionProductionAuthority.build_due_finish_fragment` | INF-1, INF-2 | verified 2026-08-12; world truth, scheduler, direct creator writes |
| INF-2R | construction production due-completion policy | INF-2 | verified 2026-08-12; timer, global obligation truth, owner outcome |
| INF-3R | `EcologyHazardAuthority.settle_frost` to construction production edge | INF-1R, INF-2R lifecycle event for delayed work, verified INF-3R-A/B admission | verified 2026-08-13 for one committed frost source -> one due construction finish fragment -> existing append/outbox/replay/scoped projection; no other consumer edge | market/body/social/population truth |
| INF-4R | world-mode plans from `SocialFactAuthority.view_for` | INF-2R, F1B scoped projection rules | family/social/civilization truth, free-running NPC runtime |

`INF-*R` records are narrow executable samples. The remaining analysis scope is
carried by independent packages, so sample evidence cannot be described as
general closure:

| Package | Scope | Required predecessors | Status | Cannot own |
| --- | --- | --- | --- | --- |
| INF-1X | closed rules/effects/resistance/lifecycle and owner mapping matrix | INF-1R, INF-2X for durable lifecycle | verified one-shot production row, four explicit Survival scheduled rows (`cold`, `overheated`, `dehydrated`, `fatigued`), two closed Survival actions (`state_dispel`, fixed `state_transform_recovery`), and INF-1O's pure StateDefinition action decision consumed before the existing Survival fragment. Also verified: one Construction `maintenance_required -> maintenance_due` facility-state row, one registered `wage_accrual_due -> EconomyAuthority` obligation row, INF-1L's fixed Ecology frost row, INF-1AA's fixed Ecology drought row, INF-1N's fixed Construction apply -> open -> expired/settled obligation row, and INF-1X's/INF-1AA's closed semantic Ecology adapters. INF-1Z completes the frost row's fixed `effect:ecology_frost_state_dispel` by writing a dispel and exact obligation cancellation in one Ecology owner batch. INF-1M now materializes seven finite state-owner contracts; INF-1Q then supplies immutable lifecycle metadata for those same seven rows plus the existing wage-obligation row and makes existing semantic routes/actions read it before owner fragments. It remains finite and cannot become generic dispatch or a writer; all other owner rows remain blocked | target-domain truth, generic writer |
| INF-2X | event-derived settlement/cancellation lifecycle for `policy:construction_due_completion@1` | INF-2R | verified 2026-08-13 for the sole construction row; cancellation derives its identity from committed construction source evidence. INF-2T additionally verifies a shared, closed-registration, event-derived bounded `open/retry -> due -> terminal` reader across existing owners, with full/checkpoint-tail equivalence and no append. Retry, compensation and all other owner rows remain unsupported unless their exact owner contract already exists | clock, scheduler, domain outcome |
| INF-2I | named Organization/Economy commerce commitment through fixed owner fragments | existing Organization, Economy, Inventory and optional Wage contracts | implemented bounded 2026-08-14: existing `CommerceAuthority` assembles only those owner fragments into one append batch, with canonical duplicate/changed-duplicate admission, redacted authority outbox, append-derived receipt and replay evidence; generic policy/payment/cross-domain settlement remains blocked | owner truth, generic writer, payment settlement |
| INF-2J | fixed Economy scheduled account-transfer obligation | existing `EconomyAuthorityService` account ledger and obligation lifecycle contract | verified 2026-08-15: `policy:economy_scheduled_account_transfer@1` event-derived open/due/settled/cancelled/expired lifecycle writes debit, credit and terminal events only on `gameplay:economy` through the existing envelope/plan/one-append spine; each privacy, idempotency, stale, funds, forged fragment and replay check is independent | caller policy registration, generic payment, cross-domain business settlement |
| INF-3X | regional ecology record/lifecycle extension of `EcologyHazardAuthority` | INF-1X, INF-2X | verified record/retirement rows, caller-driven step/path/fanout/waves, and INF-3M's source-event-shaped deterministic canonical-neighbor proposal plus bounded Ecology-only append over existing streams. INF-3I's source-only admission remains an exact existing Organization owner row. Scheduler, retry/compensation and generic consumer propagation remain unsupported | market/body/social/population truth |
| INF-3Y | registered hazard propagation consumer edges | INF-3X plus exact target fragment | verified for three exact project-visible Ecology -> existing Construction fragments, one fixed two-facility same-owner fanout, INF-3I's one exact weather-front -> existing Organization commerce commitment edge, INF-3J's one Economy quote edge, and INF-3N's one fixed two-quote Economy same-owner fanout; generic consumer registry, arbitrary fanout and other domain outcomes remain blocked | generic consumer/domain outcomes |
| INF-4R | world-mode plans from `SocialFactAuthority.view_for` | INF-2R, F1B scoped projection rules | verified 2026-08-13 for typed recipient/time/digest/source-vector frozen social input, deterministic planner admission and merge-time stale-source zero-write; schedule/capability inputs remain blocked | family/social/civilization truth, free-running NPC runtime |
| INF-4X | household/organization source projections from existing social/organization owners | INF-4R | implemented bounded 2026-08-13: existing owners publish scoped household membership and organization schedule views; planner freezes inputs and emits existing owner intents | family/organization/social truth outside its existing owner |
| INF-4Y-A | minimal read-only civilization capability owner admission | user-authorized authority/stream/event/projection contract | verified 2026-08-13 for `CivilizationCapabilityAuthority`, `gameplay:civilization_capability:{jurisdiction_ref}`, activated/revoked/corrected lifecycle, scoped views and replay; consumers require separately documented INF-4Y bindings | progression, six-axis, institution systems, consumer eligibility beyond named edges, P6/P7 |
| INF-4Y | read-only civilization capability consumer interface | INF-4Y-A plus user-approved consumer binding | implemented bounded 2026-08-13: authority-scoped, effective capability view pins exactly `supply -> OrganizationAuthority.build_commerce_commitment_fragment` and `inspection -> GovernmentAuthority.build_commercial_inspection_fragment`; both targets retain existing stream/event/receipt ownership and only opaque capability digests. Work, semantic and every unlisted consumer remain zero-write | capability/institution/civilization truth |
| INF-4Z | complete population game/simulation/preview modes | INF-2X, INF-4X, admitted owner-bound mappings, and INF-4Z-A for authoritative calibration | implemented bounded 2026-08-13: `supply -> OrganizationAuthority.build_commerce_commitment_fragment`, `inspection -> GovernmentAuthority.build_commercial_inspection_fragment` with a report-scoped redacted Government outbox/replay projection, and one Production `production-completed` scoped source -> `EconomyAuthority` wage accrual consumer. The wage row revalidates an actor-scoped frozen Production view and writes only the existing wage stream through `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch`, with source/event/vector/digest/policy/target revision pins, owner receipt, privacy and replay evidence. The historical P3C `PopulationBatchPlan` generic merge is retired to zero-write because it had no owner-fragment mapping; the INF-4Z report independently proves it cannot append caller-selected stream/event data. Branch evidence separately proves candidate order, base/calibration digest and unknown-profile zero writes. Separately, INF-4Z-A verifies `ReferenceDataAuthority` lifecycle/read admission for frozen permitted datasets on `gameplay:reference_data:{dataset_ref}`; only that authority-scoped view can admit calibration preview, and revoked/forged/stale/scope-mismatched input is zero-write. All other `work` sources/mappings remain zero-write; caller-selected game/simulation/preview cadence-budget is pinned, while preview production merge is zero-write and isolated; all capability inputs outside INF-4Y's named `supply` and `inspection` edges remain zero-write; full modes remain incomplete | population/NPC/social truth, branch promotion, external ingestion, generic reference-data use |

F1B remains the source for social/knowledge/privacy projection contracts and
F1C remains the source for governed package revision/activation. INF-R packages
may consume their revisioned scoped views but may not recreate either control
plane. A civilization capability view, ecology recovery fragment, or any
additional semantic target owner is blocked until its exact authority, stream,
and scoped projection are documented. The user-authorized INF-4Y-A read
admission and the separate narrow INF-4Y `supply` and `inspection` consumer bindings are
documented in `inf-4/2026-08-12-inf-4y-civilization-capability-read-interface-design.md`.
That exception admits no work, semantic, or other consumer binding.
Ecology facts extend only
`EcologyHazardAuthority`; household facts extend only `SocialFactAuthority`;
organization schedules extend only `OrganizationAuthority`. INF-4Y is a
read-interface admission gate, not P7 work. P6/P7 implementation
is not started by this dependency record.

## INF-3R-A admission evidence

`INF-3R-A` is a verified prerequisite, not an ecology propagation edge. It
derives a scoped frost source from the existing committed crop
`semantic.effect.settled` event and makes the existing construction projector
select exactly one due started run for the source plot. It has no construction
write path. Its independent profile is
`infra-frost-production-admission`, with evidence at
`.harness/verification/infra-frost-production-admission-report.json`.
The source and target preserve privacy/revision rejection, idempotency and
full/checkpoint-tail replay equivalence. INF-3R must still begin with new
failing consequence-settlement tests and commit only the construction owner's
authorized fragment through one existing append batch.

`INF-3R-B` is verified. The existing construction owner extends its committed
`run_started` event with only the immutable fragment recipe inputs and rebuilds
an authority-only revisioned read view through the existing projector. Evidence
is `infra-frost-production-recipe-admission` at
`.harness/verification/infra-frost-production-recipe-admission-report.json`.
It does not permit ecology or a coordinator to construct recipe data and did
not itself write a production consequence. INF-3R subsequently consumed this
admission through its own independent `infra-regional-ecology` evidence.

## Shared implementation gate

Before an INF-R/INF-X/INF-Y/INF-Z package starts code work, its implementation plan must name
the exact existing owner for every write, input projection, event stream,
expected revision, privacy scope, failure/zero-write condition, replay reader,
migration/rollback behavior, focused tests, and independently named Harness
 profile. A missing owner is a design blocker, not permission to create one.

The continuation gate is independently recorded at
`.harness/verification/infra-continuation-gate-report.json` and asserts the
admitted ecology owner, stream, event family, canonical write path, sole
INF-3Y enabled edge, and exact ecology-registered admission identity fence.
It also refuses a predecessor hazard report that lacks the independent
real-class-forgery zero-write assertion. It is a stop/go record for future
turns, not a second runtime or a consumer implementation. INF-4X is now
evidence-gated as implemented bounded. INF-4Z predecessor evidence was rerun
on 2026-08-13, but the package is stopped at its formal admission gate: an
existing-owner intent mapping must name the authority, fragment builder,
stream/event family, revision/privacy projection, and owner receipt for every
allowed population intent before the planner can call a production writer.
The current bounded INF-4Z evidence is
`.harness/verification/infra-population-world-mode-complete-report.json`; the
independent Production source admission evidence is
`.harness/verification/infra-production-completed-evidence-source-report.json`.
The source record supports only the separately verified canonical Production
evidence -> Economy wage consumer, evidenced by
`.harness/verification/infra-production-evidence-wage-consumer-report.json`.
It does not bypass the retired generic `PopulationBatchPlan` merge or the
generic `work` zero-write mapping: the INF-4Z profile independently proves the
compatibility API cannot append caller-selected stream/event data. Every other source,
evidence kind or wage mapping, and every INF-4Y consumer binding other than the
documented `supply` and `inspection` edges remain blocked.
`INF-4Z-A` separately closes the former reference-data admission gap with
`authority:reference_data`, `gameplay:reference_data:{dataset_ref}` and the
registered/corrected/revoked lifecycle. Its authority-only frozen read is
consumed solely by `BranchPreviewAuthority.preview_authorized()` and is proved
by `.harness/verification/infra-reference-data-license-admission-report.json`.
It does not create an ingestion writer, permit branch promotion, or widen any
population or civilization mapping.

## August mainline work still open

The verified rows above are prerequisites and narrow samples, not completion of
the August INF mainline. The remaining packages are ordered and must each have a
formal owner/event/projection contract before code starts:

| Mainline package | Required completion beyond current narrow rows | Current state |
| --- | --- | --- |
| INF-1 lifecycle closure | Event-derived effect expiry; StateDefinition add/replace/refresh/reject, stack limits, dispel and transform; constrained multi-condition selectors; owner-bound settlement rows | four explicit Survival rows (`cold` / `cold_exposure`, `overheated` / `heat_exposure`, `dehydrated` / `dehydration_exposure`, `fatigued` / `fatigue_exposure`) plus their closed semantic bridge, finite proposal-only `all(...)`/`any(...)` guard composition, one verified Construction `maintenance_required -> maintenance_due` facility-state row, INF-1H's closed state dispatch, INF-1J's separately registered `wage_accrual_due -> EconomyAuthority` obligation row, INF-1K's two closed Survival actions, INF-1O's pure closed-contract dispel/fixed-transform decisions before the existing Survival fragment, INF-1L's exact Ecology `effect:frost -> state:frosted@1` apply/open/expiry/settled row, INF-1AA's exact Ecology `effect:drought -> state:drought@1` apply/open/expiry/settled row sourced from committed drought-process evidence, INF-1Z's exact semantic frost dispel -> Ecology `crop_state_dispelled` plus exact open-obligation cancellation row, INF-1N's exact Construction apply -> event-derived open -> expired/settled row, and closed semantic proposal-to-Ecology frost/drought adapters are verified through 2026-08-16. INF-1Q adds one closed reader for the finite seven state rows plus the existing wage row, including terminal event, action, outbox, revision, idempotency and replay metadata. It does not add generic registration or routing. Additional cross-domain rows and generic event-derived lifecycle remain blocked by missing approved owner/event-family/receipt mappings; evaluator payload alone remains only a proposal |
| INF-2 lifecycle closure | open/due/settled/cancelled/expired/retry/compensated across construction and at least one survival/economy owner; bounded catch-up, activation pending merge and single-store receipt | construction settled/cancelled, Survival state-expiry open/retry/settled/cancelled/compensated, Economy wage open/retry/cancel/expired/settled/compensated, and INF-2J's fixed Economy scheduled account-transfer open/settled/cancelled/expired row are verified. `SettlementReceipt` always summarizes exactly one resulting `GameplayEventStore.append_batch()`. INF-2J binds only two existing same-currency Economy accounts to `policy:economy_scheduled_account_transfer@1`; its debit/credit/terminal batch and authority-only receipt/outbox have independent evidence. INF-2B/2E/2F additionally verify released activation `survival_state_expiry` -> Survival settlement for exactly `cold`, `dehydrated` and `overheated`, each with deliberately separate activation and Survival append-derived receipts. INF-2G now gives those three rows plus existing `schedule_gated_supply -> OrganizationAuthority` one immutable four-row, event-derived binding reader and preserves their separate target receipts. INF-2H formalizes the existing `EconomyAuthorityService` single-stream account opening/transfer/reservation path with authority outbox, append-derived receipt, privacy and replay evidence. INF-2P separately verifies that `OrganizationAuthority` alone writes `gameplay:organization:window:{window_ref}` open/close/due facts while `EconomyAuthority` remains bounded to wage obligation/accrual/payment/overdue and existing account transfers; the old Economy window helpers survive only as delegates and do not retain a second writer. INF-2R records those exact two append-owner rows in the immutable governed catalog and makes each owner reject catalog mismatch before batch construction; it is source-controlled admission, not registration or a coordinator writer. INF-2M now rejects policy-less, unknown, forged, or widened caller registrations, terminal-plus-smuggled-event fragments, owner-privacy scope overrides, and Construction due terminals lacking the exact committed `run_started` source event before append; caller registrations are normalized so they cannot weaken canonical `requires_committed_open` or other required admission conditions. It recognizes six existing owner policies with closed owner-local event families and fixed visibility only. Open policy registration, generic payment, account reservation release and broad cross-domain atomic policy remain incomplete |
| INF-3 process closure | weather/resource/crop/environment process lifecycle, one non-frost process or hazard, budgeted progressive propagation and target-owner edges | record/retire rows, closed one-region seasonal and drought environment/resource/crop processes, caller-driven bounded propagation, and INF-3M's bounded event-derived next-frontier planner are verified. Three exact Construction edges, INF-3H fixed two-facility fanout, INF-3I one exact Organization supply edge, INF-3J one exact source-pinned Economy quote edge, INF-3N one exact two-quote Economy owner fanout, INF-4AC's evidence-pinned active profile-to-region prerequisite, and INF-1AC's exact weather:frost -> existing Survival cold row remain finite. INF-3L records the target-owner contracts. Generic target-owner effects, arbitrary fanout, autonomous scheduling and retry/compensation remain blocked pending their own policy, privacy and owner-fragment contracts |
| INF-4 branch and batch closure | replayable isolated branch event/projection evolution and one real household/organization schedule input merged via revision/activation lock | INF-4M persists a redacted accepted isolated branch buffer and INF-4P appends one fixed redacted owner-consequence evolution event to the same `gameplay:branch_preview:{branch_ref}` stream; a fresh authority rebuilds snapshot plus ordered evolution with checkpoint-tail replay. INF-4L durably records accepted inspection evidence on that same stream before Government revalidates it to append the existing INF-4I passed or INF-4J fixed-remediation scenario row; revalidation requires exact stream/branch equality with independent passed/failed forged cross-branch zero-write proof. INF-4K derives one immutable remediation receipt from that evidence-backed row only. All use the same store, scoped outbox and replay while production replay remains isolated. One frozen social/household/organization schedule -> existing Organization supply fragment row, INF-4C's activation-event-derived released `schedule_gated_supply` pending merge, INF-4AB's released `survival_state_expiry` pending -> existing Survival owner settlement with a separate single-append receipt, and INF-4AC's activation-owned project-scoped Ecology-evidence `profile_ref -> region_ref` projection are verified. Generic remediation lifecycle, other owner scenario rows, generic scenario receipt, promotion, generic pending and complete group simulation remain incomplete |

## Mainline Closure Owner-Contract Matrix

The following are the actual August-mainline blockers after the verified narrow
verticals. They are not authorization to create a generic router, a coordinator,
or a new truth owner. A future package may start only after its row is replaced
by a concrete existing-authority contract and a focused RED test.

| Mainline gap | Existing evidence | Missing contract that blocks code | Required next artifact |
| --- | --- | --- | --- |
| INF-1 generic effect/state lifecycle | INF-1Q's six-contract immutable lifecycle reader fixes event family, action allowance, outbox, revision, idempotency and replay metadata for five existing `StateOwnerContract` rows plus the existing Economy wage row; all use existing owner append/receipt/replay | every additional pair or action lacks an approved existing authority, target stream, complete event family, scoped projection, revision/idempotency rule and owner receipt/replay reader; Construction transform/repair/payment truth is still absent | one owner-row design naming all fields, then a row-specific RED suite; state-only callers retain `semantic_state_owner_contract_unknown`, while the new lifecycle reader returns `semantic_lifecycle_owner_contract_unknown`; both are zero-write |
| INF-2 open obligation-policy registration and cross-domain settlement | construction, Survival and Economy rows each derive lifecycle events; INF-2J proves a second fixed Economy lifecycle with account debit/credit; INF-2I proves one fixed Organization/Economy/Inventory/Wage commerce commitment; INF-2K registers/revokes one typed Government inspection policy on an existing Government stream with replay view and one append-derived receipt; INF-2L migrates fixed simple-debt issue/payment/cancellation/correction/reopen/overdue/default batches to its owner-bound formal spine; INF-2M constrains coordinator input to six existing policy contracts; INF-2Q has already retired the coordinator append/callback surface, leaving it as a read-only planner | no existing owner defines the business outcome, compensation semantics, target stream/revision and receipt boundary for arbitrary policy kinds; generic cross-stream atomic business settlement remains unapproved; caller-open registration is intentionally rejected rather than implemented as a generic writer | bind one next existing-owner policy to its exact outcome and receipt, or reject before append |
| INF-3 fanout and further consumer effects | Ecology owns canonical records, bounded caller-driven propagation, INF-3M's deterministic event-derived next-frontier proposal/append, three Construction edges, the fixed INF-3I Organization supply edge, INF-3J's exact project-visible weather-front -> Economy quote edge, INF-3N's exact project-visible weather-front -> two Economy quotes one-batch row, and INF-3L's catalog enforcement across those fixed target-owner contracts | INF-3M is not autonomous scheduling or generic propagation. Each additional Economy/other-domain fanout or propagation edge still requires its own admitted target-owner fragment plus source/target revision, privacy, idempotency, retry/compensation and projection contract. INF-3L/INF-3N formalize no generic Economy path and do not make other consumers eligible | a separately designed target-owner edge and updated continuation gate; until then no generic consumer registry or other-domain write |
| INF-4 production-equivalent branch evolution and complete group simulation | isolated evidence/projection plus finite Organization/Government scenario rows, INF-4N's one Government passed-inspection promotion, INF-4O's one Organization supply promotion, and one schedule-gated merge | no approved branch-domain settlement/event-family/receipt owner exists for arbitrary owner fragments; only the exact INF-4N Government source admission -> scenario -> production inspection row and INF-4O Organization source admission -> scenario -> production commerce row are admitted, and a population/NPC/social truth owner is expressly absent | an independently approved existing-owner contract for each further fragment, or keep all non-listed branch inputs and promotion zero-write |

This matrix records a blocked design state, not a claim that INF is complete.

### 2026-08-15 owner-contract audit

The remaining INF-2 blocker was rechecked against the existing Government,
Commerce and Economy authorities. `GovernmentAuthority` accepts a supplied
`policy_revision` while writing permit, inspection and tax facts; it has no
canonical policy-registration event, policy projection, lifecycle reader or
policy receipt. `CommerceAuthority.accept_commitment()` and `record_delivery()`
assemble the already closed commitment, custody and recovery-obligation
fragments, but neither defines an account debit/credit completion outcome or a
payment compensation rule. The only admitted account-transfer lifecycle remains
the same-Economy-stream INF-2J row. Therefore neither Government nor Commerce
is an owner-contract fallback for caller-open registration, arbitrary payment,
or generic cross-domain settlement. Unknown requests must continue to reject
before `append_batch()`.

`DebtAuthorityService` previously had the same formal-spine gap. INF-2L now
migrates only its existing fixed simple-debt event family through
`GameplayCommandEnvelope -> DebtSettlementPlan -> owner fragments -> one
append_batch()` with an authority-scoped redacted outbox and replay evidence.
This supplies no fallback for caller-open policy registration, arbitrary
payment policies, or generic cross-domain settlement: the closed plan rejects
caller-selected streams and event types before append.

Innovation, civilization diffusion, branch promotion outside INF-4N's Government inspection row and INF-4O's Organization supply row, external data ingestion,
generic work, population/NPC/social truth, SOC-1, GAME-1, P6 and P7 are not
implicit INF tasks. They remain blocked until separately approved owner-bound
contracts exist.

## User-directed deferral

On 2026-08-14 the user explicitly deferred complete group simulation.  It is
therefore not an active INF completion target for the present continuation,
but it is not implemented, accepted, or silently removed from the August
mainline gap. `branch_promotion_unsupported` remains a required zero-write
result outside INF-4N and INF-4O: Government now owns one production-equivalent
passed-inspection settlement/event/projection/receipt/writeback contract and
Organization owns one supply commerce settlement/event/projection/receipt/writeback
contract, but no generic promotion authority exists. Work may
continue only on already-owned bounded INF rows; the deferral does not permit
creating a population/NPC/social truth owner or a second event store.
