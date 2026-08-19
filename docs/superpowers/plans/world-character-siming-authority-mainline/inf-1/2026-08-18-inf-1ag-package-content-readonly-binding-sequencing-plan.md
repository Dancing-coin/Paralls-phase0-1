# INF-1AG Package-Content And Read-Only-Binding Sequencing Plan

Status: `P1 implemented and verified; real package/row work remains separately gated`

Date: `2026-08-18`

## Goal

Resolve the documented candidate/binding ordering conflict before any real
`package:industrial-facilities:v1` freeze. This plan follows the approved
INF-1AG row contract and implemented INF-P boundary; it does not reopen either.

## Ordered Gates

1. Approve the candidate-time structural / activation-time read-only binding
   sequencing amendment in the matching design. `Complete.`
2. Write a separately approved file-level platform change plan for the existing
   manifest, registry active-set composition, snapshot/lifecycle retention, and
   focused platform evidence. It must not add a registry, owner, router,
   coordinator, writer, or settlement surface. `Complete.`
3. Implement and verify that platform amendment before reviewing any real
   package content. `Complete:` the P1 focused suite is `16 passed`, the
   independent `inf-p-federated-gameplay-extension-platform` Harness is green,
   and the patch/lifecycle/catalog regression band is `45 passed`.
4. Freeze the complete industrial package once, with its non-empty INF-1AG
   binding request and author declaration-digest claim already present; derive
   and confirm its digest only at that later gate. `Complete:` both equal
   version values and the verified canonical bytes are recorded in the
   [freeze record](../../../specs/world-character-siming-authority-mainline/inf-1/2026-08-19-inf-1ag-industrial-facilities-v1-freeze-record.md).
5. Approve the exact immutable Construction descriptor/catalog row after the
   frozen candidate is available, then activate through the existing active-set
   boundary with one retained binding artifact.
6. Obtain distinct approval for the owner-bound verifier/reducer, RED tests,
   Harness, and narrow Construction append vertical.

## Stop Conditions

P1 now proves that complete non-empty requests may become immutable
candidates, while activation rejects unknown, multiple, or mismatched
descriptors before mutation and retains exact binding pins in snapshot and
lifecycle replay. Stop before step 4 until the user separately authorizes a
real package freeze. Stop before step 5 without a separately approved
descriptor/catalog row. An empty-binding placeholder, descriptor chosen by
package or caller, missing replay pin, or second registry/runtime is zero-write
and not a valid alternative.
