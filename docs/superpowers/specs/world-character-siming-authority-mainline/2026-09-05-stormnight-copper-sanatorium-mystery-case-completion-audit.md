# Stormnight Copper Sanatorium Mystery Case Completion Audit

Status: `implementation in progress; foundation slices verified`

## Verified slices

- immutable original case content with four actors, ten clues, three phases
  and four declared terminal outcome kinds;
- v3/platform 2.0 package wrapper, canonical content/declaration digest checks,
  untrusted claim rejection and exact-one local binding;
- project-scoped case open, phase progression and terminal outcome append path;
- checkpoint-tail replay equality, package/checkpoint tamper rejection;
- filtered public/private case context and proposal-only Character Agent turns;
- evidence, statement, accusation and action-loop boundaries reject unadmitted
  or private input before a case cross-owner write;
- fixed handoff adapters now delegate statement/knowledge, Quest evidence and
  Inventory clue custody to their existing owner services, with owner streams
  and append receipts retained separately;
- a case-specific finite action graph and exact P5 registry surface are now
  admitted through the existing primitive/action-window/conflict path;
- a deterministic scenario runner now composes case open, action window,
  Social/Quest handoff, Inventory clue custody, accusation and all four
  declared outcome branches on one event store with replay hash comparison;
- the dedicated Stormnight Harness now executes the expanded integrated
  scenario and cross-owner event-ledger checks alongside the Godot probe;
- four-room procedural Godot presentation, read-only panels and rejection
  rollback through a dedicated Godot 4.6.3 headless Harness.

## Evidence at this checkpoint

- focused Stormnight suite: `24 passed` before the final schema-bundle add;
- Godot `stormnight-copper-sanatorium` Harness: passed;
- every durable case write uses the existing append spine;
- no frozen package or August INF A-D row was modified.

## Remaining work before reference-game completion

The fixed owner handoff is now exercised for Social statement, Quest evidence
and Inventory clue custody, and can dispatch to supplied Social/Quest owner
adapters rather than inventing a case-wide writer. The Stormnight graph is
admitted over existing action primitives. Full production-grade Quest request construction,
source-fenced ActionWindow pursuit beyond the reference window, live Character
Agent turns, desktop interactive smoke and a complete cross-owner replay with
persisted owner projection readers are still required. The four outcome
branches are deterministically exercised by the reference runner, but are not
yet a player-facing end-to-end Godot case.

The second content-only variant currently proves the package/content adapter
shape and case-open compatibility, not full playable-case genericity. The
isolated fallback handoff used by scenario tests is not sufficient production
evidence until real owner registries are supplied. Creator
Skill and Siming Director remain separate future work. August INF A-D remains
`not complete`.
