# Econ-1 面包店商业生态与多角色经营实现方案

状态：`phase-one implementation guidance; population-simulation integration is post-foundation`

本文在 [模拟经营完整玩法与多智能体协作](../玩法系统/社会与制度玩法/03-模拟经营完整玩法与多智能体协作.md) 的
完整经营闭环之上，进一步定义一个相对完整的面包店商业生态：多个员工、顾客、供应商、
竞争对手、政府、房东/债权人和物流关系共同影响经营结果。

本文不是新的 runtime、event store、bus 或总 authority。它是领域组合设计：各主体仍
通过现有 `GameplayEventStore.append_batch`、领域 authority、outbox、replay 和过滤
projection 形成唯一事实链。

## 1. 设计结论

面包店商业生态分两步交付：

1. **基础经营版本**：单经营者 + 聚合顾客需求 + 固定供应商报价，先证明完整经营日闭环；
2. **商业生态版本**：群体模拟提出真实员工、顾客、供应商和竞争对手角色的
   materialization/activation proposal，由 Character/World owner 接入同一
   `CharacterRecord`，再通过组织记录和 typed intent 参与经营。

群体模拟当前尚未实现，因此第二步只能作为后续正式 spec/plan 的目标设计。不得用
   `NpcState`、seed fixture、隐藏脚本或直接写事件的方式提前伪造这些角色。

## 2. 运行配置与角色数量

| 配置 | 经营主体 | 员工/顾客/供应商/竞争对手 | 允许的完成声明 |
| --- | --- | --- | --- |
| `bakery-single-owner` | 1 个玩家角色或 1 个经营者 CharacterAgent | 0 个 NPC；顾客为聚合需求，供应商为固定 quote，竞争由市场参数表示 | 可完成单店经营闭环 |
| `bakery-authored-agents` | 1 个经营者 + 2-4 个已存在 CharacterRecord/CharacterAgent | 只能使用正式创建的角色；不代表人口模拟 | 可验证多智能体协作，不宣称 NPC 生态 |
| `bakery-population-ecosystem` | 组织经营者 + 群体模拟中的多个角色 | 员工、顾客、供应商、竞争对手和监管相关角色由 Population Simulation planner 提出 proposal，再由 Character/World owner 接入 | 才能宣称商业生态玩法 |

建议的商业生态参考包规模如下，数字属于内容包配置，不能写死到通用核心：

- 1 个店主；
- 3 个员工：烘焙师、柜台/销售、采购/维护；
- 3 个供应商：稳定低价、低价但不稳定、质量高但昂贵；
- 2 个竞争对手：低价大批量、精品高质量；
- 4 个顾客需求段：日常刚需、价格敏感、质量偏好、时段偏好；
- 1 个房东/物业组织；
- 1 个政府辖区与监管 authority；
- 1 个贷款/债权主体，可由组织或政府金融模块提供。

在群体模拟上线前，只启用第一种配置；第二种配置只用于已有角色的受控测试。

## 3. 商业生态主体

### 3.1 面包店组织

面包店是独立 `Organization`，拥有自己的：

- 账户和现金流；
- 原料、半成品和成品库存；
- 店面、烤炉、仓储等设施产权或租赁权；
- 员工职位和授权范围；
- 采购、生产、定价和营业计划；
- 工资、租金、税费、许可证和债务义务；
- 营业周期、声誉和经营目标。

店主角色拥有经营授权，但不等于拥有组织全部事实。组织 authority 负责岗位、预算、
经营计划和期末状态；账户、库存、设施和角色状态仍由各自 authority 维护。

### 3.2 员工

员工不是组织内部的一行余额，而是拥有独立角色状态的主体：

- 自己的技能、体力、疲劳、饥饿和可用时段；
- 个人账户、工资合同和可能的债务；
- 工作资格、排班、岗位授权和完成证据；
- 对组织的关系、信任、满意度和离职倾向。

员工行为流程：

