# INF-1AH New Decommission Package Freeze And Future Admission Checklist

Status: `historical package/admission checklist; lifecycle vertical implemented and verified on 2026-08-21`

## Decision Classification

| Class | Fields |
| --- | --- |
| Already uniquely fixed | schema pair `2/1.0`; Construction owner; project privacy; facility stream; `facility_decommissioned@1`; `active -> decommissioned`; retained `facility_kind=mill_reinforced`; one-event vector; authority idempotency; append receipt; full/checkpoint-tail replay; terminal/no compensation; started-run pre-append zero-write |
| Mechanically derived after approval | v3 revision pins on all local records; declaration/binding refs; capability and outcome refs; requirement/predicate refs; canonical declaration/content digests; active-set pin tuple |
| Formerly missing business decision (now approved and frozen) | package/version/author/trust literals; exact two definition records; policy ref; dependency arrays |

## Freeze Checklist

- [x] Approve every `missing business decision` literal in the minimum decision packet.
- [x] Confirm new immutable revision is distinct from frozen
  `package:industrial-facilities:v2`.
- [x] Preserve frozen v2 as source evidence only. This is an already-fixed
  contract safeguard, not a new package-content decision.
- [x] Confirm source/target typed definitions contain only facility kind facts;
  no lifecycle, payment, material, production, weather, or social truth.
- [x] Confirm the one mechanically derived declaration/binding/capability/
  outcome identity and the separately approved lifecycle-only policy produce
  exactly one row; no generic transform/decommission vocabulary.
- [x] Confirm explicit empty dependency/conflict/rule/event-schema arrays.
- [x] Author complete placeholder-free canonical content only after approval.
- [x] Submit untrusted digest claims for adapter derivation and comparison;
  do not precompute or hand-edit a digest in this phase.
- [x] Freeze canonical package bytes and record pins in a new freeze record.
- [x] Approve and install the exact descriptor/catalog row, then verify
  exact-one read-only binding and retain package/declaration/content/
  descriptor/active-set pins.
- [x] Runtime, tests, Harness, and append implementation received separate
  later approvals and are verified for the exact INF-1AH row only.

## Future Admission Packet Order

`frozen v3 package -> exact descriptor/catalog admission -> exact-one read-only
binding resolution -> separate lifecycle runtime approval`.

Unknown, multiple, unadmitted, digest-mismatched, stale, private, binding- or
revision-conflicting inputs remain zero-write at every later gate.
