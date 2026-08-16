# INF-3C Weather-Front Regional Propagation Implementation Plan

Status: `implemented and verified for the named bounded row`

Date: `2026-08-14`

1. Add an independent focused test module for a two-region symmetric adjacency
   fixture. Run it before implementation and retain the expected missing-entry
   failure as RED evidence.
2. Extend only `EnvironmentRegion` and `EcologyHazardAuthority` with the formal
   adjacency/policy contract. Reuse the region's canonical event row and the
   existing `regional_projection`; do not add edge storage.
3. Implement one caller-driven propagation command that validates both ecology
   heads and emits disjoint source/target fragments through the existing
   multi-stream batch builder. Emit project outbox rows only.
4. Add a dedicated profile whose individual checks invoke distinct assertions
   for success, stale revision, adjacency rejection, idempotency, privacy and
   checkpoint-tail replay. Store its report under `.harness/verification/`.
5. Update the August INF status and root dependency docs. Keep broader fanout,
   hazards and every external consumer explicitly unimplemented.
6. Run the focused suite/profile, `git diff --check`, and `python -m pytest -q`.

## Execution record

Steps 1 through 5 are complete. The RED test initially failed because the
closed policy/entrypoint did not exist. The focused suite passed after the
owner-only implementation, and the dedicated profile generated
`.harness/verification/infra-ecology-weather-front-propagation-report.json`.
The final repository verification remains the required terminal step for this
execution turn.
