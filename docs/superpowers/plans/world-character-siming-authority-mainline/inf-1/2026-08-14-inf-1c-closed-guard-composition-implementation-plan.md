# INF-1C Closed Guard Composition Implementation Plan

Status: `implemented and verified 2026-08-14; proposal-only semantic evaluator increment`

1. [x] Record finite `all(...)` / `any(...)` grammar over existing atomic guard
   terms; reject nesting and arbitrary execution syntax.
2. [x] Add RED focused tests for true/false `all`, true `any`, and invalid
   composition rejection before changing evaluator code.
3. [x] Implement deterministic finite parsing and evaluation in
   `SemanticRegistry` without an event-store dependency or append path.
4. [x] Add `infra-semantic-closed-guard-composition`, one independent test per
   claimed capability, and store the evidence report.
5. [x] Synchronize the August guide, formal INF-1 index, and root dependency
   records without upgrading owner lifecycle closure.

## Explicit exclusions

No generic effect/state lifecycle, new owner mapping, semantic direct write,
unbounded rule language, selector nesting, scheduler, SOC-1, GAME-1, P6, or P7.
