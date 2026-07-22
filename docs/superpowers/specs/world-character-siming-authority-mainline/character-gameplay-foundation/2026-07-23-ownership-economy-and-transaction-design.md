# Ownership, Economy And Transaction Design

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

定义产权、账户、固定条件交易、债务与合同记录的实现级基础原语，使购买、赠与、产权转移和偿付都能由 backend authority 以完整事件溯源和跨 aggregate 原子批次结算。

本规格固定“实体物与产权分离”：物品、土地或世界资产是被指向的实体；`OwnershipRight` 是独立权威事实；地契、收据、钥匙或合同文书只是实体凭证/访问媒介。地契丢失、移动或毁损不得消灭土地产权，也不得自动转移产权。

首批经济只提供交易、物权、账户、债务和合同原语，足以支持确定性参考玩法；不实现动态市场、价格发现或宏观经济模拟。

## Scope

- ownable asset identity 与 `OwnershipRight`；
- title/credential item 与产权事实的关联；
- currency account、ledger entry 与 economic transaction record；
- 固定报价购买、赠与和显式产权转移；
- `DebtClaim`、`ContractRecord`、偿付与终止；
- inventory/custody 与 ownership 的跨域原子 settlement；
- 权限、幂等、optimistic concurrency、审计和 privacy；
- economy/ownership projection、解释查询和 Godot 可见裁剪。

## Non-goals

- 不做动态市场、订单簿、拍卖、供需定价、通胀或 NPC 宏观经济；
- 不做银行利息、复杂税制、信用评分、破产、法院和自动强制执行；
- 不把所有权等同于物品位置、实际占有、装备状态或控制权限；
- 不允许仅凭持有地契或钥匙推导产权；
- 不实现任意脚本合同或自然语言合同执行器；
- 不规定现实世界法律模型；
- 不让 Godot 本地余额、商店 UI 或预测结果成为交易真相。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-inventory-container-and-encumbrance-design.md`
- `2026-07-23-relationship-graph-boundaries-design.md`
- `2026-07-23-godot-runtime-mirror-and-prediction-design.md`
- `2026-07-23-persistence-replay-migration-and-hot-reload-design.md`
- `../2026-06-29-authority-and-settlement-runtime-closure-design.md`

本域拥有 right/account/debt/contract/transaction stream。inventory 域拥有 item placement 与 custody；world 域拥有 land/world asset lifecycle；relationship graph 只能投影公开或授权的客观关系摘要，不能修改债务金额或产权。

## Domain Model And Interfaces

### Ownable asset and ownership right

```text
OwnableAssetRef
  asset_type: item | land | building | account_share | contract_right | other_registered
  asset_id

OwnershipRight
  right_id
  asset_ref
  holder_ref
  share: rational(0, 1]
  right_kind: full_title | beneficial | lien | leasehold | licensed
  transfer_policy_ref
  encumbrance_refs[]
  valid_from
  valid_until?
  status: active | suspended | terminated
  source_ref
  revision
```

首批普通 item 和 land 使用 `full_title`、单一 holder、share=1。模型保留 share/right kind 字段但不要求首批支持复杂共有或优先级冲突；未启用的组合必须 fail closed。

### Credential and deed link

```text
CredentialLink
  credential_item_ref
  referenced_right_ref
  credential_kind: deed | receipt | certificate | key | contract_document
  proves: evidence_only | access_only | evidence_and_access
  issuer_ref
  issued_by_event_ref
  status: active | revoked | superseded
```

`CredentialLink` 是 right 的可验证引用，不是 right 本身：

- 地契 item 的 placement、custody、owner 可以与 land right holder 不同；
- 地契丢失、被盗、焚毁或转入容器只改变 item/credential 相关事实；
- land right 仅由 `ownership.transfer_right`、受信任迁移或明确 authority correction 改变；
- 补发地契会 supersede/revoke 旧 credential link，不重建或复制土地 right；
- 若 policy 要求呈示地契才能发起某命令，地契只是 precondition evidence，不能代替 holder authorization。

### Account and ledger

```text
CurrencyDefinition
  currency_id
  precision
  min_transfer_unit
  issuer_ref
  source_ref

Account
  account_id
  owner_ref
  currency_ref
  account_policy_ref
  status: active | frozen | closed
  credit_limit: 0 by default
  revision

LedgerEntry
  entry_id
  account_ref
  direction: debit | credit
  amount
  counterparty_account_ref?
  transaction_ref
  source_ref
