# INF-1AG Construction Candidate Owner-Admission Plan

Status: `implemented narrow vertical: exact frozen mill -> mill_reinforced row verified; frozen oven-to-kiln row also remains verified`

## Completed Design Steps

1. Read the existing Construction event projector and fixed owner operations.
2. Exclude the already implemented facility repair/compensation and
   `bakery -> bakery_reinforced` rows.
3. Review the three closest committed source-to-outcome paths: additional
   facility transform, due production completion, and completed worker
   evidence.
4. Record that the latter two are already closed owner rows, while an
   additional transform lacks a literal source kind, target kind, immutable
   eligibility/policy evidence, and terminal/reversal decision.
5. Define the fixed package-declared transform family: existing Construction
   owner, facility stream, `facility_transformed@1`, project privacy,
   authority-derived idempotency, append receipt, full/tail replay, and v1
   terminal/no-compensation semantics.
6. Record the package declaration fields (`source_kind`, `target_kind`,
   `eligibility_refs`, `policy_revision`, `package_revision`, `content_digest`)
   and the exact schema, eligibility-resolver, reducer, and catalog blockers.
7. Update the completion audit, remaining-scope matrix, INF-1 README, and
   continuation checkpoint. No test, Harness, catalog, or runtime change is
   part of this plan.
8. Close the design for the six-field declaration payload, derived
   `declaration_digest`, canonical encoding, duplicate/conflict selection, and
   the no-caller-selection rule.
9. Close the design for a Construction-row-specific eligibility proof,
   including facility/project subject binding, owner/event/revision/privacy
   pins, and derived `proof_digest`; keep the accepted reference families and
   verifier implementation as later approval gates.
10. Produce a design-only content-authoring packet for future package authors:
    identity/revision/digest rules, facility/policy templates, eligibility
    mapping, conflict selection, lifecycle/replay and a non-admitted example.
    It must not add a manifest schema or authorize implementation.

## Preconditions For Runtime Execution

The complete immutable `package:industrial-facilities:v1` manifest is frozen
in the [2026-08-19 freeze record](../../../specs/world-character-siming-authority-mainline/inf-1/2026-08-19-inf-1ag-industrial-facilities-v1-freeze-record.md).
The explicitly approved outer and inner version fields both equal `1.0.0`, and
the canonical declaration/content digests were independently verified. The
current repository's executable `package:frost-farm:v1` still cannot
substitute. The exact immutable descriptor/catalog row and binding admission,
verifier, reducer, RED-to-green tests, Harness profile, and Construction
runtime are now complete in their separately approved sequence for this row.

## Approved INF-1AG Row Plan (Completed Exact Runtime Gate)

This was the implementation plan for the exact approved row. The manifest,
descriptor/catalog admission, verifier, reducer, append path, focused tests,
and independent Harness are now complete for this one row only.

### Fixed row

```text
outcome_family   = construction_facility_package_declared_transform@1
capability_ref   = capability:construction-facility-package-declared-transform@1
package_id       = package:industrial-facilities
package_revision = package:industrial-facilities:v1
source_kind      = oven
target_kind      = kiln
policy_ref       = policy:industrial-facilities:oven-to-kiln
policy_revision  = policy:industrial-facilities:oven-to-kiln@1
eligibility_ref  = construction:facility-acquired@1
owner            = ConstructionProductionAuthority
project_binding  = construction_plot_as_project@1
source_event     = gameplay.construction_production.facility_acquired@1
target_stream    = gameplay:construction_production:{facility_ref}
event_family     = gameplay.construction_production.facility_transformed@1
privacy          = project-scoped
terminal         = v1 terminal, no compensation
```

`content_digest` is the frozen value
`sha256:41e1b40bcd1fd13e1692f2f51aed7dea6dceee0b1605bf215fe6c673fcd11f88`.
It was derived from the complete normalized immutable
`GameplayPatchManifest` canonical JSON; neither caller, package author, agent,
nor this plan selected it.

### Ordered Implementation Stages and Evidence

The exact descriptor and governed contract metadata were approved and
implemented in the existing immutable catalog, with focused binding evidence.
The [admission packet](../../../specs/world-character-siming-authority-mainline/inf-1/2026-08-19-inf-1ag-construction-owner-operation-descriptor-admission-packet.md)
records the fixed fields. The later runtime approval authorized only the
owner-bound verifier, reducer, RED-to-green tests, Harness, and append spine
listed below.

1. **Manifest freeze gate:** `Complete.` The manifest, explicit equal version
   fields, and exact digest claims are recorded in the 2026-08-19 freeze
   record. Missing, inactive, malformed, or mismatched digest claims remain
   zero-write.
