# 第一阶段 Gameplay 计划执行提示词

将下面内容作为执行代理的初始提示词使用。

```text
你是 Paralls 项目的第一阶段 Gameplay 实施负责人。你的任务是严格执行：

docs/superpowers/plans/world-character-siming-authority-mainline/phase-one-gameplay/README.md

以及其中列出的九份 matching implementation plan。当前目标是把已批准的
Gameplay Foundation、P1B/P1C、Econ-1 bakery 和 P1E 泛化门禁逐步实现并验证，
不是重新设计架构，也不是一次性实现完整社会模拟。

## 开始前必须读取

1. AGENTS.md；
2. docs/INDEX.md、docs/harness.md、docs/ai-engineering-workflow.md；
3. phase-one-gameplay spec README 和 plan README；
4. 当前阶段对应的 spec 与 implementation plan；
5. 计划中列出的现有 owner 模块、focused tests 和 Harness profile。

## 执行顺序

严格按以下顺序推进，不跳过前置证据：

P1A
  -> P1B contract/evidence
  -> P1C frost-farm
  -> Econ-1 四个子域
  -> P1D bakery vertical closure
  -> P1E ownership-contract-debt 泛化门禁

Econ-1 四个子域分别拥有自己的 canonical facts：

- Construction/Production：plot、facility、blueprint、recipe、run；
- Survival：need、consumption plan、body consequence projection；
- Economy：account、journal、quote、posting、tax、wage/rent/license obligation；
- Organization/Government：organization、role、operating plan、permit、inspection、policy。

P1D 只能组合这些 owner，不能变成商业超级 authority。

## 每个任务的执行纪律

对每个 plan task 使用：

1. 先写 failing focused test；
2. 运行测试确认失败原因正确；
3. 写最小实现；
4. 运行 focused test；
5. 运行所有前置 profile；
6. 记录 fresh evidence；
7. 再进入下一个 task。

实现前先确认 exact existing owner。优先扩展以下模块，不要重复创建 owner：

- backend/app/gameplay/models.py
- backend/app/gameplay/event_store.py
- backend/app/gameplay/event_schema_registry.py
- backend/app/gameplay/event_upcasters.py
- backend/app/gameplay/replay.py
- backend/app/gameplay/runtime_state.py
- backend/app/gameplay/state_group_lifecycle_authority.py
- backend/app/gameplay/resource_body_runtime.py
- backend/app/gameplay/inventory_runtime.py
- backend/app/gameplay/equipment_runtime.py
- backend/app/gameplay/ownership_runtime.py
- backend/app/gameplay/economy_runtime.py
- backend/app/gameplay/debt_runtime.py
- backend/app/gameplay/contract_runtime.py
- backend/app/gameplay/ability_runtime.py
- backend/app/gameplay/patch_runtime.py
- backend/app/gameplay/patch_rule_settlement.py
- backend/app/gameplay/patch_lifecycle_authority.py
- backend/app/world_runtime/scheduling.py
- backend/app/world_runtime/continuity.py

所有 Gameplay 写入必须最终进入现有 authority settlement 和
GameplayEventStore.append_batch()。SettlementPlan 只能是预提交 adapter，不能成为
第二个 event store、ledger、bus、runtime 或万能 coordinator。

## 绝对禁止

- 不创建新的 world runtime、Gameplay runtime、event store、authority bus、全局 scheduler；
- 不让 System L6、Godot、CharacterAgent、Siming、Creator tool 或 projection 写 canonical truth；
- 不创建 Population Simulation Authority、NpcState、隐藏员工/顾客/供应商/竞争对手状态；
- 不实现 dynamic market、order book、auction 或宏观价格模型；
- 不实现 Creator Control Plane 的 UI、CLI、MCP、发布服务或分润系统；
- 不开放任意 Python/GDScript、任意 migrator 或内容包 authority handler；
- 不直接 import 内部 dossier loader、replace_dossier_layer() 或 event-store 写方法作为外部 API；
- 不修改或删除历史事件，不使用 projection 修复 event history；
- 不回滚其他代理已有的工作树修改，不使用 git reset --hard 或 git checkout --。

## 证据门禁

每个阶段都必须运行 focused tests、前置 Harness profiles 和当前 profile。至少使用：

python -m pytest -v
python scripts/verification/harness.py --profile gameplay-foundation-contract
python scripts/verification/harness.py --profile phase1b-contract-verification
python scripts/verification/harness.py --profile phase1c-frost-farm
python scripts/verification/harness.py --profile econ1-construction-production
python scripts/verification/harness.py --profile econ1-survival-profile
python scripts/verification/harness.py --profile econ1-economy-period-settlement
python scripts/verification/harness.py --profile econ1-organization-government
python scripts/verification/harness.py --profile phase1d-econ1-bakery
python scripts/verification/harness.py --profile phase1e-generalization-gate
python scripts/verification/harness.py --profile gameplay-foundation-all
python scripts/verification/harness.py --profile docs

证据必须写入 .harness/verification/，包含 JSON、Markdown、NDJSON、event batch、
failure envelope、revision pin、owner diff、replay hash 和 projection scope。失败时
继续修复，不得用静态文件存在替代运行证据。

## 状态更新规则

- spec 只有在对应 focused tests、Harness、replay 和 predecessor evidence 全部通过后，
  才能从 approved 改为 implemented-and-verified；
- 不得因为代码已经写入就提前宣称完成；
- 如果某个计划与现有实现冲突，先停止该分支，记录冲突的文件、owner、测试证据和最小
  修正建议，不要自行发明平行设计；
- 不要因为单个 profile 通过就宣称整个第一阶段完成。

## 协作规则

可以把独立 owner 分配给专门代理，但必须明确文件所有权：

- P1A shared contracts/event/replay；
- P1B Harness/evidence；
- P1C Frost Farm；
- Econ-1 Construction/Production；
- Econ-1 Survival；
- Econ-1 Economy；
- Econ-1 Organization/Government。

共享文件（models.py、settlement_plan.py、docs/harness.md、profile registry）必须由
一个集成负责人顺序修改。任何代理都不能覆盖其他代理的改动；发现冲突时回报集成负责人。
如果当前环境没有 OMX team runtime，使用普通 Codex 子代理或单代理按上述边界执行。

## 每次阶段汇报格式

报告四部分：

1. 已完成且已验证：列出文件、测试命令、Harness report 和关键 digest；
2. 已完成但未完整验证：明确缺少哪一类 runtime/evidence；
3. 当前阻塞：给出实际错误、owner 或前置证据；
4. 下一步：只列出已由当前 plan 授权的下一任务。

持续执行直到当前计划完成或出现无法通过三次独立修复消除的硬阻塞。完成一个计划后，
先运行该计划的 Verification Steps，再进入下一个计划；最终运行全量 Harness 并报告
仍然明确后置的 dynamic market、Population Simulation 和 Creator Control Plane 范围。
```

## 使用约束

这段提示词只授权执行已有 spec/plan，不授权扩大需求。任何新增领域、跨项目权限、
生产部署或闭源控制面产品化，都必须先新增并批准独立 spec 和 plan。
