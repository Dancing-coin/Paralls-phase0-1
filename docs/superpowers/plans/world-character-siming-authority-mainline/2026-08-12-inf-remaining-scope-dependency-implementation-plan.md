# INF Remaining Scope Dependency Implementation Plan

Status: `已批准的 INF 窄纵切完成并验证；八月 INF 主线仍未完成`

Date: `2026-08-12`

## Reprioritization: Reusable Contract Substrate

Before any additional broad owner-row, ecology-consumer, obligation-policy or
branch-promotion work, execute the [reusable contract substrate plan]
(2026-08-16-inf-reusable-contract-substrate-implementation-plan.md).
It consolidates the existing pure state evaluator, closed obligation lifecycle,
owner-fragment settlement plan, finite ecology admission and deterministic
branch replay boundary. It does not authorize generic registration or writing;
it reduces future row work only after its own multi-owner reuse evidence is
green.

## Sequence

1. [x] Execute INF-1R only for the named semantic-to-construction production finish mapping.
2. [x] Execute INF-2R only for construction due completion; ecology remains blocked.
3. [x] INF-1X closed vocabulary completed for the only named one-shot
   production-finish row; durable lifecycle rows remain blocked pending INF-2X
   registered owner events.
4. [x] Execute INF-2X only for `policy:construction_due_completion@1`: owner-stream settled/cancelled events, registration, committed source obligation identity, idempotency, revision/privacy/replay; retry/compensation and all other owner rows remain zero-write rejected. Reverified 2026-08-13 after a forged cancellation identity was shown zero-write.
5. [x] INF-3R-A and INF-3R-B verified the committed frost source, deterministic due-run selection, and revisioned construction recipe view. INF-3R then verified one fixed frost -> due production finish path through the construction-owner fragment, existing append/outbox/replay/scoped projection, source/target/privacy/retry/compensation zero-write fences, idempotency, and full/checkpoint-tail replay. It is not a general hazard consumer baseline.
6. [x] Execute INF-3X by extending `EcologyHazardAuthority` only: `gameplay:ecology:{region_ref}` now has canonical region/environment/resource/crop/hazard record and retirement rows, owner fragments, scoped projection and replay evidence. INF-3C through INF-3F verify caller-shaped bounded propagation. INF-3M additionally derives one or two bounded next waves from a committed project-visible weather-front event and canonical adjacency, then reuses the same Ecology-only owner batch. It does not add scheduling, retry/compensation, a generic graph runtime, or a consumer registry; INF-3G/3H cover fixed Construction edges and INF-3I covers one exact weather-front -> existing Organization commerce commitment edge under its own target-owner contract.
7. [x] Execute INF-3Y after INF-3X source evidence: `ecology-hazard:frost-to-construction-finish:v1` is the sole project-visible canonical frost -> one construction due-finish fragment. Unknown/disabled/direct/stale/privacy inputs are zero-write; every other consumer edge remains blocked.
8. [x] Execute INF-4R only from `SocialFactAuthority.view_for`: typed recipient/time/digest/source-vector input, deterministic planner admission and merge-time stale-source zero-write are verified by `infra-population-world-mode`; capability and schedule inputs remain blocked.
9. [x] Execute INF-4X after user-authorized source contract: existing `SocialFactAuthority` now owns household membership source rows and existing `OrganizationAuthority` owns organization schedule rows; typed scoped inputs, planner pinning, privacy, zero-write and replay are independently verified by `infra-household-org-source-projection`. INF-4Y-A independently admitted `CivilizationCapabilityAuthority` lifecycle/read infrastructure, and INF-4Y subsequently admitted separately verified authority-scoped capability-gated `supply` and `inspection` consumer bindings. All other consumer bindings remain blocked; neither step starts P7.
10. [x] INF-4Z bounded rows implemented after rerunning INF-2X/INF-4X/branch predecessor Harnesses: `supply -> OrganizationAuthority.build_commerce_commitment_fragment`, `inspection -> GovernmentAuthority.build_commercial_inspection_fragment` plus an independently asserted report-scoped redacted Government outbox/replay projection, fixed-base branch digest/tail pinning, caller-selected game/simulation/preview cadence-budget, preview production zero-write, and generic `work` zero-write. The historical P3C `PopulationBatchPlan` generic merge is separately asserted zero-write by the INF-4Z Harness and is not a production path. A separately verified Production-owned source package records canonical `production-completed` evidence through `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch`, with actor-scoped outbox/view, source revision and replay evidence. A separate verified consumer then admits only that frozen worker-scoped Production evidence -> Economy wage event, pinning source event/vector/digest, wage policy and target revision. INF-4Z-A separately verifies the user-authorized `ReferenceDataAuthority` lifecycle, authority-only frozen view, rejected revoked/forged/stale/scope inputs, and non-production authorized preview. It is not external ingestion or branch promotion. INF-4Y has separately verified capability-gated supply and inspection edges; all other capability consumers still require owner admission.