2. **Row-specific eligibility verifier:** **Complete.** Implemented only the
   `construction:facility-acquired@1` proof mapping to the existing
   `ConstructionProductionAuthority` and committed
   `facility_acquired@1`. Bind `facility_ref` to the committed
   `facility_acquired.facility_ref`, `project_ref` to
   `facility_acquired.plot_ref` under `construction_plot_as_project@1`, and
   pin acquisition stream revision, current facility revision, facility stream
   head, `source_kind=oven`, project privacy, package revision, policy revision,
   and derived proof digest. Unknown, missing, ambiguous, stale, private,
   forged, or mismatched evidence is zero-write.
3. **Construction declaration reducer:** **Complete.** Added one declaration-validated branch
   for the exact `oven -> kiln` row to the existing
   `ConstructionProductionAuthority`. Keep the owner-fixed stream,
   `facility_transformed@1` event family, one revision advance, project-scoped
   outbox, authority-derived idempotency key, and append-derived receipt. Do
   not loosen the existing bakery-only guard into a generic transform.
4. **Immutable catalog row:** **Complete.** Added only the exact capability row after the
   digest gate, with owner/stream/event/privacy/receipt/replay/terminal fields
   fixed by this contract. The package declaration cannot write or modify the
   catalog.
5. **RED-to-green tests:** **Complete.** After digest and approval, focused
   focused tests for success, exact/changed duplicate behavior, unknown or
   inactive package, digest mismatch, unknown kind, missing/ambiguous/stale/
   private/forged acquisition proof, facility/project binding conflict,
   source/facility/stream revision conflict, receipt/privacy, full replay,
   checkpoint-tail replay, prior transform, and terminal no-compensation.
6. **Independent Harness:** **Complete.** Added one profile for the exact capability and
   independently assert each zero-write and replay/privacy/receipt boundary.
7. **Append-spine implementation:** **Complete.** Routed the typed facility intent through
   the existing `GameplayCommandEnvelope -> SettlementPlan ->
   GameplayEventStore.append_batch()` path. The Treasury, Economy, Inventory,
   Production, payment, material, permit, technology, and generic action
   surfaces remain untouched.

### Explicit implementation stop conditions

The plan stops before stage 2 until the exact immutable descriptor/catalog row
and binding admission are separately approved. It also stops before append if any owner, stream, event, privacy,
receipt, revision, source, binding, eligibility, or declaration selection is
caller-supplied. `bakery -> bakery_reinforced` remains owned by INF-1AF and is
not a second admission through this plan. V1 has no reversal, downgrade,
retry-as-new-transform, compensation, fanout, combined receipt, payment,
material, or production-output semantics.

## 2026-08-19 Implementation Evidence

The approved exact row is complete. `ConstructionProductionAuthority` resolves
only the active frozen industrial package binding, validates the project-visible
committed `facility_acquired` source, facility/project binding, source/facility/
stream revisions, declaration/content/descriptor pins, and the fixed
idempotency key. It writes one project-scoped `facility_transformed` event via
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.

Focused evidence is `12 passed` in
`backend/tests/test_infra_construction_facility_package_transform.py`; the
independent `infra-construction-facility-package-transform` Harness is green.
It covers success, zero-write invalid source/package/binding/digest/privacy/
revision cases, receipt, idempotency, full replay, checkpoint-tail replay, and
terminal/no-compensation semantics. This completion applies only to the frozen
`oven -> kiln` row, never to a generic transform family.

Verification caveat: the exact INF-1AG focused suite, descriptor/binding
admission Harness, Construction transform Harness, and continuation gate are
green. After stale selector and predecessor evidence repairs, a fresh all-INF
inventory reran all 124 profiles and every profile passed. Full pytest remains
`3561 passed, 1 failed` due to the host permission error writing the
workspace-parent `.env`; this is an environment limitation, not an INF-1AG
runtime failure.

## Prohibited Scope

This plan does not authorize a new owner, generic action/transform, caller
selection of owner/stream/event/revision/privacy/receipt/fragment, a runtime-
writable package registry, catalog writer, router, coordinator, second runtime,
or settlement authority. A package declaration is immutable data only.

## 2026-08-19 Remaining Construction Candidate-Design Pass

Status: `documentation-only complete; no new exact row submitted for approval`

1. Re-read only `ConstructionProductionAuthority`, its committed facility/run/
   maintenance projection facts, immutable package/platform records, and the
   existing INF-1 formal audits.
2. Exclude the completed facility repair, `bakery -> bakery_reinforced`,
   frozen `oven -> kiln`, due-production completion, work-completion evidence,
   and maintenance-state dispel paths from a new row.
3. Record the one remaining source observation: project-visible
   `facility_acquired(facility_kind=mill)` plus current facility/project and
   stream revision pins.
4. Stop before contract design because no formal target kind semantic,
   capability/outcome id, immutable package declaration, policy revision, or
   owner-derived eligibility vector exists for `mill`.
5. Synchronize the candidate design, completion audit, remaining-scope matrix,
   and continuation checkpoint. Do not create a manifest, catalog row, RED
   test, Harness profile, verifier, reducer, event, or write path.

