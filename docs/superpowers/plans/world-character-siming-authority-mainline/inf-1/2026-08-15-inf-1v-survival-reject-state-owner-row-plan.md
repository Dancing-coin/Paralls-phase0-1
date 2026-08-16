# INF-1V Survival Reject State Owner Row Implementation Plan

**Goal:** Preserve the owner-matrix fence while `reject` remains contract-blocked.

1. Add a focused test proving an unregistered `reject` definition cannot reach
   the existing Survival append path.
2. Return the canonical unregistered-owner error before evaluating or building
   an obligation.
3. Keep the package blocked until a future owner/event/projection/receipt
   contract is formally approved.
