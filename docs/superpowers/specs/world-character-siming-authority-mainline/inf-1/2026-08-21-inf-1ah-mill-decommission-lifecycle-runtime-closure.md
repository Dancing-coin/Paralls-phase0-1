# INF-1AH Mill Decommission Lifecycle Runtime Closure

Status: `implemented and verified; August INF A-D remain not complete`

The admitted INF-1AH row is now implemented solely in
`ConstructionProductionAuthority`. It accepts one owner-derived source vector:
project-visible `facility_acquired(mill)` plus the exact committed frozen-v2
`mill -> mill_reinforced` event. With the exact active frozen-v3 binding, it
appends one project-visible
`gameplay.construction_production.facility_decommissioned@1` event.

The projector has one row-specific reducer. It preserves facility kind,
condition, plot binding, runs, reservations, and output references; it changes
only the eligible facility's lifecycle from `active` to `decommissioned` and
increments its revision once. The status is not inferred for unrelated
facilities.

Before append, the owner rejects with zero writes any inactive, unknown,
ambiguous, or mismatched v3 binding; invalid v2 source pins; private or wrong
source evidence; project/facility/revision conflicts; non-active targets; or
an already committed started run for the facility. Started runs are neither
cancelled nor compensated. Exact idempotency replays its append receipt;
changed use of the same key fails closed.

Verification on 2026-08-21:

- `59 passed` across the focused decommission, descriptor-admission,
  reinforcement, package-transform, and catalog regression tests.
- `infra-construction-mill-decommission` Harness passed.
- `infra-construction-mill-decommission-descriptor-admission` Harness passed.
- Repository-root `python -m pytest -q` completed with `3846 passed, 6 failed`;
  the six failures are unrelated pre-existing Godot/script-evolution evidence
  checks (one also reports an environment `MemoryError`), not INF-1AH tests.
- `git diff --check` passed.

The dedicated lifecycle Harness is intentionally excluded from the broad
`all` profile, like its descriptor-admission prerequisite. This closes only
the exact INF-1AH vertical and does not add generic lifecycle actions,
reactivation, compensation, fanout, payments, materials, maintenance, or any
INF-2/3/4 authority.
