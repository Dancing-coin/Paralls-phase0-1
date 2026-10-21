# Equipment Runtime Plan

Status: `execution-active-for-minimum-authority-core`

## Dependencies

Inventory/container/encumbrance, effective stats, and state-group facade.

## Current Minimum Slice

The first backend-only authority slice is implemented and verified. It records
an item placement transition in `gameplay:inventory:<actor>` and the matching
slot activation lifecycle in `gameplay:equipment:<actor>` and each
activation-scoped ability-path grant lifecycle in `gameplay:abilities:<actor>`,
and registered modifier-source lifecycle in `gameplay:modifiers:<actor>`
through one `GameplayEventStore.append_batch()` call. It validates source
placement, slot compatibility and exclusivity across every occupied slot,
body-function availability, source revisions, and idempotency before commit; a
rejected precondition writes no event. A multi-slot activation records every
occupied slot under one activation and cannot partially occupy its primary slot.
The minimum `swap` path is also implemented: it validates the outgoing
destination and every incoming slot, then revokes the old activation effects,
restores the outgoing item, and activates the incoming item in one batch.

This does not implement learned-skill promotion, generic modifier-authoring or
non-equipment modifier sources, container-access or propagation grants,
ownership/control policy, presentation bindings,
persistent replay/checkpoint proof, equipment-aware affordance settlement, or
Godot delivery.

## Work

1. Define slot schemas, item compatibility, exclusive/overlay policies, grant
   sources, equip/unequip commands, and staged inventory moves.
2. Implement atomic equip/unequip event batches, reversible grant activation,
   modifier/source explanations, and safe non-empty container policy.
3. Publish typed presentation binding references through the future gameplay
   mirror; presentation attachment never proves equipment truth.
4. Test incompatible slot, bound item, stale revision, grant removal, and
   storage-ring `reject_non_empty` behavior. The first focused tests now cover
   the incompatible-slot, unavailable-body, idempotency, multi-slot, and
   atomic equip/unequip/swap core; remaining cases stay pending.

## Exit Criteria

Unequipping either succeeds atomically or leaves item location, grants,
modifiers, and presentation references unchanged.

## Stage3 T09 production prediction ingress plan

依照 Equipment 设计新增 T09 准入合同，本次在已有基础上实施：
1. 用真实 activation/presence/inventory/Equipment owners 建立 focused allowlist RED：preview 不写领域，Durable close/reopen，changed duplicate、scope、撤权、operational expiry、CAS、owner/confirmation 丢响应。
2. 新增 `backend/app/services/equipment_prediction_service.py`，复用 `EquipmentCommandService`、`PredictionAuthority` 和共享 store；仅作 typed caller，不新增账本或身份 issuer。
3. `prediction_authority.py` 最小可选 expires_at 兼容扩展；历史 payload 不加 null 字段，不改写历史 receipt。生产装配由 main lane 完成。
4. GREEN allowlist `backend/tests/test_equipment_prediction_service.py` 加既有 `test_equipment_command_service.py`；不收集带 CalibrationInput 的 branch preview tests，不运行 Godot。主线程追加 fresh Harness。
