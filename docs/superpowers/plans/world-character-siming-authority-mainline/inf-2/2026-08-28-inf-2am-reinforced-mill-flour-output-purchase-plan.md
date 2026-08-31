# INF-2AM Reinforced Mill Flour Output Purchase Plan

Status: `implemented and verified; narrow vertical only`

1. After INF-1AM passes, create and adapter-validate the immutable v7 manifest
   and exact catalog descriptor/binding; preserve v1-v6 bytes.
2. Add focused RED tests for owner-derived custody, exact package activation,
   account/price/party fences, and all zero-write cases.
3. Add the fixed Inventory receipt verifier and replay partition. Do not alter
   generic `record_output_receipt()` semantics.
4. Reuse the existing package-negotiated Economy vector only after the one
   Inventory receipt is committed; add the exact v7 source/party verifier.
5. Add independent Harness and prove both owner receipts, idempotency,
   privacy, full/tail replay and no-compensation lifecycle.

Verification repair completed 2026-08-28: the existing Inventory fragment now
rejects a stale provider custody stream before append, and the existing
Economy v7 replay reader validates the fixed settlement/provenance payload.
This closes evidence gaps only; it does not add a second Economy outcome or
generalize payment/transfer/settlement.
