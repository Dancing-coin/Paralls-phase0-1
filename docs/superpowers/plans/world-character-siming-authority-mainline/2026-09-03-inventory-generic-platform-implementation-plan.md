# General Inventory Platform Implementation Plan

Status: `implemented-and-verified`

Rollout gates:

1. strict v3/2.0 content and exact admission;
2. item/instance/lot/container/custody/reservation core;
3. condition/expiry/transport/quarantine;
4. owner-bound Production, Commerce, Ownership, Survival, Equipment, Ecology,
   Organization and Government recipes;
5. read-only Population/Godot projection.

Each gate requires RED-to-green tests, registry-backed writes, privacy/revision/
idempotency/receipt checks, tamper and zero-write rejection, full/tail replay,
an independent Harness and rollback evidence before the next gate.

The final audit must preserve old narrow-row readers and August INF A-D
`not complete` status.

Completion evidence: [Inventory Generic Platform Completion Audit](../../specs/world-character-siming-authority-mainline/2026-09-03-inventory-generic-platform-completion-audit.md),
Inventory Harness `21 passed`, repository pytest `4494 passed`, compileall and
diff check green.
