# INF-4 Specification Tree

Status: `narrow predecessor verticals implemented and verified; August INF-4 mainline remains incomplete`

1. [INF-4 population and branch preview design](2026-08-12-inf-4-population-branch-preview-design.md)
2. [INF-4R population world-mode and civilization-interface expansion design](2026-08-12-inf-4r-population-world-mode-and-civilization-interface-expansion-design.md)
3. [INF-4X household and organization source projection design](2026-08-12-inf-4x-household-organization-source-projection-design.md) - bounded source projection verified; real schedule settlement remains open
4. [INF-4Y civilization capability read interface design](2026-08-12-inf-4y-civilization-capability-read-interface-design.md) - owner admission plus approved supply and inspection eligibility edges
5. [INF-4Z complete population world-mode design](2026-08-12-inf-4z-complete-population-world-mode-design.md)
6. [INF-4Z production completed-evidence source admission](2026-08-13-inf-4z-production-completed-evidence-source-design.md) - verified source prerequisite; it does not admit wage accrual
7. [INF-4Z production evidence wage consumer](2026-08-13-inf-4z-production-evidence-wage-consumer-design.md) - verified one narrow Production-to-Economy consumer; generic work remains rejected
8. [INF-4Z reference-data license admission](2026-08-13-inf-4z-reference-data-license-admission-design.md) - verified authority-scoped calibration admission; no external ingestion or branch promotion
9. [INF-4C activation pending schedule merge](2026-08-14-inf-4c-activation-pending-schedule-merge-design.md) - verified one released `schedule_gated_supply` row; generic pending remains blocked
10. [INF-4D isolated owner-disposition branch design](2026-08-14-inf-4d-isolated-owner-disposition-branch-design.md) - verified analysis mapping only; no domain consequence
11. [INF-4F isolated owner-fragment evaluation design](2026-08-14-inf-4f-isolated-owner-fragment-evaluation-design.md) - verified non-production builder validation only; no settlement or promotion
12. [INF-4G isolated owner consequence projection design](2026-08-14-inf-4g-isolated-owner-consequence-projection-design.md) - verified isolated branch-local planned commitment/inspection projection; no settlement, receipt or promotion
13. [INF-4H Organization branch scenario settlement design](2026-08-14-inf-4h-organization-branch-scenario-settlement-design.md) - verified one Organization-owned supply scenario event on a non-production stream; no generic settlement or promotion
14. [INF-4I Government branch scenario settlement design](2026-08-14-inf-4i-government-branch-scenario-settlement-design.md) - verified one evidence-backed Government passed-inspection scenario row
15. [INF-4J Government failed-inspection remediation scenario design](2026-08-14-inf-4j-government-failed-inspection-remediation-scenario-design.md) - verified one evidence-backed fixed Government remediation row
16. [INF-4L durable BranchPreview admission evidence design](2026-08-14-inf-4l-durable-branch-preview-admission-design.md) - verified preview-evidence provenance repair for the Government scenario rows
17. [INF-4K Government branch remediation receipt design](2026-08-14-inf-4k-government-branch-remediation-receipt-design.md) - verified one derived evidence-backed remediation receipt row; no generic receipt or promotion
18. [INF-4M durable isolated branch snapshot design](2026-08-15-inf-4m-durable-isolated-branch-snapshot-design.md) - verified explicit creator-debug persistence and fresh-instance replay of the existing isolated branch buffer; no production settlement or promotion
19. [INF-4N Government inspection promotion design](2026-08-15-inf-4n-government-inspection-promotion-design.md) - independently verified fixed Government-owned passed-inspection production consequence; no generic promotion
20. [INF-4O Organization supply promotion design](2026-08-15-inf-4o-organization-supply-promotion-design.md) - independently verified fixed Organization-owned supply production consequence; no generic promotion
21. [INF-4P durable isolated branch evolution design](2026-08-15-inf-4p-durable-branch-evolution-design.md) - one fixed redacted owner-consequence evolution event on the existing branch stream; no production write or generic promotion
22. [INF-4Q Government promotion owner-contract catalog design](2026-08-16-inf-4q-government-promotion-owner-contract-catalog-design.md) - fixed Government promotion row now has immutable pre-append catalog admission; no generic promotion
23. [INF-4S Government failed-inspection promotion design](2026-08-15-inf-4s-government-failed-inspection-promotion-design.md) - independently verified fixed Government failed-inspection production consequence; no generic promotion
24. [INF-4AA P3D schedule-gated supply reclosure](2026-08-16-inf-4aa-p3d-schedule-gated-supply-reclosure-design.md) - verified real released schedule -> Organization settlement; no generic population merge
25. [INF-4AB released Survival expiry batch closure](2026-08-16-inf-4ab-released-survival-expiry-batch-closure-design.md) - independently verified second released-pending Survival settlement and single-append receipt boundary; no generic merge or branch promotion
26. [INF-4AC activation-owned profile region assignment](2026-08-16-inf-4ac-activation-region-assignment-design.md) - independently verified project-scoped, evidence-pinned profile-to-region prerequisite; no Survival write or population truth owner
27. [INF-C5 (INF-4) deterministic fixed-base branch replay contract](2026-08-17-inf-c5-fixed-base-branch-replay-contract-design.md) - independently verified pure fixed-base/calibration/input-order/projection replay contract over the existing isolated branch and fixed Organization supply admission

