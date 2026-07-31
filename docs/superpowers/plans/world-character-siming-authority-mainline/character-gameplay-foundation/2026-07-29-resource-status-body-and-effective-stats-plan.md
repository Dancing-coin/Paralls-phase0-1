# Resource, Status, Body, And Effective Stats Plan

Status: `drafted-for-spec-review`

## Dependencies

Event/projection spine and state-group facade plans.

## Work

1. Register `core.resource`, `core.status_tags`, `adventure.body_runtime`, and
   `core.effective_stats` with separate commands, events, projections, privacy,
   and mirror policies.
2. Implement resource cost/reservation/commit, status-tag lifecycle, body
   function/injury state, deterministic modifier ordering, and every-value
   explanation sources.
3. Bridge only filtered resource/body/effective-stat summaries into the current
   CharacterAgent affordance input; do not merge them into `NeedTensionState`
   or `CharacterDynamicState`.
4. Prove a learned action is blocked by right-arm injury and by insufficient
   stamina, restores when conditions recover, and never consumes cost on
   rejection.

## Exit Criteria

This is the first minimal gameplay loop: materialize groups, settle an action,
append events, rebuild the facade, and emit a typed mirror delta. No inventory,
equipment, or economy is required for this exit.

## Evidence

`gameplay-state-groups` and focused resource/body/effective-stat replay tests.
