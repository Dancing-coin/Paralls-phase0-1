# DG-P6/P7 Opening Evidence And Internal Parallelism Record

Status: `DG green; P6/P7 remain separately gated and unopened`

Historical narrow-foundation evidence (2026-08-12, commit `7b6866293e16ed6d7053666ebf4d7bf80f4f2873`):

| Gate | Report | Run archive | Conclusion |
| --- | --- | --- | --- |
| F0 | `.harness/verification/post-p5-capability-foundation-docs-report.json` plus F0 manifest | `run-20260812-103033-676396` | green, documentation/evidence baseline only |
| F1A | `.harness/verification/post-p5-f1a-foundation-report.json` | `run-20260812-103257-430200` | green, partial foundation only |
| F1B | `.harness/verification/post-p5-f1b-foundation-report.json` | `run-20260812-103257-430795` | green, partial foundation only |
| F1C | `.harness/verification/post-p5-f1c-foundation-report.json` | `run-20260812-103257-430801` | green, partial foundation only |
| F2 | `.harness/verification/post-p5-f2-gates-report.json` | `run-20260812-103516-508968` | green, taxonomy gate only |

These reports do not satisfy the generic F1A/F1B/F1C contracts or authorize P6/P7 implementation. They remain historical precursor evidence only.

## Current DG evidence

The executable checklist is `.harness/verification/post-p5-dg-opening-report.json`.
It is the source of the current F0/F1A/F1B/F1C/F2 complete-profile paths,
run IDs, working-tree or commit fingerprint, owner, freshness rule,
invalidation condition, rollback target, and successor state. The report is
fail-closed: if any complete profile is absent or stale, DG is
`planned/blocked`. A green DG row still sets `p6_p7_authorized: false`; P6/P7
require their own explicit implementation authorization and profiles.

## Decision already made

The external order is fixed:

```text
P5 -> post-P5 capability foundation -> P6 -> P7
```

This record does not rename or renumber P6/P7. It decides only whether a
sub-track may start and which work can be prepared in parallel.

## Evidence freshness contract

An opening row is green only when its report was generated at the current
commit, or at a named compatible commit whose owner, write path, contract
revision and assertion set have been reviewed unchanged. The DG checklist must
record both `commit` and Harness `run_id`; a latest-path alone is not durable
evidence. Future-dated/staged documentation is design input, not proof.

Changing an owner, write path, contract/schema revision, projection or privacy
rule, Harness assertion, migration, or rollback behavior invalidates every
successor row that relies on it. That row returns to `planned` until its
predecessor profile and downstream profile have been rerun.

## Opening matrix

| Track | Required predecessor evidence paths | May prepare in parallel | Hard implementation gate | Expected future profile |
| --- | --- | --- | --- | --- |
| P6A | `phase5a-quest-objective-evidence-report.json`, `phase5b-relationship-reputation-knowledge-report.json`, F0 ledger, future `post-p5-f1a-semantic-causal-gate-report.json`, future `post-p5-f1b-social-privacy-gate-report.json` | P6B contract design | capability boundary, denial and privacy evidence | `p6a-creator-scope-authority` |
| P6B | P6A report plus `docs/8月分析/第六阶段推进/02-UI、CLI与MCP对齐契约.md` | P6C package schema design | UI/CLI/MCP authorization parity | `p6b-control-plane-channel-parity` |
| P6C | P6B report, future `post-p5-f1c-package-governance-gate-report.json`, future `post-p5-f2-proof-taxonomy-gate-report.json` | P6D fixture design | activation, rollback, audit and replay evidence | `p6c-governed-package-activation` |
| P6D | P6C report plus `docs/8月分析/第六阶段推进/04-创作者流程与第六阶段门禁.md` | P7 read-only research design | creator vertical slice and governance evidence | `p6d-creator-governed-vertical-slice` |
| P7A-D | P6D report, F2 report, `docs/8月分析/第七阶段推进/04-文明推演参考包与第七阶段门禁.md` | only read-only research preparation before P6D | branch replay, proposal-only, reproducibility and safety profiles | `p7a-branch-replay`, `p7b-world-model-safety`, `p7c-civilization-reference`, `p7d-robotics-safety` |

All report names above are relative to `.harness/verification/`. The four
`post-p5-*` profiles and all P6/P7 profiles are required future profiles, not
registered current profiles; their names define the acceptance surface that
the matching implementation plan must create before claiming that track green.

## Five-week gate schedule

| Week | Deliverable | Gate owner |
| --- | --- | --- |
| 1 | F0 ledger and P1-P5 evidence reconciliation | baseline/release owner |
| 2 | F1A semantic/rule/causal contract | world/runtime owner |
| 3 | F1B social/privacy and F1C package governance contract | projection and ops owners |
| 4 | F2 profile, replay, privacy, zero-write, audit taxonomy | Harness owner |
| 5 | opening checklist and responsibility matrix | mainline maintainer |

## Required decision evidence

The checklist must link each predecessor report with its `run_id`, `commit`,
run date, compatibility decision, next owner, rollback target, and stale state;
it then states whether the track is `green`, `planned`, or `blocked`.
Any proposal to remove the P6D predecessor, rename phases, or add a new owner
requires a separate migration decision record.

## Non-goals

This record does not authorize P6/P7 implementation, direct world writes,
parallel runtime creation, or a claim that creator tooling, civilization
simulation, world-model runtime, or robotics runtime is complete.
