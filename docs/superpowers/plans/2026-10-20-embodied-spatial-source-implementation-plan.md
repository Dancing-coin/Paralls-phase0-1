# Embodied spatial source implementation lane

This is the Task2 dependency lane of the [October stages 1–3 plan](2026-10-20-october-stages-1-3-implementation-plan.md), which owns the execution ledger and acceptance matrix. Design: [controller-bound spatial source](../specs/2026-10-20-embodied-spatial-source-design.md).

1. RED for foreign/unbound scope, continuity, freshness, reconnect, SQLite recovery, duplicate and owner read CAS; implement minimal shared-store source. Completed in `cdb424d8`, exact staged 62 passed; evidence is indexed in the parent matrix.
2. RED for production settings/composition and strict authenticated sample ingress. Wire internally authored scopes and the existing shared world store; reject client scope registration and malformed/unbound samples without writes. Use focused backend tests and backend-contract.
3. Consume fresh source revisions at production L4/ESM admission and owner commit. Recover the cross-store session gap using the original owner receipt. Keep R07–R09 open until the parent plan's real Laya and recovery evidence exists.
4. Defer all Godot modification/start/operation/scene verification to the parent plan's final A/B/C acceptance. No sample test substitutes for those gates.

Architecture, sequence and data-flow diagrams are maintained in the linked design and parent plan. This lane adds no separate architecture or authority.