Each step blocks on its predecessor's focused report, full/checkpoint-tail
replay proof, zero-write failures, scope filtering, and `git diff --check`.
Do not begin P6/P7 merely because an INF-R, INF-X, INF-Y, or INF-Z document exists.

The numbered rows above are completed narrow prerequisites, not the August INF
completion plan. Execute the following remaining mainline packages strictly in
order after their own spec, plan and RED focused tests exist:

11. [ ] INF-1: turn serialized effect expiry proposals into owner-submitted,
    replayable `ScheduledObligation` lifecycle events; complete the minimal
    StateDefinition and constrained-selector closure without direct rule writes.
    INF-1B/1D/1E have verified the three closed semantic proposal -> Survival
    `state:cold@1`, `state:overheated@1` and `state:dehydrated@1` owner submissions. INF-1F now stores these same three
    existing rows as one registered state/effect policy matrix, without admitting another owner. INF-1G additionally verifies
    only `effect:maintenance_required -> state:maintenance_due@1` on an acquired existing Construction facility stream,
    including owner-side exact semantic-vector and fixed-pair fences; it does not admit a generic second-domain matrix. INF-1C has verified finite
    proposal-only `all(...)`/`any(...)` guard composition; generic owner
    coverage and lifecycle closure remain open. INF-1H additionally verifies
    closed dispatch for the four registered rows, including direct-helper
    stale-vector and non-canonical Survival definition zero-write fences; it
    does not make owner dispatch generic. INF-1J separately verifies exactly
    `effect:wage_accrual_due -> EconomyAuthority` through a registered closed
    mapping and effect definition, fixed wage stream/project/vector inputs,
    owner-built append path, idempotency/revision/privacy zero-write fences,
    and lifecycle full/checkpoint-tail replay. It remains one additional row,
    not generic owner dispatch or INF-1 closure.
    INF-1K separately verifies exactly two existing Survival state-action rows:
    `effect:state_dispel` and fixed `effect:state_transform_recovery`. Its
    command fingerprint is folded into the existing owner-plan
    idempotency digest, so a changed snapshot with the same key is zero-write
    rejected. This remains a closed owner-local action mapping, not generic
    action dispatch or INF-1 closure.
    INF-1O makes those two actions derive from the three existing Survival
    `StateDefinition` contracts before a fragment is built: only dispel and
    the fixed `state:recovering` target are accepted. It has independent pure
    decision, owner settlement, zero-write, idempotency, privacy and replay
    evidence, and does not admit generic state actions or a writer.
    INF-1L separately verifies exactly `effect:frost -> state:frosted@1`
    through the existing Ecology owner and `gameplay:ecology:{region_ref}`.
    It appends fixed apply/open and expiry/settled event pairs through the
    existing coordinator, with refresh, idempotency, privacy, revision and
    full/checkpoint-tail replay evidence. It is one Ecology row, not a generic
    lifecycle router or additional consumer edge.
    INF-1M separately verifies a finite seven-row owner-contract reader for
    the four Survival rows, Construction maintenance row and the two Ecology
    rows. The existing Survival, Construction and Ecology append boundaries
    each validate their contract before writing; forged contract metadata is
    zero-write rejected. Historical unregistered Survival compatibility input
    remains outside the matrix and is still rejected by downstream admission.
    This is not open registration, generic dispatch or INF-1 closure.
    INF-1N separately verifies the existing Construction facility stream's
    fixed `maintenance_required -> maintenance_due` state apply -> event-derived
    obligation open -> expired/settled path. Its Construction owner retains the
    sole write path, and stale/wrong-source/second-active/retry/cancel/
    compensation inputs are zero-write. It is not generic lifecycle closure.
    INF-1P then verifies one bounded Construction action: only
    `effect:maintenance_state_dispel` may clear the active
    `state:maintenance_due` and cancel its exact committed expiry obligation in
    the same Construction owner batch. Ordinary lifecycle cancellation remains
    zero-write; transform, repair/payment/material facts and all other actions
    still lack an owner contract.
    INF-1Q then consolidates only the existing seven state contracts and one
    Economy wage-obligation contract into an immutable lifecycle reader with
    fixed terminal events, action allowance, outbox, revision, idempotency and
    replay metadata. Existing semantic routes/actions read it before their
    owner fragment; it neither registers a row nor routes Ecology frost through
    generic semantic settlement.
    INF-1Z adds only the exact Ecology frost dispel action: after the fixed
    semantic proposal revalidates the canonical project-visible hazard/crop/
    region relation, `EcologyHazardAuthority` appends `crop_state_dispelled`
    and the exact open obligation cancellation in one existing ecology batch.
    It does not admit generic Ecology actions, repair/transform semantics or
    generic dispatch.
    INF-1AC separately admits exactly one Ecology-to-Survival row:
    project-visible committed `weather:frost` plus INF-4AC's active
    profile-to-region evidence can enter the existing
    `effect:cold_exposure -> state:cold` Survival row.  The existing Survival
    owner revalidates both source heads and appends only its current
    `state_applied` / `obligation_opened` event family with its own receipt and
    replay reader.  This does not admit other weather, states, profiles,
    fanout, retry, compensation, a consumer registry, or generic lifecycle
    closure.
