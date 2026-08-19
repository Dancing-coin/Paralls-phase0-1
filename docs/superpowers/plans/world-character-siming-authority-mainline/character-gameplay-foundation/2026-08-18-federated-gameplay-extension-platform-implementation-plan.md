# Federated Gameplay Extension Platform Implementation Plan

Status: `INF-P P1 binding sequencing implemented and verified; package content and row bindings remain separately unapproved`

Date: `2026-08-18`

This plan turns the Federated Gameplay Extension Platform design into an
ordered approval and implementation sequence. It stops before every mutable
runtime surface until the platform schema, canonicalization, and immutable
admission boundary receive explicit approval.

## Guardrails

- Reuse the existing `GameplayPatchManifest`/patch admission path when and if
  its extension is approved; do not create a second manifest or registry.
- Keep `GovernedAuthorityContractCatalog` immutable/read-only.
- Keep package content, Rule IR, character needs, and agent agreements as
  proposal inputs, never committed truth.
- Use only an already approved owner contract for any eventual write.
- Do not add a generic writer, resolver, router, registry writer, coordinator,
  transform engine, treasury, payment/transfer API, or settlement authority.
- Do not add a second runtime, store, bus, clock, or scheduler.
- Preserve zero-write behavior for unknown, stale, private, conflicting,
  duplicate, or caller-selected authority inputs.

## Ordered Phases

### Phase 0 - Platform design approval packet (completed)

Review and approve or reject:

- logical platform record vocabulary and schema-version boundary;
- package identity/revision/dependency fields;
- declaration and binding separation;
- owner operation descriptor slots and fixed source/event/privacy/revision/
  receipt/replay/terminal/compensation boundaries;
- restricted predicate vocabulary and owner-derived evidence proof model;
- deterministic selection grammar and precompiled cross-domain recipe types;
- canonical JSON and digest derivation;
- candidate/active immutable lifecycle;
- conflict, disable, upgrade, and replay retention rules;
- owner-bound eligibility proof and privacy boundary.

Deliverable: approval packet and explicit gate-by-gate user disposition. No
code or schema edit. Disposition is approved and recorded in the packet.

### Phase 1 - Platform schema decision (current; design-only)

Only after Phase 0 approval, decide whether the existing
`GameplayPatchManifest` can receive the logical sections through a compatible
read-only adapter. Record exact field names, schema version, validation order,
and backward-compatibility behavior.

Deliverables: [schema decision design](../../../../specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-schema-decision-design.md)
and [schema decision implementation plan](2026-08-18-federated-gameplay-extension-platform-schema-decision-implementation-plan.md)
covering compatibility, logical fields, version migration, validation order,
and verification planning. These deliverables are not schema implementation
approval. Still no runtime write path, catalog row, RED tests, or Harness.

### Phase 2 - Canonicalization and digest decision

Freeze the canonicalization algorithm, semantic array ordering, duplicate
handling, digest exclusion rules, dependency/schema digest inputs, and the
distinction between declaration and complete-content digests.

Deliverable: approved canonicalization record and deterministic fixtures plan.
Do not calculate or record `package:industrial-facilities:v1`'s digest before
the complete manifest is frozen under the approved schema.

### Phase 3 - Immutable admission boundary

Design and approve candidate validation, active-set selection, disable and
upgrade evidence, dependency/conflict checks, package revision pinning, and
the read-only package-to-capability binding boundary. Define owner operation
descriptor resolution, restricted predicates, deterministic unique selection,
owner-derived proof provenance, and precompiled cross-domain recipe lookup.
Verify that no package or caller can register a capability or choose owner
contract fields.

Deliverable: immutable admission contract. No generic runtime registry.

### Phase 3A - Binding Boundary Approval Gate

This is a separate approval gate, not an implementation substep. Approve the
read-only binding relation from a package declaration to exactly one immutable
owner operation descriptor and, where allowed, exactly one precompiled recipe
type. Multiple matches, missing descriptors, arbitrary predicate families,
caller proofs, or package-built multi-owner fragments remain zero-write.