```

balance 是 ledger events 的投影，不是可被 UI 或玩法脚本直接赋值的字段。amount 必须是 currency precision 下的正数；正负由 direction 表达。首批账户 credit_limit 为 0，除非明确启用另一 policy。

### Economic transaction

```text
EconomicTransaction
  transaction_record_id
  authority_transaction_id
  transaction_kind: purchase | gift | title_transfer | debt_issue | debt_payment | correction
  parties[]
  consideration[]
  asset_refs[]
  right_refs[]
  contract_ref?
  status: committed | reversed_by_event
  source_ref
  occurred_at
```

record 是已提交事实的审计聚合，不是预结算 intent。反向修正通过新 transaction/event 引用原 record，不能删除或把旧 status 就地改成未发生。

### Debt and contract primitives

```text
ContractRecord
  contract_id
  contract_type: simple_transfer | simple_debt | simple_service
  parties[]
  terms_ref
  effective_at
  due_at?
  status: proposed | active | fulfilled | terminated | breached_recorded
  authority_policy_ref
  source_refs[]
  revision

DebtClaim
  debt_id
  contract_ref
  creditor_ref
  debtor_ref
  currency_ref
  principal_amount
  outstanding_amount
  due_at?
  status: active | satisfied | cancelled_by_event
  source_ref
  revision
```

首批 `terms_ref` 只能引用注册的 typed terms schema，不能执行任意代码。偿付只减少 `outstanding_amount` 投影；每次减少必须由 account entries 与 debt payment event 同批支持。`outstanding_amount=0` 时产生 satisfied event。取消债务需要有权限的独立 command，并保留取消原因。

### Offers and fixed pricing

```text
FixedOffer
  offer_id
  seller_ref
  offered_asset_ref
  offered_right_ref
  price:
    currency_ref
    amount
  destination_policy_ref
  valid_from
  expires_at?
  max_fills
  source_ref
  revision
```

首批购买只消费 authority 注册的固定报价。offer 是确定性结算输入，不根据并发 demand、历史销量或客户端展示动态变价。报价失效或 revision 改变时返回冲突/过期，后端不能静默采用新价格。

### Query and proposal interfaces

```text
get_rights(asset_ref, principal_ref, at_revision?) -> OwnershipRightView[]
is_right_holder(subject_ref, asset_ref, right_kind, at_revision?) -> Decision
get_account_balance(account_ref, at_revision?) -> BalanceView
get_transaction(record_ref, principal_ref) -> TransactionView
get_debt(debt_ref, principal_ref, at_revision?) -> DebtView
get_contract(contract_ref, principal_ref, at_revision?) -> ContractView
resolve_credential(credential_item_ref, principal_ref) -> CredentialDecision
explain_ownership(right_ref) -> OwnershipExplanation
explain_transaction(record_ref) -> TransactionExplanation