```text
Population/Character plan
-> 接受或拒绝工作安排
-> 到岗/缺勤/迟到
-> 生产或销售 intent
-> Skill + Survival + Facility 校验
-> 生产证据 / 销售证据
-> 工资义务结算
-> 角色状态和组织关系更新
```

员工的技能和身体后果可以影响产量、质量、损耗和营业时间，但员工不能直接改组织
账户或生产进度。

### 3.3 顾客

顾客分两种运行形态：

- 基础经营版本使用 `CustomerDemandAggregate`，只表示分时段、分商品、分价格带的
  需求量，不创建顾客角色；
- 群体生态版本由 Population Simulation Authority 提供真实顾客 CharacterRecord，
  顾客拥有预算、需求、知识、偏好、家庭责任和声誉记忆。

真实顾客的购买过程：

```text
看到/听到报价的 perception
-> 依据预算、需求、价格、质量和信任形成 purchase intent
-> Economy + Inventory + MarketQuote 校验
-> 付款、取得商品、消费或转售
-> satisfaction / complaint / repeat-visit projection
```

顾客的个人消费不能由市场聚合器直接替代；聚合器只用于群体模拟尚未上线的基础版本。

### 3.4 供应商与物流

供应商可以是组织，也可以在群体模拟之后由真实角色代表。供应商提供：

- 材料类型、质量、交付周期和可供数量；
- 价格、最低订单量、付款条件和信用条件；
- 缺货、延迟、污染、损耗和替代材料风险；
- 交付、验收和争议证据。

供应链流程：

```text
面包店采购计划
-> supplier quote / contract
-> account hold 或付款条件
-> inventory reservation
-> logistics delivery obligation
-> 到货验收与质量/数量检查
-> 接收入库或生成争议/退款/债务
```

第一版本可使用固定供应商 quote 和确定性交付时间；供应商角色、运输者角色和讨价还价
属于群体模拟之后的扩展。

### 3.5 竞争对手

竞争对手是其他商业组织，不应直接读取面包店私有库存或内部计划。它们通过公开市场
和辖区投影产生竞争：

- 商品报价和营业时段；
- 商品质量、声誉和促销；
- 原料采购对市场库存的影响；
- 招聘竞争和工资水平；
- 抢占店面、供应商和顾客需求。

基础版本用两个参数化竞争者 profile 生成公开报价，不创建竞争对手 NPC。群体生态版本
再由 Population Simulation Authority 激活竞争者组织的经营者或管理角色。

竞争对手不能直接降低玩家库存、修改玩家声誉或操纵顾客状态；它只能提交自己的经营
intent，或通过市场/关系/政策 authority 产生可追踪的间接影响。

### 3.6 政府、房东与债权人

- 政府是辖区政策和监管 authority，不需要先创建一个监管 NPC；
- 房东是拥有物业权利、租赁合同和收租义务的组织或角色；
- 债权人是账户、债务和合同权利的主体；
- 检查员、房东代理和催收人员只有在群体模拟后才作为真实角色出现。

## 4. 核心数据模型

本节只定义商业生态所需的领域记录。角色、组织、设施、库存、账户和政策各自拥有
canonical stream，跨域只保存引用和 revision。

