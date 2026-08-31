# Federated Gameplay Extension Platform Approval Packet

Status: `design approved; INF-P platform mechanics implemented and verified; no package or row approval implied`

Date: `2026-08-18`

This packet is the review surface for the platform-level design. It does not
approve or implement a manifest schema, package, catalog row, verifier,
reducer, test, Harness, runtime, or append path.

## Decision Scope

The platform supports unlimited future package content **inside already
approved owner operation families**. It does not automatically admit new
facts, new owners, arbitrary settlement, or arbitrary multi-owner event
vectors.

At the time this platform packet was authored, August INF A-D execution was
paused. The later verified INF-P mechanics and independently approved
row-specific work are recorded in the current audit; this packet still never
substitutes for business-row approval or completion evidence.

## Normative Decisions For Approval

| Decision | Normative rule |
| --- | --- |
| Federated authority | Domain owners remain the only writers of their domain facts. Package content, typed intents, predicates, and recipes are not truth owners. |
| Package envelope | One immutable logical package envelope carries identity, revision, definitions, declarations, bindings, dependencies, schemas, replay references, and verification references. It is adapted into the existing patch admission path only after schema approval. |
| Owner operation descriptor | An immutable owner-authored descriptor fixes owner, operation family, accepted intent schema, source/event/stream/privacy/revision/receipt/replay/idempotency/terminal/compensation rules, allowed predicate families, and allowed recipe types. Only named package content slots are fillable by a package. |
| Predicate vocabulary | Predicates are a closed typed vocabulary over owner-derived facts. Composition is limited to typed `all`/`any`/`not` with fixed depth. No arbitrary code, dynamic owner lookup, I/O, clock, randomness, caller proof, or authority selection is allowed. |
| Selection grammar | A typed intent is matched against active declarations and descriptors by exact family, revision, typed slots, subject fences, privacy, revision, and satisfied predicates. Exactly one match is required. Zero or multiple matches are zero-write. No priority, load order, default, or caller tie-breaker exists. |
| Cross-domain recipes | A package may reference only a separately approved immutable owner-bound recipe type. It cannot add owners, reorder operations, merge receipts, supply fragments, or construct an arbitrary multi-owner event vector. |
| Compiler boundary | The package compiler is deterministic and side-effect-free. It produces an immutable admission artifact and never reads mutable world state, writes the catalog, constructs events, issues receipts, or calls `append_batch()`. |
| Immutable admission | Candidate and active package records, descriptor revisions, recipe revisions, and admission artifacts are immutable. Disable/revoke/upgrade affects future admission only and preserves historical replay. |
| Canonicalization | Canonical JSON uses the existing Patch convention; declaration and complete-content digests are derived, never caller-selected. Digest calculation begins only after the approved logical schema and complete content are frozen. |
| Migration | Only lossless read-only adapters and explicitly versioned new revisions are allowed. Historical events keep their original package/descriptor/reader pins. Semantic authority changes are never in-place migrations. |
| Binding boundary | Package-to-capability binding is read-only and resolves only to already approved immutable descriptors/recipes. It cannot register or mutate a capability. |

## Required Invariants

An approved platform contract must preserve all of these invariants:

1. Package content can be extended without adding a runtime truth owner.
2. Every committed fact has one existing owner and one owner-defined operation
   descriptor.
3. Every eligibility decision is traceable to owner-derived evidence with
   event/projection kind, subject binding, privacy scope, revision pin, and
   proof digest.
4. Selection is deterministic and cardinality-one; ambiguity is zero-write.
5. A package cannot select owner, stream, event family, target derivation,
   privacy, revision, receipt, replay, idempotency, compensation, or fragment.
6. A recipe cannot become an arbitrary cross-domain settlement authority.
7. Rejected input produces no event, marker, receipt, outbox record, or partial
   fragment.
8. Historical replay never reruns changed package logic to reinterpret truth.
9. Disable, upgrade, and migration preserve historical event readability or
   fail closed with an auditable replay-readiness error.
10. The platform remains compatible with the single existing runtime/store/
    bus/clock/scheduler spine.

## Independent Approval Gates

These gates are independent and ordered:

1. **Logical platform vocabulary**: approve the records, references, revision
   relationships, descriptor model, predicate model, recipe model, and
   platform schema-version boundary as design semantics only.
2. **Canonicalization and digest**: approve canonical JSON, array ordering,
   duplicate handling, digest exclusion, and declaration-versus-content digest
   derivation. This does not freeze any package.
3. **Immutable admission/compiler boundary**: approve candidate validation,
   active-set lifecycle, compiler side-effect prohibition, artifact pinning,
   disable/revoke/upgrade behavior, and replay retention.
4. **Read-only package-to-capability binding**: separately approve exact
   descriptor/recipe resolution, restricted predicate families, deterministic
   selection, evidence proof requirements, and cardinality-one zero-write
   behavior.

Only after these platform gates may a future row-specific owner contract,
package content revision, or implementation plan be reviewed. The schema
decision remains a separate documentation gate: its exact field mapping and
migration errata must be accepted before any schema implementation review.
Those later steps are outside the current task.

## Explicitly Not Approved

- any manifest schema change;
- any package identity/revision/content digest freeze;
- any runtime compiler or registry writer;
- any catalog row or catalog mutation;
- any generic owner, resolver, router, coordinator, writer, treasury,
  payment, transfer, market, or settlement authority;
- any new owner operation family;
- any RED test, Harness profile, or append/write path;
- any INF row, including `oven -> kiln`.

## Final Design Approval Record

The following design-only artifacts are explicitly approved and complete:

```text
platform contract:                       approved
schema mapping/migration errata:         approved
schema-closure addendum:                 approved
design-only platform completion:         approved
```

The approved addendum includes the author-input versus normalized-output
`declaration_digest` boundary: an author claim is required but untrusted; the
adapter derives and compares the expected value after excluding only that
field; only the derived value is retained; and outer `content_digest` follows
all declaration normalization. Missing, malformed, mismatched, or conflicting
claims are zero-write.

The completed platform design does not approve schema implementation, package
content freeze/digest, row binding, catalog/compiler/verifier work, tests,
Harness, or INF runtime. Each is an independent future task requiring its own
approval.

## Approval Record Template

The approver should record one disposition for each gate:

```text
logical_platform_vocabulary:      approved
canonicalization_and_digest:     approved
immutable_admission_compiler:    approved
readonly_capability_binding:     approved
scope_constraints:               accepted
```

The four platform gates, scope constraints, mapping/migration errata, and
schema-closure addendum are explicitly approved. The platform is now
`design approved and complete`. Any future schema-v2 implementation plan,
schema change, package content freeze/digest, row binding, catalog/compiler/
verifier work, test/Harness work, or INF runtime requires separate approval.
