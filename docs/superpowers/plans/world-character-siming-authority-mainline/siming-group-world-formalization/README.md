# Siming Group World Formalization Plan Tree

Status: `draft plan; execution blocked until each SGC contract is approved`

## Documents

1. [Program plan](2026-08-17-sgc-siming-group-world-formalization-implementation-plan.md)
2. [SGC-1 plan](01-sgc-1-governed-siming-capability-plan.md)
3. [SGC-2 plan](02-sgc-2-derived-cognitive-graph-plan.md)
4. [SGC-3 plan](03-sgc-3-population-fidelity-continuity-plan.md)
5. [SGC-4 plan](04-sgc-4-presentation-view-plan.md)
6. [SGC-5 plan](05-sgc-5-performance-replay-evidence-plan.md)

Read the matching [formal spec](../../../specs/world-character-siming-authority-mainline/siming-group-world-formalization/README.md) and the August analysis package before executing any task.

## Dependency And Status Matrix

| Package | Depends on | Current state | First executable action | Stop state |
| --- | --- | --- | --- | --- |
| SGC-1 capability | one complete existing owner row | `owner-contract blocked until selected` | freeze row and write RED | `owner-contract blocked` |
| SGC-2 graph | approved scoped authority projection | `source gate pending` | freeze reader/scope fixture | `owner-contract blocked` |
| SGC-3 continuity | committed cadence projection plus admitted owner consumer | `cadence gate pending` | freeze mode/cadence revisions | `owner-contract blocked` |
| SGC-4 presentation | owner event family plus published manifest | `presentation source pending` | freeze view schema and privacy layers | `owner-contract blocked` |
| SGC-5 evidence | one verified SGC-1..4 vertical | `deferred` | freeze synthetic benchmark inputs | `unimplemented` |

The execution order is SGC-1 -> SGC-2 -> SGC-3 -> SGC-4 -> SGC-5. A blocked
package does not authorize the next package's missing owner; the next package
may proceed only if its own dependency row is independently satisfied.

## Evidence Convention

Focused pytest output, Harness JSON/Markdown reports, source/revision digests,
privacy/redaction evidence and checkpoint-tail comparisons are stored under
`.harness/verification/sgc-1/` through `.harness/verification/sgc-5/`.
Profile names are registered through the existing `.harness/profiles/*.json`
and `.harness/rules/*.json` manifests. These manifests are verification
configuration, not a runtime registry.