```text
Organization
  organization_id, subject_ref, kind, jurisdiction_ref, status

RoleAssignment
  assignment_id, organization_ref, character_ref, role_ref
  authority_scope, wage_policy_ref, schedule_ref, status

EmploymentContract
  contract_id, organization_ref, character_ref, role_ref
  wage, pay_period, expected_hours, leave_policy, status

ShiftPlan
  shift_id, organization_ref, character_ref, facility_ref
  start_tick, end_tick, work_order_refs, status

OperatingPlan
  organization_ref, period_ref, budget_ref, procurement_targets
  production_targets, pricing_policy_ref, staffing_targets, approval_refs

BusinessPeriod
  period_id, opening_tick, closing_tick, revenue, cost, payroll
  rent, tax, debt_due, inventory_value, reputation_delta, result

SupplierOffer
  offer_id, supplier_subject_ref, item_ref, lot_terms, price_terms
  delivery_terms, quality_terms, expires_at_tick, policy_revision

PurchaseOrder
  order_id, buyer_org_ref, supplier_ref, offer_ref, lot_reservation_refs
  payment_terms, delivery_obligation_ref, status

CustomerDemandAggregate
  aggregate_id, jurisdiction_ref, period_ref, item_ref, segment_ref
  requested_quantity, price_elasticity, quality_weight, time_window
  source_revision, demand_digest

CustomerIntent
  intent_id, customer_character_ref, item_ref, quantity, accepted_quote_ref
  budget_projection_ref, knowledge_refs, status

CompetitorOperatingProfile
  organization_ref, product_mix, quality_band, price_policy_ref
  opening_hours, staffing_policy_ref, public_offer_revision

MarketQuote
  quote_ref, issuer_ref, item_ref, side, unit_price, quantity_limit
  tax_policy_ref, valid_from_tick, valid_until_tick, source_digest

Permit
  permit_id, holder_org_ref, jurisdiction_ref, scope, effective_revision
  expires_at_tick, inspection_policy_ref, status

TaxAssessment
  assessment_id, holder_org_ref, period_ref, tax_kind, taxable_base
  amount, due_tick, policy_revision, status
```

## 5. Authority 边界

| Authority | 拥有的事实 | 可以读取 | 不可以做 |
| --- | --- | --- | --- |
| Skill Authority | 技能等级、资格、完成证据 | 角色状态、工作项、配方要求 | 写工资、库存、设施 |
| Inventory Authority | item、lot、容器、数量、custody、预留 | 配方、生产 run、采购订单 | 写账户余额或顾客需求 |
| Construction/Production Authority | 地块、设施、配方、生产 run、质量、维护 | 技能、库存、组织排班、许可 | 写工资、税费、角色身体 |
| Survival Authority | 需求、消费计划、身体后果、劳动能力投影 | 角色状态、库存可用来源、价格投影 | 直接扣款或凭空生成食物 |
| Economy Authority | 账户、分录、hold、quote、工资、税务分录、债务义务 | 组织预算、订单、生产/销售证据、政策 | 写库存、设施或角色档案 |
| Contract/Debt Authority | 采购、租赁、雇佣、交付和借款合同及履约/违约状态 | 组织、账户、交付证据、政策 | 直接转移库存或改账户余额 |
| Organization Authority | 组织注册、岗位、排班、预算、经营计划、period close | 账户、库存、设施、角色资格、市场和政策 | 复制账户、库存、员工身体状态 |
| Government Authority | 辖区、许可、检查、政策 revision、税务评估 | 组织经营证据、公开市场、申诉证据 | 直接删除资产或改角色私有状态 |
| Population Simulation Authority | 后置：人口计划、角色激活 proposal、日程和批量 intent | 受授权的世界/家庭/组织 projection | 直接 materialize CharacterRecord，或写任何 Gameplay canonical fact |

没有一个“商业生态 coordinator”拥有全部状态。需要跨域时，只允许生成带有
`expected_revision_vector`、`causation_refs`、`policy_revision` 和
`idempotency_key` 的预提交计划，最后由各 owner 映射为事件并调用现有
`GameplayEventStore.append_batch`。

## 6. 经营周期与跨域结算

### 6.1 开店

```text
角色创建/接管组织
-> 账户、设施产权或租赁权、初始库存
-> 申请营业许可证
-> 政府检查/许可结果
-> 组织 operating plan 激活
```

许可证未生效时，生产可以处于试制状态，但营业销售必须被拒绝；拒绝不产生部分扣款。

### 6.2 采购和交付

```text
OperatingPlan procurement target
-> 选择 SupplierOffer
-> quote/contract/hold
-> inventory lot reservation
-> delivery obligation
-> 到货验收
-> 入库、付款、争议或退款
```