INF-4Z and INF-4Z-A supersede the base document's earlier source/revision/digest/
calibration-admission gaps. INF-4C supersedes the former fail-closed-only
activation-lock statement for one released schedule row. INF-4H, INF-4I and
INF-4J add three event-sourced branch scenario rows for accepted Organization
`supply`, passed Government `inspection`, and failed Government `inspection`
with fixed `follow_up_required` remediation. Their branch streams are
non-production and excluded from production replay; none is a generic branch
receipt, remediation lifecycle or promotion authority. Remaining gaps: other
owner scenario rows, generic branch settlement/receipt, promotion (zero-write),
or complete group
simulation. INF-4N separately verifies only the exact Government passed-inspection
source admission -> branch scenario -> production inspection row; it does not
authorize other owner fragments or complete group simulation. Evidence:
[Organization scenario](../../../../../.harness/verification/infra-organization-branch-scenario-settlement-report.json),
[Government scenario](../../../../../.harness/verification/infra-government-branch-scenario-settlement-report.json),
[fixed remediation](../../../../../.harness/verification/infra-government-failed-inspection-remediation-scenario-report.json),
[remediation receipt](../../../../../.harness/verification/infra-government-branch-remediation-receipt-report.json),
[durable admission](../../../../../.harness/verification/infra-durable-branch-preview-admission-report.json),
[durable snapshot](../../../../../.harness/verification/infra-durable-isolated-branch-snapshot-report.json),
and [INF-4N promotion](../../../../../.harness/verification/infra-government-inspection-promotion-report.json).
The failed companion row is separately evidenced by
[INF-4S promotion](../../../../../.harness/verification/infra-government-failed-inspection-promotion-report.json).
The fixed Organization supply promotion is separately evidenced by
[INF-4O promotion](../../../../../.harness/verification/infra-organization-supply-promotion-report.json).
INF-4Q additionally fences the existing Government production promotion with
an immutable owner/stream/event/scope catalog row before fragment construction;
its separate evidence is [INF-4Q catalog admission](../../../../../.harness/verification/infra-government-promotion-owner-contract-catalog-report.json).
This scope reuses CharacterProfile identity and does not establish a population,
social, household, organization, or civilization truth owner.

INF-C5 (INF-4) now canonicalizes the fixed branch replay inputs and recomputes
the isolated projection digest for full and checkpoint-tail readers. Its
contract is consumed by the existing Organization supply admission before the
owner builds the production fragment. It does not authorize any other owner,
generic branch settlement, generic receipt, generic promotion, or complete
group simulation. Evidence: [INF-C5 fixed-base replay](../../../../../.harness/verification/infra-fixed-base-branch-replay-contract-report.json).

INF-4P now makes the isolated branch durable beyond a single snapshot for one
fixed accepted owner consequence: `authority:branch_preview` appends a redacted
`owner_consequence_applied` event to the existing creator-debug branch stream,
and a fresh authority rebuilds snapshot plus ordered evolution. This is branch
evidence, not a branch-domain truth owner or promotion path.

User-directed deferral (2026-08-15): complete group simulation is not active
implementation work, but remains unimplemented and must stay visible in the
mainline closure record.  Promotion remains unsupported for every row except
the separately admitted INF-4N Government passed-inspection, INF-4S Government
failed-inspection, and INF-4O Organization supply contracts; all other
promotion inputs remain zero-write.