12. [ ] INF-2: generalize the event-derived lifecycle across construction and
    one survival/economy owner, including bounded catch-up, retry/cancel/
    compensation and activation pending merge while retaining one clock/store.
    INF-2B/2E/2F/2N verify exactly four released `survival_state_expiry` handoffs
    (`cold`, `dehydrated`, `overheated`, `fatigued`) with separate activation and Survival receipts. INF-4AB independently
    closes the same pre-existing Survival route as its second exact INF-4 batch row, including the single-append receipt boundary. INF-2C verifies one Economy
    `policy:economy_wage_accrual@1` open/retry/cancel/expired/settled/compensated row;
    compensation reverses only accrual semantics and does not admit payment.
    The verified Economy wage row keeps its lifecycle registration on
    `EconomyAuthority`; it is closed rather than caller-registered. INF-2F verifies the third existing-owner-only `state:overheated@1` row
    with a separate activation and Survival receipt. INF-2G closes the
    scattered pending admission conditionals into one immutable four-row reader
    for those three Survival rows and the existing schedule-gated Organization
    row; it preserves separate activation and owner receipts. Open registration
    and a unified cross-domain receipt remain open. INF-2H additionally moves
    the existing `EconomyAuthorityService` account opening, same-stream
    transfer and budget reservation writes from its legacy raw helper to the
    formal envelope/plan/append path, with authority-scoped redacted outbox and
    append-derived receipt. It does not admit payment obligations, policy
    registration or arbitrary cross-domain settlement. INF-2I additionally
    formalizes the existing named Organization/Economy commerce commitment:
    only fixed Organization, Economy, Inventory and optional Wage fragments can
    enter one append batch, whose duplicate admission, redacted authority
    outbox, receipt and replay are independently verified. It does not admit a
    generic cross-domain settlement writer. INF-2J additionally verifies the
    fixed `policy:economy_scheduled_account_transfer@1` Economy row: its
    event-derived open/due/settled/cancelled/expired lifecycle writes the two
    existing same-currency account balances and its terminal event in exactly
    one formal Economy append batch. It does not admit caller registration,
    generic payment, account reservation release, retry/compensation, or
    arbitrary cross-domain settlement. A 2026-08-15 owner-contract audit
    rechecked `GovernmentAuthority`, `CommerceAuthority` and the existing
    Economy ledger: Government has supplied policy revisions but no
    event-sourced policy-registration lifecycle or receipt; Commerce has fixed
    commitment/delivery fragments but no payment-completion or compensation
    outcome. They are not fallback owners for open registration or generic
    settlement, so no runtime code is authorized by this audit. INF-2L also
    migrates the existing fixed simple-debt owner through
    `GameplayCommandEnvelope -> DebtSettlementPlan -> owner fragments -> one
    append_batch()` with a redacted authority outbox and replay evidence; it
    admits only its existing simple-debt event family, not arbitrary payment,
    caller registration, or a generic cross-domain writer.
    INF-2M then closes `ObligationSettlementCoordinator` admission to six
    existing owner lifecycle registrations and their closed owner-local event
    families. Policy-less, unknown, forged, widened caller registrations,
    terminal-plus-smuggled-event fragments, owner-privacy scope overrides, and
    Construction due terminals without the exact committed `run_started` source
    event are independently zero-write rejected before append. Caller-provided
    registrations are normalized so they cannot weaken canonical
    `requires_committed_open` or other required admission conditions. It does
    not open policy registration or add a generic writer.
    INF-2T additionally makes those closed event-derived records available as
    one read-only bounded `open/retry -> due -> terminal` time view. Its
    full/checkpoint-tail equivalence applies the same explicit shared tick and
    catch-up budget after replay; it does not persist due state, advance a
    clock, append a batch, select an owner, or relax the registration fence.
    INF-2W then materializes the same registered event-derived records as
    read-only `ScheduledObligation` inputs, preserving committed opening
    provenance and projected stream revisions without append, owner selection,
    receipt creation, or clock advancement. INF-2Y replaces the synthetic
    lifecycle catalog placeholder with five exact existing-owner state rows
    and makes those owners validate their immutable contract before their
    current append path. Neither package opens caller policy registration,
    generic lifecycle dispatch, or arbitrary cross-domain settlement.
    INF-2Z then adds one separately admitted Economy tax-obligation row sourced
    from a committed `gameplay.economy.tax_due_recorded` event. Its open and
    terminal events remain on `gameplay:economy`, use the existing envelope /
    SettlementPlan / append spine, and settle only obligation state without
    account mutation. It does not add payment truth, caller-open registration,
    compensation, or arbitrary cross-domain settlement.
