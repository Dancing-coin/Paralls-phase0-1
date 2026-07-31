# Gameplay Patch Rule IR And Capabilities Plan

Status: `drafted-for-spec-review`

## Dependencies

Contracts/events, state groups, and at least the resource/body minimal slice.

## Work

1. Implement immutable patch manifests declaring group definitions, schemas,
   event versions, Rule IR, allowed capability names, migrations, bindings, and
   verification metadata.
2. Implement deterministic triggers, typed conditions, reservations/effects,
   modifier policy, budgets, proposal validation, and revision pinning.
3. Register trusted handlers behind the manifest; handlers return proposals and
   cannot write stores or invoke Godot directly.
4. Implement install/enable/disable/upgrade with dependency/conflict checks and
   replay fixtures.

## Exit Criteria

Invalid, circular, unauthorized, timed-out, or malformed patch behavior cannot
partially activate or mutate authoritative domain state.
