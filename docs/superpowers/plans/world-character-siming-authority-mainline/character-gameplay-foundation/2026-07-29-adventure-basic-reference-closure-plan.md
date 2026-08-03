# Adventure-Basic Reference Closure Plan

Status: `partially-implemented; scenario-1-backend-verified; broader-closure-planned`

## Current Baseline

`assets/gameplay/adventure-basic/manifest.json` now provides a strict,
digest-checked governed package entry, and `adventure-basic` verifies that
entry before activation. Scenario 1 has an explicit backend-only seed and
composition over the existing fixed-offer and equipment authorities: it proves
the fixed-price sword purchase batch, the separate right-hand equipment batch,
projection updates, and insufficient-funds zero-write rejection. Patch
activation, replay, mirror, and Godot results are not complete.

## Dependencies

All preceding first-closure plans, including Rule IR/capabilities, persistence,
and Godot mirror work.

## Work

1. [~] Author and validate the `adventure-basic` manifest, seeds,
   item/container fixtures, fixed offers, actor/account fixtures, Godot
   bindings, and patch lifecycle fixtures. The manifest and the narrow
   Scenario 1 backend seeds are validated; Patch lifecycle, Godot bindings,
   and every other scenario fixture remain planned.
2. [~] Prove purchase/equip sword; injury and stamina rejection; storage ring
   encumbrance; land right versus deed; and gift/debt/contract lifecycle.
   Purchase/equip is backend-verified only; its replay/mirror/Godot closure,
   and all remaining scenarios, are still planned.
3. For each scenario retain command/result, event batch, revisions, rebuilt
   facade, mirror output, explanation trace, replay hash, and Godot evidence.
4. Implement and run all planned gameplay profiles and `gameplay-foundation-all`;
   then run the repository-wide `all` profile and update status documentation.

## Exit Criteria

Every scenario has an authoritative success or structured constraint result,
replays identically, and produces the specified observable Godot result. The
closure does not claim deferred cultivation, dynamic market, relationship graph,
or Siming knowledge graph implementation.
