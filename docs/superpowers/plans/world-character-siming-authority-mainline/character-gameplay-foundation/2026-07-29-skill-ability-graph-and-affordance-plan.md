# Skill Ability Graph And Affordance Plan

Status: `minimum-core-implemented; broader-graph-planned`

## Dependencies

State-group facade and resource/status/body. Equipment, inventory, ownership,
and world/relationship policy feed later affordance predicates as available.

## 2026-08-02 Implementation Status

The first backend-only core is implemented and verified by
`gameplay-ability-affordance`: a small definition registry, event-derived
learned skill/grant projection, and body/resource affordance query. The slice
does not authorize promotion, equipment/inventory predicates, transport, or
Godot delivery. Existing `character_agent/skills/` remains advisory; no model
or evaluator writes stable ability state.

## Work

1. Preserve `character_agent/skills/` as a source adapter and migrate only its
   approved definitions/seeds into a new `core.skills` gameplay state group.
2. Implement versioned graph nodes/edges for learned/granted skills, actions,
   prerequisites, costs, evidence, and reversible equipment grants.
3. Implement a separate current-affordance projection that joins stable graph
   knowledge with body, resource, equipment, inventory, environment,
   relationship permission, and authority policy.
4. Feed a privacy-filtered summary back to CharacterAgent; L2/L3 may rank it,
   but only settlement may accept actions and consume costs.

## Exit Criteria

Temporary injury or low stamina blocks an action while the learned ability
remains intact. A replayed projection explains every blocking predicate.
