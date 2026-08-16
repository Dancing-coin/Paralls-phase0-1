# INF-1N Construction Maintenance State Obligation Plan

Status: `implemented and verified; fixed Construction lifecycle row only`

1. [x] Add focused failing tests for the fixed Construction maintenance state/open
   and due/expired-settled lifecycle, including the paired expiry invariant,
   direct non-owner rejection, and all other rejection, privacy,
   idempotency and replay cases named in the design.
2. [x] Extend only `ConstructionProductionAuthority` and its existing projector
   with the fixed policy/event family. Keep the existing facility stream and
   construct owner-authorized fragments for the caller-driven coordinator.
3. [x] Register this one policy only through an explicit
   `ObligationLifecycleRegistration` owned by the Construction contract. Do
   not add dynamic registration, a scheduler or another coordinator writer.
4. [x] Add an independent Harness profile with a distinct selector for every
   listed capability. Rerun the predecessor semantic maintenance and
   obligation lifecycle profiles.
5. [x] Synchronize formal design/plan, the INF-1 tree, root dependency records,
   August analysis and `docs/harness.md`; run focused tests, full replay,
   checkpoint-tail replay, `git diff --check`, and `python -m pytest -q`.
