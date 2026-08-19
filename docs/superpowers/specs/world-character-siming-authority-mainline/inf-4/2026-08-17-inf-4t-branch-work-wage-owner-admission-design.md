# INF-4T Branch Work To Economy Wage Owner-Admission Design

Status: `approved and implemented narrow vertical; generic branch promotion remains not implemented`

## Scope And Decision

This proposal evaluates one bounded candidate only:

```text
creator-debug BranchPreview work candidate
  -> existing Economy wage accrual
```

The candidate is **not** admitted as currently shaped. A branch candidate is a
proposal/evidence record, not completed-work truth. The only legal source for
the existing wage outcome is a committed, worker-scoped Production
`work_completion_evidence_recorded` event. The branch may carry a request or
digest for that source, but it may not manufacture, replace, or promote a
Production fact.

This design therefore preserves the existing INF-4Z
Production-to-Economy wage consumer and adds one separately admitted,
branch-requested invocation of the same existing Economy owner. It does not
create a branch owner, population/social owner, promotion writer, or generic
branch-to-Economy router. Approval does not authorize a branch candidate to
substitute for Production evidence.

## Owner And Fact Boundary

| Fact | Owner | Boundary |
| --- | --- | --- |
| isolated branch candidate/proposal and branch replay | existing `BranchPreviewAuthority` | creator-debug buffer only; never production truth |
| completed worker evidence | existing `ConstructionProductionAuthority` | committed `work_completion_evidence_recorded` and actor-scoped view |
| wage accrual obligation/event | existing `EconomyAuthority` | actor-scoped `gameplay:economy:wage:{worker_ref}` only |
| branch promotion, population/social truth, payroll payment, correction or compensation | not admitted | no owner/capability exists in this row |

## Proposed Typed Intent And Source Admission

Proposed capability reference: `capability:branch-work-wage-promotion@1`.

An intent may identify a branch request and an authenticated worker, but it
cannot select an owner, stream, event family, wage policy, privacy scope,
revision, receipt, retry, or compensation rule. The target worker is bound to
the authenticated actor envelope. Any evidence reference is only a lookup key;
the Economy owner must re-read the canonical Production view and reject a
branch-only or forged reference.

`BranchWorkWageRequest` contains only that request metadata and the digest of
the existing INF-4Z wage plan. It does not embed the plan or its wage-policy
payload. The separate existing plan is revalidated against the request digest,
canonical Production evidence, and current Economy revision before append.

Admission would require:

1. a committed Production
   `gameplay.construction_production.work_completion_evidence_recorded` event
   on its canonical facility stream;
2. the exact worker-scoped `ProductionCompletedEvidenceView`, including event
   refs, source stream revisions, digest, evidence ref, run-finished source
   pin, assignment and work-order linkage;
3. an authenticated branch request whose branch replay contract, base/tail
   digest and candidate digest match the request, while the branch remains
   creator-debug and is never treated as the source event; and
4. the current Economy wage stream revision and fixed wage policy revision.

If (1) or (2) is absent, there is no branch promotion. The request rejects
before any Economy append. The existing INF-4Z `merge_production_evidence_wage`
path is the valid non-branch operation and must not be renamed or generalized.

## Fixed Target Contract If Separately Approved

| Boundary | Fixed value |
| --- | --- |
| Source owner/event | `actor_gameplay.construction_production_domain` / `gameplay.construction_production.work_completion_evidence_recorded` |
| Target owner/event | `actor_gameplay.econ1_economy_domain` / `gameplay.economy.wage_accrued` |
| Target stream | `gameplay:economy:wage:{worker_ref}` |
| Append path | Economy owner fragment through `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()` |
| Target revision | current exact wage stream head; source Production revision vector is a read-set pin |
| Privacy | source `actor:{worker_ref}` and target actor scope; creator-debug branch data never enters the target projection |
| Receipt | one Economy append-derived owner receipt; no branch/production combined receipt |
| Replay | existing Economy wage projection full/checkpoint-tail replay plus independent branch replay; histories are never merged |

The immutable catalog entry `inf:branch-work-wage-admission@1` fixes the
existing Economy owner, wage stream/event and project replay reader. It is
read-only metadata and is checked before the owner append; it is not a runtime
registry.

## Idempotency, Terminal, And Compensation Semantics

The idempotency key would be fixed to the canonical worker/evidence/wage cycle
identity used by the existing INF-4Z row. Exact duplicates replay the Economy
append result; changed duplicates are zero-write. A branch digest mismatch,
stale Production source, stale wage head, or changed wage policy rejects before
append.

The only terminal event admitted by this proposal is the existing Economy wage
accrual. Payroll payment, wage reversal, retry scheduling, correction and
compensation are explicitly not admitted. Branch deletion discards branch
evidence; it cannot roll back or reopen the Economy wage event. Any future
correction would require a separate Economy owner-local contract.

## Required Zero-Write Rejections

- branch candidate without the committed Production evidence event/view;
- branch or creator-debug data supplied as a replacement for Production
  source, stream, revision or worker binding;
- source/branch digest, worker, assignment, run, policy or wage revision
  mismatch;
- public, authority-only, or caller-selected privacy scope;
- caller-selected owner, stream, event family, receipt, retry or compensation;
- unknown or unapproved capability/catalog row;
- exact idempotency key with changed payload; and
- any request for multiple workers, fanout, payroll payment, generic promotion,
  or branch merge.

## Approval Boundary

The approved implementation adds only a typed `BranchWorkWageRequest`, an
immutable catalog row, and a request validator on the existing continuity
consumer. Validation rereads the canonical Production view and durable
creator-debug branch snapshot, then invokes the existing Economy owner through
the normal envelope/SettlementPlan/append spine. It appends only
`gameplay.economy.wage_accrued`; branch history remains isolated and branch
promotion remains unsupported.