材料数量不足、质量不合格、报价过期、资金不足和交付超时都必须产生结构化结果。

### 6.3 排班和生产

```text
RoleAssignment + ShiftPlan
-> skill/body/survival availability
-> facility slot reservation
-> material/tool reservation
-> ProductionRun
-> finish obligation
-> consume inputs + create outputs + record quality
```

多员工争用同一个烤炉时，以 facility stream revision 和 slot reservation 决定成功者；
失败者得到 `facility_slot_conflict`，不能出现双重生产。

### 6.4 顾客和销售

基础版本：

```text
CustomerDemandAggregate
-> quote policy
-> inventory availability
-> sale intent
-> payment + tax posting
-> inventory transfer
-> demand satisfied / unsatisfied projection
```

群体模拟版本：

```text
Customer CharacterRecord
-> perception/knowledge/budget/need
-> purchase intent
-> same sale authority
-> consume / complain / return / repeat-visit evidence
```

真实顾客角色的预算和需求不能由面包店销售脚本直接写入。

### 6.5 工资、税费和关日

```text
completed work evidence
-> payroll calculation
-> wage posting / failed payment obligation
-> sales and property tax assessment
-> permit/rent/debt due items
-> organization period close
-> next-period operating plan
```

工资、税费、租金和债务是显式义务；停服恢复时按 catch-up policy 有界补算，不能
一次性无上限追赶所有 tick。

## 7. 员工与多智能体经营

### 7.1 员工状态

真实员工角色拥有独立的：

- 技能、身体资源、生存需求和疲劳；
- 工作合同、工资、班次和请假/缺勤；
- 个人账户、家庭义务、声誉和工作关系；
- 可见的组织政策、岗位目标和同事关系。

组织只能提交排班、工作项和预算约束；员工 CharacterAgent 或人口 planner 决定
接受、拒绝、迟到、换岗、辞职或提出谈判 intent。

### 7.2 工作结果

员工的“努力”不是结果。只有以下 authority evidence 才能结算工资：

- 到岗与有效工作时段；
- 技能检查和工具/设施使用；
- 生产产出、质量、服务订单或采购交付；
- 缺勤、损坏、投诉或违规记录。

工资结算不改变员工的技能和身体；这些由 Skill/Survival authority 根据工作证据更新。

### 7.3 群体模拟接入门

群体模拟完成前，员工只能是已存在并被明确授权的多智能体角色；不能为了填满“3 个
员工”而在面包店初始化时创建 NPC。Population Simulation Authority 上线后，才新增：

- 求职、招聘和职业迁移；
- 员工家庭预算、照护与通勤；
- 批量排班接受/拒绝、缺勤、跳槽和工资谈判；
- 组织之间的人才竞争和人口迁移。

## 8. 顾客、供应商与竞争对手生态

### 8.1 顾客需求段

基础版本可定义四类聚合需求段：日常刚需、价格敏感、质量偏好、时段偏好。每个
需求段只输出数量、价格弹性、质量权重和营业时段，不携带角色余额或私有记忆。

群体模拟后，这些段落成为角色生成和校准参数，不能继续替代真实顾客的 canonical
账户、家庭义务、知识和消费事件。

### 8.2 供应商生态

第一版提供三个固定供应商 profile：稳定低价、低价但易延迟、质量高但昂贵。它们是
公开 quote/交付规则，不是 NPC。群体模拟后才允许供应商经营者、销售人员和运输者
成为真实角色。

### 8.3 竞争对手生态

第一版提供两个竞争组织 profile：低价大批量和精品高质量。它们通过公开报价、质量、
营业时段和招聘策略影响市场参数；不直接修改玩家状态。

群体模拟后，竞争组织可以拥有真实经营者和员工，并提交采购、招聘、定价、促销、
扩张和退出 intent。竞争结果必须通过公开市场、劳动力市场或声誉投影产生。

