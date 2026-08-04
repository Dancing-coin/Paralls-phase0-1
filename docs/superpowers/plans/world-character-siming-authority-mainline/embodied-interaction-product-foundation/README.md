# Embodied Interaction Product Foundation Plan Tree

Status: `execution-active-for-foundation-slices`

Date: `2026-07-29`

This plan tree advances the matching embodied-interaction specification through
focused, evidence-backed foundation slices. Registry, controller, authority
settlement, replay, interaction-session, carry/handoff, and action-asset
selection already have limited implementation evidence. It intentionally
excludes TTS, streamed dialogue, visemes, and broad presentation-content work.

It authorizes continued work only within reviewed contracts: local controllers
do not settle authority, VLA remains `fast-only` advisory with deep parked and
non-blocking, and root motion never owns world-space truth. Wave 1 has one
Godot-runtime-verified `obj_letter` and `obj_plaque` authority-owned
`inspect/read` fixtures, plus the authority-gated `obj_lamp_switch` `press`
fixture with `switch: idle -> activated` evidence, and the stateful
`obj_archive_door` `open_close` fixture with `door: closed -> open -> closed`
and state-constraint evidence. `obj_worktable` adds the stateful single-actor
`use` / `finish_use` fixture with `work_surface: ready -> engaged -> ready`.
`obj_observation_bench` adds actor-scoped `sit` / `stand`, owner-only release,
and posture-result evidence. Door occupancy, seated animation, shared
seat/table occupancy, and physical animation remain planned. `obj_archive_token`
adds the first backend-resolved, custody-only `grab` reference: no client world
refs are accepted and presentation changes only after the carry/place authority
event. It does not close inventory, ownership, hand attachment, or generic
pickup/place semantics. The next custody-to-inventory reference is a restricted
backend `stow_intent`: it resolves item and backpack server-side, atomically
commits custody/location/evidence, and gives Godot only an accepted authority
presentation marker. It is not a general inventory UI or stow flow. Its
reviewed `obj_archive_storage_chest` `retrieve_to_custody` inverse now has
default-scene transport with server-resolved source container and receiver;
Godot receives only the accepted authority result. It does not authorize a
generic container family, client-selected receiver, or broad transport policy.
Every further family still needs stable bindings, an authority policy, and
visible success/constraint evidence.

## Plan Order

1. [Implementation plan](2026-07-29-embodied-interaction-product-foundation-implementation-plan.md)
2. [Atomic action library and default scene coverage](2026-08-01-atomic-action-library-and-default-scene-coverage-plan.md)
3. [obj_archive_door physical embodiment vertical slice](2026-08-04-obj-archive-door-physical-embodiment-vertical-slice-plan.md)

The plan's phases are sequential at their contract boundaries. Within a phase,
backend tests and isolated Godot asset/controller work may be parallelized only
after their shared schemas are frozen.
