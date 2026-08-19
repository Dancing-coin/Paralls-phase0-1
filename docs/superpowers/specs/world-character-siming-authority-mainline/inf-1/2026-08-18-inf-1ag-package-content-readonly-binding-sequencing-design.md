# INF-1AG Package-Content And Read-Only-Binding Sequencing Design

Status: `P1 sequencing amendment implemented and verified; package freeze complete, descriptor/binding admission remains separately gated`

Date: `2026-08-18`

## Purpose

This document closes the ordering conflict between the implemented INF-P v2
manifest boundary and the approved INF-1AG `oven -> kiln` owner-admission
contract. Its original design stage did not freeze a package, derive a real
digest, add a descriptor or catalog row, modify runtime code, add tests or
Harness, or resume an INF business vertical. The separately approved package
freeze is recorded in the 2026-08-19 freeze record; this design itself remains
unchanged.

The fixed row is:

```text
package_id          = package:industrial-facilities
package_revision    = package:industrial-facilities:v1
outcome_family      = construction_facility_package_declared_transform@1
capability_ref      = capability:construction-facility-package-declared-transform@1
source_kind         = oven
target_kind         = kiln
policy_revision     = policy:industrial-facilities:oven-to-kiln@1
eligibility_ref     = construction:facility-acquired@1
owner/evidence      = ConstructionProductionAuthority /
                      gameplay.construction_production.facility_acquired@1
privacy             = project
terminal            = v1 terminal/no compensation
```

## Superseded INF-P Boundary

Before P1, INF-P parsed and normalized every v2 manifest before the existing
`GameplayPatchRegistry.validate_install_many()` candidate path. Its
`PlatformExtension` validation rejects every non-empty
`capability_binding_requests` collection with
`platform_capability_binding_unknown`. Therefore a complete package carrying
the INF-1AG binding cannot currently become a candidate. A package with an
empty request collection can become a candidate, but it is not the same
immutable package: adding the request later changes the normalized record and
the outer `content_digest`.

This prior fail-closed behavior was correct, but P1 replaced only its
candidate-time rejection with the bounded gate specified below. It is still
not evidence that a package, descriptor, binding, or Construction write is
already admitted.

## Decision: Candidate Before Descriptor

A real immutable package **may** precede an owner descriptor as a retained
candidate only after the candidate/binding sequencing amendment below is
approved and implemented. For INF-1AG, the real candidate must already contain
the exact declaration and exact non-empty binding request. Candidate admission
validates only immutable package-local facts:

- v2/`1.0` schema pair and author-canonical array order;
- package identity/revision equality with the outer manifest;
- exact author claim and adapter-derived `declaration_digest`;
- outer normalized `content_digest`;
- declaration/binding internal references, namespaces, duplicates, and
  authority-shaped-payload prohibition; and
- existing package dependency/conflict checks that do not select an owner.

Candidate admission does not resolve a descriptor, a predicate, owner evidence,
stream, event family, privacy, receipt, or settlement fragment. It cannot
activate the candidate or authorize a Construction command.

## Required Sequencing Amendment

The minimal design change is a narrow split of the existing fail-closed check:

| Gate | Existing boundary reused | Required disposition |
| --- | --- | --- |
| candidate-time | `GameplayPatchManifest` plus `GameplayPatchRegistry.install_many()` | accept a non-empty binding request only after structural/package-local validation; do not resolve it |
| descriptor admission | immutable `GovernedAuthorityContractCatalog` and a separately approved row-specific owner operation descriptor | introduce no mutable catalog API; verify the exact capability/outcome family and allowed `construction:facility-acquired@1` predicate/evidence family |
| activation-time | existing `GameplayPatchRegistry.compose_active_set()` / `activate()` | resolve every candidate binding through the read-only descriptor relation; require exactly one result or reject the whole proposed active set before mutation |
| row-binding-time | immutable activation binding artifact consumed by the existing Construction row only | pin package/declaration/descriptor/active-set values; resolve owner evidence only when the later approved row executes |