propose_economy_effect(command, pinned_context) -> EconomyEffectProposal
validate_economy_proposal(proposal, pinned_context) -> ValidationResult
apply_economy_event(state, event) -> state
```

所有 query 受 privacy scope 约束。公开可观察的 item holder 不等于可读取其账户余额或私人债务。

## Commands And Event Flows

### Commands

```text
economy.purchase_fixed_offer
economy.transfer_funds
economy.gift_asset
ownership.transfer_right
ownership.issue_credential
ownership.revoke_credential
economy.create_contract
economy.issue_debt
economy.pay_debt
economy.cancel_debt_by_policy
economy.reverse_transaction_by_policy
```

每条写命令必须携带所有可能写入 aggregate 的 expected revisions。购买至少固定 offer、buyer account、seller account、asset/right、source/destination container revisions；不允许 handler 在 pipeline 中途发现遗漏后直接补写另一 stream。

### Fixed-offer purchase

```text
1. 校验 principal、buyer 授权、idempotency 和 expected revisions
2. 固定 offer/policy/registry revisions
3. 验证 offer active、价格与 command 中 accepted_price 完全匹配
4. 验证 seller 是可转让 right holder，asset 未被禁止转让
5. 验证 buyer balance、seller account、currency 与 precision
6. 请求 inventory 域验证 destination capacity、custody 和 placement
7. 形成完整跨域 candidate batch
8. authority settlement compare revisions 并原子 append
9. transaction-boundary projector 更新 balance/right/inventory/Godot views
```

典型成功批次：

```text
economy.account_debited                  # buyer
economy.account_credited                 # seller
inventory.item_removed_from_container
inventory.item_placed_in_container
inventory.custody_changed
ownership.right_transferred
economy.fixed_offer_consumed
economy.transaction_recorded
```

如果商品来自未实例化库存，允许同批使用 `inventory.item_created`，但 item ID 必须在 candidate batch 中确定且重复请求仍返回同一 ID。余额不足、offer 过期、产权受限、目标容器满或任一 revision 冲突均零提交。

### Gift and independent title transfer

`economy.gift_asset` 可以在同一原子批次转移普通 item 的 placement/custody/right，并记录零对价 transaction。`ownership.transfer_right` 是独立 authority transaction，可只转移 land right 而不移动地契 item；若 policy 要求同时交付凭证，则 credential item move 是同一批次的显式附加事件，而不是产权转移的隐式副作用。

下列命令不是产权转移：

- `inventory.move_item`；
- `inventory.pick_up_item`；
- `equipment.equip_item`；
- Godot 将地契节点移动到另一角色附近；
- credential item 被销毁或无法定位。

### Debt creation and payment

债务创建流程：

```text
create/activate ContractRecord
-> create DebtClaim with principal == outstanding
-> optionally transfer principal funds/assets
-> record EconomicTransaction
```

若债务发行包含资金交付，合同、债权、账户 entries 和 transaction record 必须同批提交。单次偿付批次至少包含：

```text
economy.account_debited                  # debtor
economy.account_credited                 # creditor
economy.debt_payment_applied
economy.debt_satisfied?                  # remaining == 0
economy.contract_fulfilled?              # terms fulfilled
economy.transaction_recorded
```

超额偿付首批固定拒绝，不自动退款或创建负 outstanding。部分偿付允许，但 amount 必须大于零且不超过 pinned outstanding。

## Authority Invariants

1. ownership、account、transaction、debt 和 contract 的权威状态只能由 immutable event stream 重放得到。
2. ownable entity 与 `OwnershipRight` 是不同 aggregate；placement/custody/control 也不等于 ownership。
3. 地契或其他 credential 的丢失、移动、盗取、禁用和销毁都不能消灭或转移被引用的 right。
4. 产权转移必须由独立、授权、可审计的 authority transaction 完成。
5. 所有转账必须产生等额、同币种、同 authority transaction 的 debit/credit entries；非交易性发行/销毁必须使用单独 issuer command/event。
6. 一个账户余额不能低于其 pinned credit limit；首批默认不得透支。
7. purchase/gift/debt payment 涉及的账户、产权、库存和 transaction events 必须同批全提交或零提交。
8. transaction record 必须引用实际 committed event batch，不可先记录成功再异步结算。
9. `outstanding_amount` 只能由 debt issue/payment/cancel/correction events 推导，不可直接赋值。
10. 同一 asset 的互斥 full title 在同一有效期内最多一个 active holder；未启用共有时 share 总和必须为 1。
11. 固定报价按 pinned offer revision 与 accepted price 结算；服务端不得静默替换价格。
12. Godot、本地预测、关系 belief 和持有凭证都不能创建经济或产权真相。
13. 敏感 balance、contract terms 和 debt 只能进入授权 projection；审计 trace 也必须按 privacy scope 脱敏。
14. 修正和撤销通过新事件引用原交易，绝不删除历史 ledger/right/debt event。

## Failure Semantics

所有失败使用统一 `SettlementFailure`，并给出稳定 `error_code`、失败 stage、相关 revision 和安全的 recovery action。

| Error code | Failed precondition | Commit | Recovery |
| --- | --- | --- | --- |
| `economy_offer_not_found` | offer 不存在或不可见 | none | 刷新商品视图 |
| `economy_offer_expired` | offer 已过期/耗尽 | none | 获取新 offer 后以新命令提交 |
| `economy_price_changed` | accepted price 与 pinned offer 不同 | none | 向用户展示新价格并重新确认 |
| `economy_currency_mismatch` | account/price currency 不一致 | none | 使用匹配账户 |
| `economy_amount_invalid` | 非正数、精度非法或超额偿付 | none | 修正 amount |
| `economy_insufficient_funds` | 可用余额不足 | none | 降低金额或补充资金 |
| `economy_account_frozen` | debit/credit policy 拒绝 | none | 按账户 policy 恢复 |
| `ownership_right_missing` | seller/transferor 无 active right | none | 刷新 right 或修正主体 |
| `ownership_transfer_forbidden` | lien/policy/authority 阻断 | none | 解除限制或走授权流程 |
| `ownership_credential_invalid` | 所需凭证无效/已 supersede | none | 使用有效 credential；不改变 right |
| `economy_contract_invalid` | terms schema、签署方或生效条件非法 | none | 修正 typed terms/授权 |
| `economy_debt_not_active` | debt 已满足/取消或不可见 | none | 刷新 debt view |
| `economy_payment_exceeds_outstanding` | payment 大于 pinned outstanding | none | 使用不超过 outstanding 的 amount |
| `inventory_destination_rejected` | placement/capacity/control 失败 | none | 修正目标容器/权限 |
| `revision_conflict` | 任一相关 stream 变化 | none | 刷新完整 transaction context 后重提 |
| `atomic_append_failed` | commit 未确认 | none/unknown | 用原 idempotency key 查询，不得新 key 盲重试 |

规则：

- 所有业务前置条件失败均不产生账户、产权、库存、合同或 transaction event；
- 原子 append 故障不得出现“已扣款但未交付”“已交付但未转权”或“已偿付但 debt 未减少”；
- commit status unknown 时查询原 command/idempotency outcome，不能创建第二笔交易；
- projection 失败保留 committed ledger/right events，通过 checkpoint 或完整 replay 恢复；
- Godot delta 丢失不重提 purchase/payment，只请求 transaction result 或 snapshot；
- authorization failure 的 details 不泄漏余额、债务、隐藏 owner 或合同条款。

## Acceptance Criteria

1. 从空事件流重放可重建账户、ledger、right、credential、transaction、contract 和 debt 状态。
2. 固定报价购买成功时 buyer/seller balance、item placement/custody、ownership right、offer fill 和 transaction record 同批提交。
3. 在 batch 第一个、中间、最后 event 注入写入故障，均证明零部分提交或以原 transaction 查询到完整提交。
4. 余额不足、价格变化、offer 过期、产权受限、容器满和 revision conflict 都返回结构化失败且 event count 不变。
5. 同一 idempotency key 重试 purchase/gift/payment 返回原 transaction ID，不重复扣款或转权。
6. item 被拾取、偷走、装备或放入他人容器不会隐式改变 ownership right。
7. land deed 丢失、销毁或被他人持有后，土地 right holder 和 right revision 不变。
8. `ownership.transfer_right` 能在不移动 deed item 的情况下原子改变 land right，并保留完整来源解释。
9. 补发地契只新增/supersede credential link，不复制土地 right。
10. 每笔普通转账的 debit/credit 金额和币种守恒，replay 后 balance 与在线 projection 一致。
11. debt issue、部分偿付、完全偿付能确定性重放；超额偿付零提交且 outstanding 永不为负。
12. 若债务发行含本金交付，则资金、contract、debt 和 transaction record 同批提交。
13. 未授权 actor 不能读取他人余额或私人债务；Godot projection 只含批准字段。
14. property tests 覆盖随机转账/赠与/偿付序列的资产守恒、title exclusivity、幂等和 replay determinism。
15. 首批实现不包含 demand-based pricing、订单簿、自动利息或市场 tick；scope test/manifest 能证明这些 capability 未启用。

## Harness Mapping

### Current review gate

- `python scripts/verification/harness.py --profile docs`

### Required implementation profiles

- `gameplay-foundation-contract`
  - right/account/ledger/offer/transaction/debt/contract/credential schemas；
  - version、precision、privacy 与 failure contract。
- `gameplay-event-replay`
  - balance、outstanding、title exclusivity、credential link 和 correction replay；
  - checkpoint 与完整 replay canonical diff。
- `gameplay-economy-authority`
  - 固定报价 purchase、gift、独立 title transfer、debt issue/payment；
  - 原子批次 fault injection、并发 revision、幂等和隐私拒绝。
- `gameplay-possession-equipment`
  - placement/custody/control 与 ownership right 的分离。
- `godot-gameplay-mirror`
  - pending purchase 表现不得成为 confirmed truth；result lookup 与 snapshot 收敛。
- `adventure-basic`
  - 买剑、赠与、债务/合同、土地 right 与地契分离场景。
- `gameplay-foundation-all`

证据必须保留 command、pinned revisions、完整 committed event batch、ledger/right/debt projections、结构化失败以及 online/full replay/checkpoint 三方比较；只验证最终余额不满足审计要求。
