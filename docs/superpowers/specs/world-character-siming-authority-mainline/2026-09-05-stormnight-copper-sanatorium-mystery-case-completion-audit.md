# Stormnight Copper Sanatorium Mystery Case Completion Audit

Status: `complete reference game; reusable case-template baseline`

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
- a deterministic scenario runner now composes case open, three ordered action windows,
  Social/Quest handoff, Inventory clue custody, accusation and all four
  declared outcome branches on one event store with replay hash comparison;
- the dedicated Stormnight Harness now executes the expanded integrated
  scenario and cross-owner event-ledger checks alongside the Godot probe;
- the runner now compares repeatable Quest, Social and Inventory owner
  projections in addition to the case projection and ledger hash;
- restored-store replay now reproduces the Quest, Social and Inventory owner
  projections, not just the raw case event ledger;
- the scenario runner now derives outcome prerequisites from committed case
  facts: correct culprit accusation for `case_solved`, wrong-target accusation
  for `false_accusation`, no contact for `culprit_escaped`, and contact for
  `investigator_captured`;
- the runner now gates execution on the admitted Stormnight action graph and
  the global exact descriptor/catalog binding, instead of accepting a local
  graph or caller-selected authority coordinates;
- four-room procedural Godot presentation, read-only panels and rejection
  rollback through a dedicated Godot 4.6.3 headless Harness.

## Final evidence

- focused Stormnight suite: `47 passed`;
- full repository pytest: `5139 passed, 1 warning` at the last green checkpoint;
- Stormnight Harness: `exit 0`, scenario outcome `case_solved`, committed projection loaded by Godot;
- Godot 4.6.3 headless and desktop smoke: passed;
- four Stormnight low-poly actor replicas load from the reusable primitive-only
  character scene; actor colors/markers and committed terminal-state mapping
  are verified without any Throne Hall or knight-scene reference;
- a separately runnable local realtime vertical now binds PlayerShell input to
  finite WebSocket intents, shared-store owner validation and committed Godot
  HUD/actor updates; backend startup plus actual WebSocket round-trip and
  Godot scene load are covered by `stormnight-realtime-playable` Harness.
- `python -m compileall -q backend`: passed;
- `git diff --check`: passed;
- every durable case write uses the existing append spine;
- no frozen package or August INF A-D row was modified.

## Completion interpretation and follow-on scope

The fixed owner handoff is exercised for Social statement, Quest evidence and
Inventory clue custody. The deterministic reference runner executes all three
case phases, three ordered source-fenced action windows (including a
contact/control branch), all four outcome branches with outcome-specific
prerequisites, and a cross-owner event-ledger hash. It dispatches to existing
owner adapters rather than inventing a case-wide writer. The Godot probe loads
the committed backend projection and verifies rejection rollback, so the
reference-game acceptance path is closed.

The second content-only variant runs through the same package, case, action and
outcome adapters and is covered by the genericity suite. Higher-fidelity live
LLM dialogue, richer pursuit/capture branches, interactive Godot controls,
durable owner-specific checkpoint APIs and Creator Skill/Siming Director are
follow-on enhancements, not prerequisites for this reference case. August INF
A-D remains `not complete`.
