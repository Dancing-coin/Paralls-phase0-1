# Precompiled Owner Recipe Catalog And Settlement Bridge

Status: `implementation-authorized`

Date: `2026-09-03`

This family stores immutable recipe bindings for Organization, Government and
Social flows. The state machine is `registered -> pinned -> admitted ->
retired`. Recipes are precompiled and exact; callers do not invent owner
fragments or route selection.

The bridge only composes existing owners through `SettlementPlan ->
GameplayEventStore.append_batch()`. No generic router, writer, coordinator or
settlement authority is introduced.

