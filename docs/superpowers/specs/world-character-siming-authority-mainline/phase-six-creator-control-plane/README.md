# Phase Six Creator Control Plane Specification Tree

Status: `design-only; implementation not authorized`

Date: `2026-08-10`

## Purpose

P6 formalizes `docs/8月分析/第六阶段推进/`: creators can configure and
publish governed gameplay packages without receiving closed-core internals or
production truth writers. It is a control plane, not gameplay authority.

## Operating Forms And Permissions

| Form / role | Permitted capability | Prohibited capability |
| --- | --- | --- |
| local preview | edit authorized draft, validate, simulate | write remote production facts |
| remote formal run | submit signed revision, activate approved profile | direct database/event-store write |
| reader | authorized schema, public projection, report | draft, publish, closed internals |
| editor | authorized draft, preview, lint, review submission | activation signature, player fact mutation |
| admin | membership, classification, approval, staged activation/rollback | secret/core algorithm/raw writer access |

One authorization-decision contract governs UI, CLI and MCP. Client hiding alone
does not enforce permissions. The closed core retains authority, keys, raw event
ingress, private memory and internal policy implementation.

Approved package activation remains a proposal into the existing
`GameplayCommandEnvelope` / `SettlementPlan` / `GameplayEventStore.append_batch()`
path. The control plane never becomes a canonical gameplay writer.

## Dependency Order

```text
P5D fresh-green -> P6A capability boundary -> P6B UI/CLI/MCP alignment
                 -> P6C package lifecycle -> P6D creator operations slice
```

P6 consumes [P5D RPG investigation](../phase-five-rpg-social-gameplay/2026-08-10-p5d-rpg-investigation-vertical-slice-design.md)
and the closed-core/Patch contracts in the Character Gameplay Foundation tree.

## Documents

1. [P6A capability and closed-core boundary](2026-08-10-p6a-creator-capability-and-closed-core-boundary-design.md)
2. [P6B UI, CLI and MCP alignment](2026-08-10-p6b-ui-cli-and-mcp-authoring-alignment-design.md)
3. [P6C package publishing and remote operations](2026-08-10-p6c-package-publishing-and-remote-operations-design.md)
4. [P6D creator operations vertical slice](2026-08-10-p6d-creator-operations-vertical-slice-design.md)

Matching plans: [P6A](../../../plans/world-character-siming-authority-mainline/phase-six-creator-control-plane/2026-08-10-p6a-creator-capability-and-closed-core-boundary-implementation-plan.md),
[P6B](../../../plans/world-character-siming-authority-mainline/phase-six-creator-control-plane/2026-08-10-p6b-ui-cli-and-mcp-authoring-alignment-implementation-plan.md),
[P6C](../../../plans/world-character-siming-authority-mainline/phase-six-creator-control-plane/2026-08-10-p6c-package-publishing-and-remote-operations-implementation-plan.md),
[P6D](../../../plans/world-character-siming-authority-mainline/phase-six-creator-control-plane/2026-08-10-p6d-creator-operations-vertical-slice-implementation-plan.md).