13. [ ] INF-3: extend `EcologyHazardAuthority` with process lifecycle, one
    non-frost process/hazard and budgeted target-owner edges. INF-3B has
    completed `seasonal_process -> Construction maintenance`, and INF-3G has
    completed the exact `weather-front -> Construction maintenance` edge;
    fanout and additional domain targets remain open. INF-3D has a
    separate formal adjacency/revision/privacy/idempotency contract for one
    explicit, no-repeat Ecology-only path of at most three hops; it does not
    authorize inferred graph traversal or any consumer edge. The legacy
    authority-only Economy dynamic-quote helper is not an admitted target:
    it lacks the required envelope/SettlementPlan, project-scoped ecology
    admission and owner-receipt contract. INF-3N separately admits only one
    fixed same-owner Economy fanout: a weather-front source plus two canonical
    existing quote refs becomes two `dynamic_quote_published` events in one
    Economy owner batch. It does not authorize arbitrary fanout or another
    consumer family.
14. [ ] INF-4: replace metadata-only preview with replayable isolated branch
    events/projections and settle one existing household/organization schedule
    input through revision/activation lock; INF-4C has completed one
    event-derived released `schedule_gated_supply` row. INF-4F additionally
    records isolated existing-owner fragment-builder validation for `supply` and
    `inspection`; INF-4G additionally rebuilds only redacted branch-local planned
    commitment/inspection consequences from accepted evaluations. INF-4H settles
    one accepted supply candidate through the existing Organization owner, and
    INF-4I settles one accepted passed-inspection candidate through the existing
    Government owner, each onto a non-production scenario stream in the same
    event store with scenario replay/outbox evidence and production replay
    isolation. INF-4J also settles one accepted failed-inspection candidate as
    a fixed Government `follow_up_required` remediation record on that same
    non-production stream. INF-4L now records and replays a scoped accepted
    preview-evidence event before Government revalidates either inspection row;
    INF-4K derives one receipt from the fixed evidence-backed remediation row.
    INF-4M additionally persists the existing BranchPreviewAuthority's accepted
    redacted buffer on its existing creator-debug branch stream, and INF-4P
    appends one fixed redacted accepted owner-consequence evolution event to the
    same stream, so a fresh authority can reconstruct snapshot plus evolution
    without a production write.
    INF-4AC additionally closes only the prerequisite active-profile placement
    map: the existing ProfileActivationAuthority revalidates one committed,
    project-visible Ecology region event and appends one project-scoped
    `population.activation.region_assigned` event to its existing population
    stream. This is not a Survival consumer, generic location system, or
    population truth owner.
    Generic remediation lifecycle, other owner scenario
    settlement, generic branch receipts and promotion remain zero-write/incomplete.

