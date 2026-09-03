# Unified Bakery Gameplay Loop v1 Completion Audit

Status: `implementation-active; backend/replay/Harness gates verified; Godot dynamic gate pending`

Task 1 deterministic three-period owner composition is implemented and
verified. Task 2 adds an injected Construction `run_failed@1` outcome with
explicit Inventory reservation-release recovery. Task 3 exposes committed-only
period, facility, output, sale, permit and failure/recovery state through the
read-only Bakery mirror and Harness.

Task 4 replay evidence covers full replay and checkpoint-tail replay equality,
including tampered-checkpoint rejection. Final repository regression and Godot
desktop evidence remain the release gate before declaring the Goal complete.

The fixed employee path now records Economy-owned wage accrual and payment
facts through existing wage/account APIs; the read-only mirror reports wage
parity without owning payroll truth.

The employee path also admits one fixed existing Contract `simple_service`
employment record per employee before wage accrual, retaining Contract as the
source of labor terms rather than adding bakery-owned contract state.

Simulation-mode periods also exercise the existing Survival owner tick; the
default narrative/disabled modes remain non-authority presentation choices.

The repository-wide backend regression is green (`5057 passed`). Godot project
import, scene-load smoke, and static scene checks pass after Git LFS hydration;
the broader `phase0` dynamic verifier still reports missing observatory/live
presentation markers, so this Goal remains active pending a Bakery-specific
Godot projection smoke or an accepted runtime-equivalent evidence artifact.

August INF A-D remains `not complete` and is not changed by this loop.
