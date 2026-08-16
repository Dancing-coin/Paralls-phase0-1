# INF-2M Closed Lifecycle Registration Admission Plan

Status: `completed as an input-admission fence; owner-only write-spine closure remains planned`

Date: `2026-08-15`

1. [x] Add RED tests for a finite owner-contract reader and zero-write rejection of
   policy-less, unknown, forged, and widened caller registrations.
2. [x] Add immutable existing-owner lifecycle contract lookup in
   `world_runtime/obligations.py`; registration input may only select a
   capability subset of its matching closed contract.
3. [x] Make the coordinator require a recognized policy source before assembling a
   batch. This retains a coordinator append capability and therefore is not
   evidence of the owner-only write spine; INF-2Q must move commit ownership
   back to each existing authority while preserving receipts and replay.
4. [x] Reject any registered fragment event outside its closed owner-local event
   family before append, including terminal-plus-smuggled-event payloads.
5. [x] Reject a registered fragment whose event visibility differs from the
   owner policy's fixed visibility scope before append.
6. [x] Preserve the canonical committed-open admission condition when a caller
   supplies a less-capable registration view; Construction due completion must
   observe its committed `run_started` source before append.
7. [x] Update obsolete generic-farm tests to assert rejection rather than a
   caller-generated world write.
8. [x] Add a package Harness and synchronize INF-2, root, August, and evidence
   documents before broad verification.

## Stop Conditions

Do not add a new policy, owner, stream, event family, or cross-domain outcome.
If an existing registration cannot be mapped exactly, reject it before append.
