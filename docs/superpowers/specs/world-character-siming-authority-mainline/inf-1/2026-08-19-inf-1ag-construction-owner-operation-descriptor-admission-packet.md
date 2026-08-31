# INF-1AG Construction Owner-Operation Descriptor Admission Packet

Status: `approved and implemented static immutable admission; exact Construction narrow vertical implemented and verified`

Date: `2026-08-19`

## Purpose And Non-Admission

This packet was the exact proposed immutable metadata admission for the already
frozen INF-1AG `oven -> kiln` package. Its fixed static descriptor and governed
contract row are now approved and implemented in the existing read-only
catalog. This packet does not add a Construction command, verifier, reducer,
append path, event, or generic runtime surface.

The package remains immutable at [its frozen canonical bytes](package-industrial-facilities-v1.manifest.json):

```text
package_id         = package:industrial-facilities
package_revision   = package:industrial-facilities:v1
content_digest     = sha256:41e1b40bcd1fd13e1692f2f51aed7dea6dceee0b1605bf215fe6c673fcd11f88
declaration_ref    = declaration:industrial-facilities-oven-to-kiln@1
declaration_digest = sha256:04869873a57a24b834cc123a14440444717bdd482910eb9d8ae1d50cc3bc2ed8
```

## Proposed Immutable Metadata

### Descriptor

```text
descriptor_id       = descriptor:construction-facility-package-declared-transform@1
descriptor_revision = descriptor:construction-facility-package-declared-transform@1
capability_ref      = capability:construction-facility-package-declared-transform@1
outcome_family_ref  = outcome:construction-facility-package-declared-transform@1
allowed_predicates  = [predicate:construction-facility-acquired@1]
allowed_effects     = [effect:construction-facility-package-declared-transform@1]
```

The descriptor is not selected by package, agent, caller, or intent. It only
allows the one typed binding already contained in the frozen package. No other
predicate family, eligibility family, effect type, or declaration is admitted.

### Governed Construction Contract Row

```text
contract_ref        = inf:construction-facility-package-declared-transform@1
contract_kind       = settlement
owner_ref           = actor_gameplay.construction_production_domain
owner               = ConstructionProductionAuthority
stream_pattern      = gameplay:construction_production:{facility_ref}
event_type          = gameplay.construction_production.facility_transformed
projection_scope    = project
receipt_reader_ref  = GameplayEventStore.append_batch
replay_reader_ref   = ConstructionProductionAuthority.projector
```

`owner_ref` is the existing catalog identity for
`ConstructionProductionAuthority`; it does not create a second owner. The
single event is the fixed write family
`gameplay.construction_production.facility_transformed@1` on the fixed facility
stream. The package cannot select its stream, event, owner, privacy, receipt,
reader, or fragment.

## Source, Revision, Privacy, And Replay Contract

The sole source is existing committed
`gameplay.construction_production.facility_acquired@1` evidence and the
existing `ConstructionProductionProjection.facilities` state. The allowed
eligibility family is exactly `construction:facility-acquired@1`; the allowed
package predicate family is exactly
`predicate:construction-facility-acquired@1` with
`slot:facility-project@1` binding both `facility_ref` and `project_ref`.

The verifier later required by this packet must derive and pin all of the
following before it can produce an owner operation:

```text
acquisition event stream revision = exact committed acquisition-event revision
current facility revision         = exact projection facility revision
facility stream head              = exact target facility-stream head
facility_ref                      = committed facility_acquired.facility_ref
project_ref                       = committed facility_acquired.plot_ref
source kind                       = oven
project privacy                   = matching project-scoped evidence
package/declaration pins          = all five frozen values above
```

The receipt is only the receipt returned by
`GameplayEventStore.append_batch()`. Full replay uses the existing
`ConstructionProductionAuthority.projector` from the event origin. Checkpoint-
tail replay invokes that same reader from an authority-created checkpoint and
revalidates the package, declaration, source, privacy, facility/project, and
revision pins before applying the tail. There is no combined receipt or second
reader/runtime.

## Fixed Terminal Operation

The operation has the fixed authority-derived idempotency key:

```text
construction:facility-transform:
  package_revision:content_digest:facility_ref:
  acquisition_event_id:prior_facility_revision
```

V1 changes only the existing Construction facility kind from `oven` to `kiln`.
It is terminal: no reversal, downgrade, retry-as-new-transform, reopen,
compensation, fanout, payment, material, production-output, permit, or
technology semantics exist. `bakery -> bakery_reinforced` remains the separate
closed INF-1AF row and is not admitted here.

## Activation Resolution And Zero-Write Rules

During existing `GameplayPatchRegistry.compose_active_set()/activate()`, the
frozen binding request resolves against the immutable read-only catalog only:

1. Select descriptors whose `capability_ref` exactly equals the fixed package
   capability.
2. Retain only descriptors whose `outcome_family_ref` exactly equals the
   normalized declaration's outcome family.
3. Require exactly one result and exact equality of both the allowed predicate
   vector and allowed effect vector.
4. Persist only the existing activation-derived binding pins: package revision,
   content digest, declaration digest, descriptor id/revision, and active-set
   revision.

Zero writes are required before candidate/active mutation or Construction
append for an unknown package or declaration, an unadmitted descriptor, zero
or multiple descriptor matches, package/declaration digest mismatch, stale or
private source evidence, facility/project binding conflict, duplicate or
changed duplicate, source/facility/stream revision conflict, a non-`oven`
source, an already transformed facility, or a privacy mismatch. These are
rejections, not fallback selection or normalization.

## Explicit Prohibitions

This packet does not admit a generic Construction transform, caller-selected
owner/stream/event/revision/privacy/receipt/fragment, compensation, fanout,
payment, material semantics, router, registry, writer, coordinator, settlement
authority, or second runtime/store/bus/clock/scheduler. `GovernedAuthorityContractCatalog`
remains immutable/read-only and `SettlementPlan` remains composition-only over
fixed owner-authorized fragments.

## Verified Admission And Completed Vertical

The exact descriptor and contract row above are present in the existing
read-only catalog. The focused catalog/binding suite proves the frozen package
resolves exactly one descriptor and retains the package/content/declaration/
descriptor/active-set pins in a temporary registry; no Construction append is
performed by that admission profile. The suite is `16 passed`.

The owner-bound Construction verifier/reducer and narrow append vertical were
subsequently approved and implemented with focused RED-to-green coverage and
an independent Harness. INF-1AG is therefore implemented and verified for the
exact frozen `oven -> kiln` row. August INF A-D remains `not complete`, and
this packet does not broaden admission beyond the fixed descriptor above.
