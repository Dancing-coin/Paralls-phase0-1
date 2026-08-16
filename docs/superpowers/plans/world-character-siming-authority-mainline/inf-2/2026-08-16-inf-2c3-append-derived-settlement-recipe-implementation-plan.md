# INF-2C3 Append-Derived Settlement Recipe Implementation Plan

Status: `implemented and focused-verified`

1. Add RED tests for single-owner and multi-owner fragment composition,
   append-derived committed/rejected receipts, and overlapping-stream fence.
2. Add the pure `AppendDerivedSettlementRecipe` wrapper around the existing
   fragment adapter and receipt factory.
3. Route obligation planner batch materialization through the recipe without
   changing owner commit authority.
4. Run focused owner-only obligation, receipt and reusable recipe suites.
5. Record independent Harness checks and update INF status indexes.

Completion condition: the reusable recipe proves one append-derived receipt
shape for both single-owner and existing multi-owner fragments, preserves
revision/privacy/idempotency rejection, and introduces no writer or second
truth store.