Deliverable: binding-boundary approval record. No schema, catalog, tests,
Harness, package freeze, or runtime change.

### Phase 4 - Row-specific package content (paused for current task)

After Phases 1-3 are approved, freeze one complete immutable package revision.
For INF-1AG this means the exact industrial package definitions,
`oven -> kiln` declaration, policy revision, eligibility reference, all
dependencies/schemas/replay references, and derived canonical content digest.

Deliverable: user-confirmed package identity/revision/digest. This is a content
gate, not an implementation approval.

### Phase 5 - Row-specific owner admission (paused for current task)

Verify the fixed owner contract against the package declaration. For INF-1AG,
Construction must derive the acquisition proof bound to facility/project,
exact acquisition stream revision, current facility revision and source kind.
The package still cannot choose owner, stream, event, privacy, receipt,
compensation, or target semantics.

Deliverable: immutable catalog row and owner-bound verifier design approval.

### Phase 6 - Focused RED and independent Harness (paused for current task)

Only after all prior gates are approved, write RED tests for success,
zero-write rejection, privacy, revision, idempotency, receipt, full replay,
and checkpoint-tail replay. Add an independent Harness profile with selectors
for the same assertions.

Deliverable: failing focused suite plus independent Harness specification.

### Phase 7 - Narrow owner vertical (paused for current task)

Implement through the existing
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`
spine. The existing owner builds the fixed event vector and append-derived
receipt; the platform only admits and supplies typed references/proofs.

Deliverable: focused tests and Harness green, replay/privacy evidence recorded,
no generic surface introduced.

### Phase 8 - Audit and continuation closeout

Update the completion audit, remaining-scope matrix, package/INF README,
checkpoint, and verification record. Report the row separately as fully
implemented and verified, implemented narrow vertical, owner-contract blocked,
or unimplemented. Preserve environment-limited failures as limits, not passes.

## Stop Conditions

Stop before implementation if the platform schema, canonicalization,
immutable admission boundary, package digest, owner contract, or replay/privacy
contract is not approved. Missing fields are blockers; defaults and implicit
policy are forbidden. A platform design approval does not itself unblock
INF-1AG or any other row.

The independent platform design task is complete. August INF A-D remains
paused. Do not enter row-specific package content, package freeze, digest
derivation, catalog admission, RED tests, Harness, row binding, or runtime
implementation from this completed design plan. A later file-by-file
schema-v2 implementation plan is independently gated and not yet approved.

## Evidence Requirements

For any future implementation, retain the focused test result, independent
Harness report, append-derived receipt evidence, owner projection/outbox,
full replay, checkpoint-tail replay, privacy/revision/idempotency evidence,
and zero-write rejection evidence. Documentation-only progress in Phases 0-3A
must be reported as such; Phases 4-7 remain paused for this task.

## INF-P Implementation Result

The explicit INF-P implementation authorization supersedes the former schema
implementation hold for platform mechanics only. The existing
`GameplayPatchManifest` now accepts only the approved `(2, "1.0")` extension
pair, derives and checks declaration digests before retaining normalized
immutable declarations, preserves byte-compatible v1 serialization and digest
behavior, and reuses the existing candidate/active/snapshot path. P1 permits a
complete non-empty request to install as a candidate after package-local
validation, then requires exact-one read-only descriptor resolution inside the
existing active-set composition. It retains package/content/declaration/
descriptor/active-set pins in snapshots and lifecycle replay; unknown,
multiple, and mismatched descriptors fail before mutation.

Evidence: `16 passed` in
`backend/tests/test_inf_p_federated_gameplay_extension_platform.py`, `45
passed` in the existing patch/lifecycle/catalog regression suite, and the
green `inf-p-federated-gameplay-extension-platform` Harness profile with 12
selectors. This result does not freeze a real package, calculate a real package
digest, add a business catalog row, bind a row, or execute an INF-1/2/3/4
vertical.
