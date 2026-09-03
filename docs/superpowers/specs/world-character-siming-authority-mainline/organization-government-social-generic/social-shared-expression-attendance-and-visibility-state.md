# Social Shared-Expression, Attendance And Visibility State

Status: `implementation-authorized`

Date: `2026-09-03`

SocialFactAuthority owns shared-expression, attendance and visibility state.
The state machine is `invited -> joined -> observed -> left -> redacted`.
Visibility revocation must preserve replay and privacy boundaries.

Writes use `gameplay.social.shared_expression`. The family is recipe-bound and
does not create a second session runtime, generic chat writer, or attendance
coordinator.