## 9. 市场规则

第一阶段不做订单簿、拍卖和宏观金融，但要有可玩的市场闭环：

- 每日或每经营周期重新计算公开 quote；
- 价格受基础成本、库存覆盖、聚合需求、税费、质量和竞争 profile 影响；
- 报价固定 revision、有效时间、数量上限和解释摘要；
- 销售只能引用未过期 quote；
- 竞争对手和供应商只能通过自己的公开 offer 影响市场；
- 玩家看不到其他组织的私有预算、库存和角色心理。

群体模拟接入后，再把角色预算、家庭需求、知识不对称和关系信用接入 quote 选择，
不能由市场模块直接读取所有角色私有状态。

## 10. 政府与商业生态

政府不是一个需要先生成的监管 NPC，而是辖区和政策 authority。第一版至少提供：

- 营业许可证；
- 销售税；
- 租赁/营业区域规则；
- 一次卫生或设施检查；
- 罚款、整改或暂停营业结果。

检查员、房东代理和催收人员属于后置角色。没有这些角色也不影响政策 authority
先完成行政结算；角色化只改变互动和叙事，不改变政策事实的 owner。

## 11. 目标、风险与结果

### 玩家经营目标

- 三日内保持正现金流；
- 完成指定产量或订单；
- 达到声誉/质量阈值；
- 维持许可证和税费合规；
- 在生存模式开启时保持经营者可工作。

### 失败结果

- 现金耗尽；
- 工资、租金、税费或债务违约；
- 设施停摆或关键材料断供；
- 许可证吊销；
- 经营者生存后果导致无法继续工作。

失败只提交新的事实和义务，不删除历史；恢复可以通过减产、重新采购、借款、整改、
暂停营业或重新开始经营周期完成。

## 12. 实现路线

### E0：正式契约冻结

冻结 `Organization`、`RoleAssignment`、`ProductionRun`、`InventoryLot`、`MarketQuote`、
`CustomerDemandAggregate`、`Permit`、`TaxAssessment`、`BusinessPeriod` 的 schema、
owner、revision、visibility、失败码和事件目录。

### E1：单经营者完整游戏

只实现 `bakery-single-owner`：

- 1 个经营者角色；
- 店主亲自生产；
- 聚合顾客需求；
- 固定供应商 quote；
- 两个参数化竞争组织；
- 至少三个经营日；
- 真实的采购、库存消耗、生产、销售、税费、生存和失败恢复。

### E2：已有角色的多智能体协作

不引入群体模拟。使用正式存在的 2-4 个 CharacterRecord/CharacterAgent，验证店主、
烘焙师、采购员之间的排班、资源争用、工作证据和工资结算。

### E3：Population Simulation Authority 接入

这是独立后续阶段，必须先完成群体模拟正式 spec/plan 和 Harness，再接入：

- 员工求职、招聘、缺勤、跳槽和家庭义务；
- 顾客预算、消费、投诉、复购和口碑传播；
- 供应商经营、交付、信用和运输角色；
- 竞争对手经营者、员工、促销和退出；
- 监管人员、房东代理和债权人互动。

### E4：更完整商业生态

在 E3 之后才扩展订单簿、动态市场、跨区供应链、金融信用、公司制、破产和城市级
商业网络。

## 13. 完成门禁

- E1 不产生任何 NPC canonical state；
- E2 的每个角色都有正式 `CharacterRecord`、权限、可见 projection 和 typed intent；
- E3 前不得宣称员工/顾客/供应商/竞争对手已由群体模拟驱动；
- 所有采购、生产、销售、工资、税费、许可证、生存和竞争影响均可回放；
- 成功、拒绝、资金不足、材料不足、报价过期、排班冲突、税费违约和重复 tick 均可验证；
- 新领域只增加 schema、authority、projection 和 package，不新增 event store、bus、
  runtime、影子角色或绕过现有 `append_batch` 的写入口。
