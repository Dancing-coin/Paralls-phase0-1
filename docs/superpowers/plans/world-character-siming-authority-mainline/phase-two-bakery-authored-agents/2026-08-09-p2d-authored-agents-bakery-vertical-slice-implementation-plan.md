# P2D Authored-Agents Bakery Vertical Slice Implementation Plan

Status: `historical plan superseded; P2D-R re-closure required`

## Hard prerequisites

Before any P2D implementation command, verify fresh `phase1d-econ1-bakery` plus P2A, P2B and P2C
focused profiles. Static docs cannot substitute for these reports.

## Exact files and order

1. Add `backend/tests/fixtures/phase2_bakery_authored_agents.py` and
   `backend/tests/test_phase2d_authored_agents_bakery_vertical_slice.py`; the fixture references three already
   registered profiles and declares operator, baker/production and counter/procurement roles without
   mutating authored identity.
2. Add backend integration assertions to `backend/tests/test_phase2d_authored_agents_bakery_vertical_slice.py`
   for two successful roles, an auditable operator manager principal, a counter procurement
   WorkOrder linked to the existing fixed-quote purchase receipt, a second-window recoverable failure,
   aggregate demand, public competitor profile, wage payment or overdue, and no partial write.
3. Compose existing organization/production/inventory/economy/survival/government authorities through
   their existing event store and `SettlementPlan`; do not add a vertical-slice authority.
4. Add full/checkpoint-tail replay and actor/manager/Godot scope-filtered mirror tests to
   `backend/tests/test_gameplay_event_replay.py`,
   `backend/tests/test_gameplay_shared_replay_and_permission.py`, and
   `backend/tests/test_godot_gameplay_mirror_projection.py` using the existing
   `GameplayMirrorSubscriptionRegistry` and committed outbox. Replay setup must explicitly re-grant
   session scope; grants themselves are not replayed canonical state.
5. Added the exact Harness files after the preceding tests were green:
   `.harness/profiles/phase2-bakery-authored-agents.json`,
   `scripts/verification/verify_phase2_bakery_authored_agents.py`, and the report/trace artifacts
   under `.harness/verification/`; the fresh report records 65 committed events and matching
   full/checkpoint-tail hashes.

## Required evidence matrix

Capture profile registry lookup, assignment/shift/work evidence, owner/event diff, stream revisions,
idempotency/causation/correlation/pinned revisions, facility/reservation race, wage evidence refs,
payment/overdue receipt, full/checkpoint-tail hashes, mirror redaction, and a no-new-owner audit.

## Verification commands

```powershell
python -m pytest -q backend/tests/test_bakery_domain_integration.py backend/tests/test_bakery_failure_recovery.py backend/tests/test_bakery_reference_runtime.py backend/tests/test_bakery_mirror_source.py backend/tests/test_gameplay_event_replay.py backend/tests/test_gameplay_shared_replay_and_permission.py
python scripts/verification/harness.py --profile phase1d-econ1-bakery
python scripts/verification/harness.py --profile phase2-bakery-authored-agents
python scripts/verification/harness.py --profile docs
```

## Explicit non-authorization

The historical implementation did not satisfy this plan: it constructed batches in the verifier
instead of composing the stated owner entry points, and its focused test did not exercise the
success scenario. It is therefore superseded by
[`P2D-R`](2026-08-15-p2d-r-authored-bakery-authority-reclosure-plan.md). The new plan retains the
no-Population/no-NPC/no-second-store/no-scheduler boundary.
