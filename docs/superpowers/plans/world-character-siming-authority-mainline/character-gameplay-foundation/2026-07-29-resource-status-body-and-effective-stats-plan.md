# Resource, Status, Body, And Effective Stats Plan

Status: `minimum-resource-body-gate-implemented; broader-domain-closure-planned`

## Dependencies

Event/projection spine and state-group facade plans.

## Work

1. [~] Register `core.resources`, `core.status_tags`, `core.body_runtime`, and
   `core.effective_stats` with separate commands, events, projections, privacy,
   and mirror policies.
   The current narrow gate consumes already-enabled `core.resources` and
   `core.body_runtime` groups. It does not register tags/effective stats or
   add consumer/mirror policy.
2. [~] Implement resource cost/reservation/commit, status-tag lifecycle, body
   function/injury state, deterministic modifier ordering, and every-value
   explanation sources.
   The implemented slice rebuilds integer resources, explicit reservation
   created/consumed/released state, and injury-derived
   functional capacity from committed events. It rejects insufficient stamina
   and unavailable required functions before a batch, then atomically records
   resource cost plus action settlement. It reuses the existing skill-path
   evaluation only as a read gate, so it creates no second skill-state owner.
   A backend-only reservation authority service validates the current resource
   projection before appending reserve/consume/release events; timeout policy
   remains planned.
   A pure backend-only effective-stat resolver now covers canonical modifier
   ordering, condition rejection, stacking policy, and explanation digest;
   modifier-source lifecycle and runtime projection remain planned. The initial
   status-tag authority lifecycle now covers explicit apply/remove/expire,
   stack-count limits, exclusivity, and replay; refresh policies, source-bound
   duration and consumer views remain planned. Active tags now contribute only
   registered typed modifier templates; remove/expire removes their source
   before effective-stat resolution. Arbitrary template code remains forbidden.
3. [ ] Bridge only filtered resource/body/effective-stat summaries into the current
   CharacterAgent affordance input; do not merge them into `NeedTensionState`
   or `CharacterDynamicState`.
4. [x] Prove an action with an unchanged requirement is blocked by missing skill
   path, right-arm injury, and insufficient
   stamina, restores when conditions recover, and never consumes cost on
   rejection.

## Exit Criteria

This is the first minimal gameplay loop: materialize groups, settle an action,
append events, rebuild the facade, and emit a typed mirror delta. No inventory,
equipment, or economy is required for this exit.

## Evidence

`gameplay-state-groups`, `gameplay-resource-body`, `gameplay-status-tags`, and
`gameplay-effective-stats`. The current profiles are
backend-only and does not prove full replay/checkpoint equivalence, effective
stat source lifecycle beyond active tags, or Godot mirror delivery.
