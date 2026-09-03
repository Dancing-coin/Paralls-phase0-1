# Organization Membership, Roster And Role State

Status: `implementation-authorized`

Date: `2026-09-03`

Organization owns membership, roster and role state for admitted actors only.
The state machine is `proposed -> admitted -> active -> suspended -> revoked ->
archived`. Population profiles are only inputs to explicit materialization.

`GameplayPatchManifest v3` / `platform_schema_version="2.0"` content is
strict, exact, owner-bound and precompiled. Membership writes use
`gameplay.organization.membership`; unknown, stale, duplicate or foreign-owner
claims zero-write. No employee shadow state, generic HR writer or roster
coordinator is introduced.

