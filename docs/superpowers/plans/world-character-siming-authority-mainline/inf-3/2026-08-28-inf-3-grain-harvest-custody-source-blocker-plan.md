# INF-3 Grain Harvest Custody Source Blocker Plan

**Goal:** Historical plan for admitting one exact crop-to-grain source row before any downstream custody work.

**Current Gate:** Resolved on 2026-08-28 for the Ecology-owned upstream source only. The implemented row uses a dedicated `grain_crop.admitted` fact and one `grain_harvested` outcome with fixed wheat literals. Inventory custody remains separate.

1. Approve exact crop/grain definitions, maturity predicate, quantity policy,
   terminal/replant semantics, receiver/holder, and container derivation.
2. Write a row-specific Owner-Admission Contract with existing
   EcologyHazardAuthority and InventoryAuthorityService event/stream/privacy/
   revision/receipt/replay boundaries.
3. Write RED tests before any Ecology harvest behavior.
4. Verify append receipt, full/checkpoint-tail replay, privacy, idempotency,
   and no generic material conversion.
5. Keep this file as historical planning evidence; revisit downstream INF-2AM
   only with a separate Inventory/Economy row.
