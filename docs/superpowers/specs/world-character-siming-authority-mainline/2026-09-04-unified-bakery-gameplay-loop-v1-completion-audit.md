# Unified Bakery Gameplay Loop v1 Completion Audit

Status: `implemented narrow vertical; all Bakery Loop v1 gates verified`

Task 1 deterministic three-period owner composition is implemented and
verified. Task 2 adds an injected Construction `run_failed@1` outcome with
explicit Inventory reservation-release recovery. Task 3 exposes committed-only
period, facility, output, sale, permit and failure/recovery state through the
read-only Bakery mirror and Harness.

The default scenario now binds its organization owner to the committed,
repository-visible `character:char_a` profile; no synthetic owner ref is used.

Task 4 replay evidence covers full replay and checkpoint-tail replay equality,
including tampered-checkpoint rejection.

The fixed employee path now records Economy-owned wage accrual and payment
facts through existing wage/account APIs; the read-only mirror reports wage
parity without owning payroll truth.

The employee path also admits one fixed existing Contract `simple_service`
employment record per employee before wage accrual, retaining Contract as the
source of labor terms rather than adding bakery-owned contract state.

Completed production now carries an existing Construction work-contribution
record and verified completion-evidence event; Economy wage accrual references
that committed evidence rather than a caller or synthetic skill claim.

Employee admission reads the existing Character capability layer and fails
closed before any append when the skill declaration is absent; this is a gate,
not a duplicate Skill owner or caller-provided skill truth.

Simulation-mode periods also exercise the existing Survival owner tick; the
default narrative/disabled modes remain non-authority presentation choices.

The repository-wide backend regression is green (`5057 passed`). Godot project
import, scene-load smoke, static scene checks, and the dedicated headless plus
desktop `BakeryCommittedMirrorProbe` all pass after Git LFS hydration. The
broader `phase0` verifier still reports missing observatory/live presentation
markers, but those are outside this Bakery Goal's scope. Dedicated
`BakeryCommittedMirrorProbe` passes in both headless and desktop modes.

August INF A-D remains `not complete` and is not changed by this loop.