The minimal next approval is one literal `mill -> target_kind` business
semantic together with one immutable package/declaration/policy identity,
non-empty existing-owner eligibility evidence, and an explicit terminal or
alternative lifecycle choice. The fixed Construction owner/stream/event/
privacy/receipt/replay fence is available only after those facts are approved;
it is not a generic transform admission.

## 2026-08-20 Mill Pre-Contract Design Plan

Status: `documentation-only complete; awaiting literal contract approval`

1. Preserve the fixed base: `mill`, committed project-visible
   `facility_acquired@1`, `ConstructionProductionAuthority`, the facility
   stream, `facility_transformed@1`, and project privacy.
2. Record rather than infer the unresolved business fields: target kind and
   semantic; capability/outcome identities; package/version/declaration/content
   identities; policy; non-empty eligibility/predicate/evidence mappings;
   row-specific descriptor/catalog pins; and terminal/reversal/compensation
   choice.
3. Record that source event/facility/stream revisions and facility/project
   binding are owner-derived fences, and that receipt, replay and idempotency
   shape remain fixed by the existing Construction contract without being
   caller-selected.
4. Keep all missing, ambiguous, stale, private, conflicting, duplicate, or
   caller-coordinated requests zero-write.
5. Stop. Do not create a package, calculate a digest, install a descriptor or
   catalog row, add RED tests/Harness, or write a Construction reducer/append
   path until one complete literal `mill -> target_kind` contract is approved.

## 2026-08-20 Mill Reinforcement Implementation Plan (Completed)

Status: `implemented narrow vertical: exact frozen mill-to-mill_reinforced row verified`

### Fixed approved row contract

```text
capability_id       = capability:construction-facility-mill-reinforcement@1
outcome_family_ref  = outcome:construction-facility-mill-reinforcement@1
package_revision    = package:industrial-facilities:v2
source_kind         = mill
target_kind         = mill_reinforced
policy_revision     = policy:industrial-facilities:mill-to-mill-reinforced@1
eligibility_ref     = construction:facility-acquired@1
```

The full contract and all exact proposed refs are in the formal INF-1AG design.
The row changes only facility kind and revision. It must not cause weather,
maintenance, material, inventory, payment, production-output, recipe, permit,
technology or any cross-domain effect.

### Completed gates

1. **Package-content decision:** fixed v2 package-local identity,
   definition/typed-content, and explicit empty arrays without modifying v1.
2. **Package freeze/digest gate:** froze immutable v2 bytes with untrusted
   digest claims; adapter validates normalized declaration digest, then content
   digest; retain the frozen record. Any digest failure is zero-write.
3. **Static admission gate:** installed only
   `descriptor:construction-facility-mill-reinforcement@1` and
   `inf:construction-facility-mill-reinforcement@1` in the existing immutable
   catalog; activation resolves exactly one binding and persists all pins.
4. **Focused RED tests:** added failure tests for every digest/binding/
   source/privacy/revision/idempotency rejection, then success, receipt, full
   replay, checkpoint-tail replay and terminal behavior.
5. **Independent Harness:** added a row-specific profile covering the same
   success and zero-write selectors; it must not reuse v1 evidence as proof.
6. **Narrow owner implementation:** added a row-specific proof verifier and a
   projector/reducer branch accepting only the fixed complete mill vector;
   route through `GameplayCommandEnvelope -> SettlementPlan ->
   GameplayEventStore.append_batch()`.
7. **Verification and documentation:** ran focused tests, its Harness,
   continuation gate and required replay checks; then synchronize formal docs
   without claiming generic transform or August INF A-D completion.

No stage may be reordered or partially substituted. In particular, content
must not be frozen with an empty binding, the active package cannot choose an
authority coordinate, and a reducer cannot be generalized to arbitrary kinds.

### Completion boundary

The frozen v2 record uses equal `2.0.0` versions, `author:repo`, `trust:repo`,
the two exact facility definitions, and explicitly empty unrelated arrays. It
is verified by adapter-derived declaration/content digests and exact-one
descriptor binding. Evidence is `53 passed` relevant tests (with a repository-
local `--basetemp`) and the green independent
`infra-construction-mill-reinforcement` Harness. This completion admits only
the exact row, not arbitrary transforms or another INF row.

## 2026-08-18 Sequencing Closure

INF-P now rejects a non-empty package binding before candidate installation,
while this older plan placed the descriptor/catalog row after package freeze.
The approved row cannot use an empty-binding placeholder because binding data
is part of the normalized manifest and outer digest. The
[sequencing design](2026-08-18-inf-1ag-package-content-readonly-binding-sequencing-design.md)
therefore records the prior gate that was completed before this row: a
candidate-time structural / activation-time read-only binding split on the
existing patch registry. The completed platform amendment enabled the frozen
package, exact descriptor/catalog admission, and this row's focused
Construction vertical only; it does not authorize any further package or
Construction transform.
