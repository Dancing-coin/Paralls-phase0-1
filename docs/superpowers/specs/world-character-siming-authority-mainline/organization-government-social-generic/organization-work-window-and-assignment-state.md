# Organization Work Windows And Assignment State

Status: `implementation-authorized`

Date: `2026-09-03`

Organization owns work windows, assignments and completion state only. The
state machine is `planned -> open -> assigned -> started -> completed/failed
-> closed`. Windows are explicit and revision-pinned; they are not a global
clock or scheduler.

Work writes use `gameplay.organization.work` and are assembled from
precompiled owner recipes. All cross-owner dependencies remain owned by their
source domains. No payroll, generic task router, or hidden worker lifecycle is
created.