The registry remains the sole candidate/active-set runtime. The catalog remains
immutable/read-only. The activation-time check is a deterministic validation
inside the existing active-set composition boundary, not a router,
coordinator, generic writer, or second registry. A binding request never
constructs an event vector or receipt.

## Pin Order

1. Author submits the complete v2 package, including the exact INF-1AG
   declaration and binding request plus the untrusted declaration-digest claim.
2. The adapter verifies the claim and retains only the derived
   `declaration_digest`; it then derives the outer `content_digest` from the
   normalized complete package, excluding only outer `content_digest`.
3. The existing registry retains that complete immutable manifest as a
   candidate and snapshots it. The candidate is inactive and has no descriptor
   selection yet.
4. A separate approved INF-1AG descriptor/catalog admission names its own
   immutable descriptor revision. It may reference the already frozen package
   id/revision/content digest and declaration digest, but the package never
   selects that descriptor revision.
5. During proposed active-set composition, the existing registry derives the
   prospective `active_patch_set_revision`, resolves the exact one descriptor
   from the read-only catalog, and emits an immutable binding artifact carrying
   `(package_revision, content_digest, declaration_digest, descriptor_ref,
   descriptor_revision, prospective_active_patch_set_revision)`.
6. The activation snapshot and lifecycle evidence retain that binding artifact
   beside the existing active-set pins. Full and checkpoint-tail replay reload
   the candidate snapshot and require the exact retained binding pins; missing,
   multiple, or changed pins fail closed.
7. Only a later separately approved INF-1AG vertical may use that artifact to
   request owner-derived acquisition proof and then call the existing
   `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`
   path.

`policy_revision`, source/current Construction revisions, facility/project
binding, project privacy, idempotency, append receipt, and terminal/no-
compensation semantics remain fixed by the already approved Construction row
contract. They are not package- or caller-selected pins.

## No Temporary Empty Binding

An empty-binding industrial package cannot later be "filled in" under the same
`package:industrial-facilities:v1` revision. The binding collection contributes
to the canonical v2 record and therefore to `content_digest`; changing it
creates a different immutable revision. Such a package is not a legitimate
INF-1AG candidate and must not be activated as a placeholder.

If preliminary content review is needed, it remains an uninstalled authoring
draft. Once candidate installation is authorized, the first candidate must be
the complete binding-bearing manifest, or a new package revision must be used.

## P1 Implementation Evidence And Remaining Gate

P1 implemented the **candidate-time structural / activation-time read-only
binding sequencing amendment** on the existing manifest, registry, immutable
catalog boundary, snapshot, and lifecycle replay boundary. It proves:

1. non-empty binding requests are syntactically and digest validated at
   candidate time without descriptor lookup;
2. a proposed active set rejects unless every binding resolves to exactly one
   already admitted immutable descriptor;
3. existing active-set snapshot/lifecycle retention gains the immutable binding
   artifact and its package/declaration/descriptor/active-set pins; and
4. no candidate with unresolved binding is activatable or executable.

The focused P1 suite passed `14` tests; the independent
`inf-p-federated-gameplay-extension-platform` Harness is green; and the
existing patch/lifecycle/catalog regression band passed `45` tests. P1 adds no
business descriptor rows. This is not a license to create a generic descriptor
resolver. The later INF-1AG descriptor/catalog row, activation, RED tests,
Harness, verifier, reducer, and Construction write path remain independent
approvals.

## Current Disposition

```text
INF-P P1 sequencing amendment:       implemented and verified; not reopened
INF-1AG row contract:                approved design only; not implemented
real industrial package freeze:      complete; exact canonical digests verified
descriptor/catalog admission:       not approved
binding activation/runtime:         platform-only verified; row binding not approved
August INF A-D:                     not complete
```
