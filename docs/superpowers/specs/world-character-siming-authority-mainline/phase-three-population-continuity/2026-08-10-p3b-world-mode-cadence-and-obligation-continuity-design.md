# P3B World Mode, Cadence And Obligation Continuity

Status: `design-only; implementation not authorized`

## Purpose And Contract

A revision-pinned `WorldModeProfile` selects game, persistent-simulation or
branch-consumption precision, wake budget, allowed intent classes, Survival
mode, catch-up policy, load degradation and pause/resume semantics. It uses the
existing `world_runtime` entry point; it is not a new world clock.

Due work, payroll, consumption, permits and taxes remain their owners' explicit
obligations. Cadence can request due evaluation using typed envelopes, but it
cannot settle inventory, accounts, needs or government facts. Catch-up is
deterministic from checkpoint plus committed tail, pins policy revision and
records an explanation; it cannot invent elapsed actions.

## Gate

Prove pause/resume, Survival mode selection, budget degradation, overdue
handling, replay equivalence and no implicit tick writes. A universal
`SimulationClock` or economy scheduler is out of scope.
