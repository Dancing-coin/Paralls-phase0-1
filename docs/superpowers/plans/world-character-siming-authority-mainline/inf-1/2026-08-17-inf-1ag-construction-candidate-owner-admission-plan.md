# INF-1AG Construction Candidate Owner-Admission Plan

Status: `implemented and verified: exact frozen package-declared oven-to-kiln narrow vertical`

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
substitute. The next gate is the exact immutable descriptor/catalog row and
binding admission; verifier, reducer, RED test, Harness profile, and
Construction runtime implementation remain separate approvals.

## Approved INF-1AG Row Plan (Design-Only Gate)

This is the implementation plan for the exact approved row, recorded before
implementation authorization. It does not create any executable artifact.

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

### Ordered Future Implementation Stages

The exact descriptor and governed contract metadata were approved and
implemented in the existing immutable catalog, with focused binding evidence.
The [admission packet](../../../specs/world-character-siming-authority-mainline/inf-1/2026-08-19-inf-1ag-construction-owner-operation-descriptor-admission-packet.md)
records the fixed fields. This does not authorize the owner-bound verifier,
reducer, RED/Harness vertical, or append work.

1. **Manifest freeze gate:** `Complete.` The manifest, explicit equal version
   fields, and exact digest claims are recorded in the 2026-08-19 freeze
   record. Missing, inactive, malformed, or mismatched digest claims remain
   zero-write.
2. **Row-specific eligibility verifier:** implement only the
   `construction:facility-acquired@1` proof mapping to the existing
   `ConstructionProductionAuthority` and committed
   `facility_acquired@1`. Bind `facility_ref` to the committed
   `facility_acquired.facility_ref`, `project_ref` to
   `facility_acquired.plot_ref` under `construction_plot_as_project@1`, and
   pin acquisition stream revision, current facility revision, facility stream
   head, `source_kind=oven`, project privacy, package revision, policy revision,
   and derived proof digest. Unknown, missing, ambiguous, stale, private,
   forged, or mismatched evidence is zero-write.
3. **Construction declaration reducer:** add one declaration-validated branch
   for the exact `oven -> kiln` row to the existing
   `ConstructionProductionAuthority`. Keep the owner-fixed stream,
   `facility_transformed@1` event family, one revision advance, project-scoped
   outbox, authority-derived idempotency key, and append-derived receipt. Do
   not loosen the existing bakery-only guard into a generic transform.
4. **Immutable catalog row:** add only the exact capability row after the
   digest gate, with owner/stream/event/privacy/receipt/replay/terminal fields
   fixed by this contract. The package declaration cannot write or modify the
   catalog.
5. **RED-to-green tests:** only after the digest and user reconfirmation, write
   focused tests for success, exact/changed duplicate behavior, unknown or
   inactive package, digest mismatch, unknown kind, missing/ambiguous/stale/
   private/forged acquisition proof, facility/project binding conflict,
   source/facility/stream revision conflict, receipt/privacy, full replay,
   checkpoint-tail replay, prior transform, and terminal no-compensation.
6. **Independent Harness:** add one profile for the exact capability and
   independently assert each zero-write and replay/privacy/receipt boundary.
7. **Append-spine implementation:** route the typed facility intent through
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

Focused evidence is `11 passed` in
`backend/tests/test_infra_construction_facility_package_transform.py`; the
independent `infra-construction-facility-package-transform` Harness is green.
It covers success, zero-write invalid source/package/binding/digest/privacy/
revision cases, receipt, idempotency, full replay, checkpoint-tail replay, and
terminal/no-compensation semantics. This completion applies only to the frozen
`oven -> kiln` row, never to a generic transform family.

## Prohibited Scope

This plan does not authorize a new owner, generic action/transform, caller
selection of owner/stream/event/revision/privacy/receipt/fragment, a runtime-
writable package registry, catalog writer, router, coordinator, second runtime,
or settlement authority. A package declaration is immutable data only.

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
