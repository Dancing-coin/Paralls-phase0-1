# INF-1AM Reinforced Mill Flour Output Certification Plan

Status: `implemented and verified; narrow vertical only`

1. Add focused RED tests for the exact v2-reinforced mill/run source vector,
   project privacy, source/revision pins, duplicate/change rejection, receipt,
   and full/checkpoint-tail replay.
2. Add the one immutable Construction descriptor/catalog contract.
3. Add the fixed verifier and one project-scoped event partition to the
   existing Construction projector and append spine.
4. Add an independent Harness, run focused and adjacent Construction tests,
   then synchronize the ledger. No Inventory, Economy, material movement, or
   generic output implementation is in this plan.