## Closure-Contract Gate

Rows 11-14 remain unchecked because their true closure conditions exceed the
verified finite verticals. Do not advance them by adding another sample row.
Before any new code, use the `Mainline Closure Owner-Contract Matrix` in the
dependency design to name an existing authority, stream, event family, scoped
projection, revision/idempotency rule, privacy boundary, owner receipt/replay
reader and zero-write rejection for the exact missing capability. If any field
is absent, update the formal design with the blocked owner and add no runtime
or writer. This gate specifically preserves the finite INF-1 matrix, the
single-store INF-2 receipt boundary, the finite eight-edge INF-3 continuation fence, and
the INF-4 production/promotion zero-write boundary outside the separately
admitted INF-4N Government passed-inspection and INF-4O Organization supply
rows.

SOC-1, GAME-1, P6 and P7 are explicitly excluded until these rows finish.

## User-directed deferral

Complete group simulation is deferred by the user as of 2026-08-14.  Leave
INF-4's unchecked closure row and the formal blocker visible, but do not make
it the next implementation package. Production-equivalent branch promotion
remains an unsupported-input, zero-write boundary except for INF-4N's existing
Government-owned passed-inspection and INF-4O's existing Organization-owned
supply settlement/event/projection/receipt contracts.

Continuation preflight: every resumed turn must run
`infra-continuation-gate` and read its report before changing the next package.
The current report proves INF-3X's canonical owner map, the finite eight-edge
registered consumer inventory, and the registered-admission identity fence. It does not authorize any
additional consumer or implementation outside the exact formal contract.

## Mandatory completion steps for each package

1. Lock an owner/event/projection map and add failing focused tests.
2. Implement only the stated vertical through the existing append/outbox/replay
   path.
3. Add a separate Harness assertion per claimed capability and store the report.
4. Run focused tests, full pytest, and `git diff --check`.
5. Update the matching August analysis, formal spec, plan, and evidence report
   with proven scope and remaining gaps.
