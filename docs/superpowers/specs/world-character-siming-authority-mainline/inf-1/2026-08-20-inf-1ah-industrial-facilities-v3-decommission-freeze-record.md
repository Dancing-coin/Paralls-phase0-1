# INF-1AH Industrial Facilities V3 Decommission Freeze Record

Status: `historical package/admission record; lifecycle vertical implemented and verified on 2026-08-21`

Date: `2026-08-20`

## Frozen Bytes And Derived Pins

The frozen UTF-8 manifest payload is stored in
[package-industrial-facilities-v3-decommission.manifest.json](package-industrial-facilities-v3-decommission.manifest.json).
It is the sole immutable content for `package:industrial-facilities:v3` and
must never be edited, regenerated, or overwritten in place. The derived
digests below are over the adapter's canonical decoded JSON record (sorted
keys and compact separators), rather than a claim about physical file-layout
bytes.

```text
manifest pair      = (2, "1.0")
patch version      = 3.0.0
package version    = 3.0.0
declaration ref    = declaration:industrial-facilities-mill-reinforced-decommission@1
declaration digest = sha256:ad800530f5e9a85baad29c5825a0e7edfc7e6cfa664a20208f5d2566819a7c3c
content digest     = sha256:bde53b49ee207d90c2d2bfd7e7ff95ef03638a41719883a21c2b83a3e15930ca
```

The author supplied both digest claims. The existing adapter excluded only
`declaration_digest` from the canonical declaration payload, derived the value
above, compared it exactly, and normalized the declaration with the derived
pin. It then excluded only outer `content_digest` from the complete normalized
v2 record, derived the outer value above, and compared it exactly. Missing,
malformed, mismatched, or conflicting claims remain fail-closed and
non-mutating.

Non-mutating candidate validation through the existing
`GameplayPatchRegistry.validate_install_many()` also passed for the trusted
`author:repo` record. This validation did not install a candidate, activate a
package, resolve a descriptor, write a catalog row, or append a business event.

## Narrow Content Boundary

The frozen package declares only two facility definitions, the one lifecycle
declaration, and one typed binding request:

```text
definition:industrial-facilities-mill@1
definition:industrial-facilities-mill-reinforced@1
policy:industrial-facilities:mill-reinforced-decommission@1
binding:industrial-facilities-mill-reinforced-decommission@1
capability:construction-facility-mill-decommission@1
outcome:construction-facility-mill-decommission@1
construction:facility-mill-reinforced@1
```

Both definitions use `schema:industrial-facilities-facility@1` and carry only
their respective `facility_kind`. The record freezes explicit empty dependency,
conflict, event-schema, replay-reader, verification, rule, legacy capability,
economic-outcome, and granted-effect arrays. It does not select or declare an
owner, stream, event family, privacy scope, receipt, replay authority,
compensation, payment, material, inventory, production, weather, maintenance,
social, or any other cross-domain fact.

Frozen `package:industrial-facilities:v2` remains source evidence only for the
predecessor `mill -> mill_reinforced` event. It was not modified, recalculated,
overwritten, or reused as v3 content.

## Remaining Admission Gate

The exact `ConstructionProductionAuthority` descriptor and immutable
`GovernedAuthorityContractCatalog` row are admitted and verified through the
existing read-only Registry binding path. Binding pin retention, snapshot
replay, and exact-one zero-write evidence are recorded in the admission
packet/Harness. Lifecycle projection, verifier/reducer, business-event tests,
Harness, and append path remain separately unapproved; all INF-1AH runtime
requests remain zero-write.

This freeze record did not itself implement INF-1AH. The separate lifecycle
runtime is now implemented and verified; August INF A-D remain incomplete.
