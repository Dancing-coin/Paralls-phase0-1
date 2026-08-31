# INF-1AH Decommission Package Admission Packet

Status: `historical package/admission prerequisite; lifecycle vertical implemented and verified on 2026-08-21`

## Fixed Admission Boundary

This packet governs only the future package declaration for the exact
Construction lifecycle operation defined in the INF-1AH contract. The package
may describe row-local content and request one typed binding; it cannot choose
the owner, stream, event family, event revision, privacy, receipt, replay
reader, compensation, or settlement fragment.

The frozen source package remains read-only evidence:

```text
package_revision  = package:industrial-facilities:v2
content_digest    = sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896
declaration_digest= sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8
```

It is not the decommission package, does not acquire new declarations, and
must never be regenerated or overwritten.

## Frozen Package Fields (Historical Admission Record)

The following table records the literal approval surface that produced the
frozen v3 bytes. No value was inferred from v2, a facility name, or a prior
descriptor:

| Field | Required rule | Current state |
| --- | --- | --- |
| package id and revision | a new immutable package revision, distinct from v2 | approved and frozen as v3 |
| patch/package version, author, trust policy | explicit schema-valid values | approved and frozen as v3 |
| declaration and binding refs | one exact row-local declaration and one exact binding | mechanically derived, validated, and frozen as v3 |
| policy ref and revision | one lifecycle-only policy | approved and frozen as v3 |
| capability/outcome refs | must exactly match the separately approved owner descriptor | frozen package claims; exact descriptor remains separately pending |
| typed eligibility request | one non-empty `construction:facility-mill-reinforced@1` mapping with facility/project subject binding | approved, validated, and frozen as v3 |
| definition/typed content and dependency arrays | explicit schema-valid content and explicit array decisions | approved and frozen as v3 |

The approved author input was validated and frozen in the
[v3 freeze record](2026-08-20-inf-1ah-industrial-facilities-v3-decommission-freeze-record.md).
The existing adapter derived and compared declaration digests from the
canonical declaration payload, normalized it, then derived and compared the
outer content digest. The packet was later admitted through the existing
read-only candidate/active binding path; it does not authorize lifecycle
runtime, manifest edits, or Construction business events.

## Binding Selection And Rejection

At the approved activation gate, the existing registry resolves only one exact
immutable descriptor for the one binding request. Zero,
multiple, stale, mismatched, unadmitted, or caller-selected bindings are
zero-write before any owner append. The active snapshot must retain new-package
content/declaration/descriptor/active-set pins alongside the frozen v2 source
pins.

This packet does not admit a generic lifecycle action, a registry writer, or a
new authority. Admission evidence is recorded in the exact descriptor/catalog
packet and its independent Harness; lifecycle runtime remains separate.

The field-by-field approving decision, including explicit empty-array choices,
is recorded in the [minimum business decision and admission closure
packet](2026-08-20-inf-1ah-minimum-business-decision-admission-closure-packet.md).
