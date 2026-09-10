# Task 2 Report

## Outcome

Added `publish_authorized_population_cadence(...)` in `backend/app/main.py`.
It validates the caller-supplied cadence source and current store revision vector,
assembles Task 1 committed projections, rejects duplicate or scope/vector-invalid
legacy projections, and publishes one `population_cadence_event`. It does not
mint cadence time, append gameplay facts, call an Owner or Character Core, or
start a scheduler.

The game-start path now constructs its existing authorized cadence and legacy
Bakery projection, then delegates to the publisher. Its single explicit
game-start cadence remains intact.

## Verification

- `python -m pytest -q backend/tests/test_siming_population_authorized_cadence_publication.py backend/tests/test_siming_population_production_boundaries.py backend/tests/test_siming_population_domain_owner_runtime.py`
  - 48 passed
- `git diff --check`
  - passed
- `python -m compileall -q backend/app/main.py backend/tests/test_siming_population_authorized_cadence_publication.py`
  - passed

## Boundary

- Completed and verified: authorized cadence publication seam and game-start delegation.
- Not Godot-related: this task changes backend-only authority publication.
- No scheduler or autonomous cadence source was added.

## Review Fixes

- Projection revision vectors are now accepted when they are current subsets of
  `cadence.base_revision_vector`; the publisher no longer requires equal key sets.
- Cadence sources are limited to bound world-mode resume, activation, or
  Organization schedule projections with admitted visibility.
- Caller-supplied legacy rows are limited to the existing typed
  `schedule_gated_supply` capability and committed schedule evidence shape.
- Published projections are serialized in deterministic `ref` order.
- A real multi-stream publication test proves that an assembled Production
  projection survives the union.

Review-fix verification:

- Task 1 + Task 2 focused suite: `79 passed, 3 deselected`; the deselected tests
  are the paused Task 3 drafts already present in the shared test file.
- The shared worktree still contains uncommitted Task 3 changes; they are not
  included in the Task 2 fix commit.
