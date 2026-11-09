# G0 权威来源、现状与下游阶段门

- 核查日期：2026-11-09；运行时代码：`5321266dbd882f45eb6a24dd7b328e9f56746228`。
- 本记录补充带日期的证据，不改写 PRD、生产计划或历史验收结论。**G0 未通过，G1 未放行。**
- 本地真实仓库是 `D:/Users/User/Documents/paralls-phase-0-demo`。D11 所说“此路径不存在、真实路径 D:/Paralls-phase0-1”在本机已经反转；旧路径不可继续作为命令输入。

## 权威来源与冲突处置

| 来源 | 当前含义 | 本轮处置 / 对应门 |
|---|---|---|
| [PRD 入口](../../PRD/README.md:70) | 产品正式技术导航仍指向 v1 architecture | 保持正式产品范围。v2 不能以设计文档自行改写 Demo 验收 |
| [基础设施计划](../../production/基础设施与Owner建设总计划.md:11) | 23 Owner 唯一注册表与完整交付包仍依 v1；A2 冻结写权，A5 冻结 UE 部署节奏 | G3 注册前逐条对照 v2 native/stewarded 与字段写权；G5 前批准部署/提交合同 |
| [县城执行计划](../../production/县城守城Demo执行计划.md:87) | 要求全部 23 Owner 正式 Authority/完整包 | v2 把部分交付降为托管声明，属于交付组织差异。G3/G4 证明等价交付并经生产计划裁决后才能更新完成标记 |
| [v1/v2 对照](../00-总纲/04-与v1的对照.md) | revision/CAS、幂等、receipt、旧版本回放等保持；Owner 机制、模型与结算组织方式改变 | G1 只抽共享机制，领域摘要/校验/副作用保留；FactType/Resolver/包组织留 G3/G4 |
| [执行规格](../../superpowers/specs/2026-11-09-architecture-v2-execution-spec.md) 与 [执行计划](../../superpowers/plans/2026-11-09-architecture-v2-execution.md) | 本轮 G0 的范围与阶段门；文档状态仍为提案，不代表 G1 自动获批 | 用户本次授权建立 G0 基线，不扩为 runtime 迁移或语义修复 |
| [旧幂等缺陷记录](05-基线缺陷-幂等回放未校验.md) §10 | 历史文字声称修复 | 本 HEAD 的 missing:event 重试仍成功，见 F058 `test_package_exchange_rejects_corrupt_receipt_event_reference`。当前运行证据优先；独立缺陷轨道处理 B1 |
| [历史失败清单](06-已知基线失败清单.md) | 历史版本/特定 15 域集合 201 失败 | 当前已更新版本且使用全 backend/tests 集合，不能相减解释为“修复了 93 项” |

实施前必须保留的语义：一个作用域/epoch 一个 canonical writer；未知保持 unknown/拒绝；模型结果不直接成事实；旧版本回放；补偿追加；医疗 Workflow 无领域写权；Object/Objective 不越权。上述语义不因 shared base 或 stewarded 实现改变。

## 能力状态：定义不等于接入或验收

| 能力 | 已定义 | 当前可执行证据 | 已接入 / 已验收边界 |
|---|---|---|---|
| Gameplay EventStore、atomic batch、revision、receipt | 是 | 两轮正式 backend 测试及定向清单；仍有坏收据缺陷 | 有 Python 域使用；不代表所有 Owner 或 UE 已验收 |
| 统一 Owner runtime base | v2 计划 | 当前 backend/app 下未找到 `owner_runtime_base.py`；存在各域 runtime | 未证明共享机制已迁移；不得把测试通过数当迁移进度 |
| 读时 principal 可见性强制 | v2 已定义 | 本次检查 event_store 的 read_stream/read_events/get_event 及 durable 对应接口未带 principal 强制边界 | 只说明这些通用读取接口；不宣称全仓没有裁剪视图或授权检查。G2 正反用例与性能待做 |
| event/known/presented 三时间 | v2 已定义 | 本轮 event_store 源内未见 known_time/presented_time；其他域可能已有自己的时钟字段 | 不能用历史“全仓零命中”当本 HEAD 结论。G2 统一保留与回放证据待做 |
| authority epoch 栅栏 | v2 已定义 | 本轮未审计全仓所有授权路径；不把字段存在当提交强制 | G2 必须在真实提交边界拒绝旧 epoch；当前未验收 |
| Pool/Bond 六原语 D1 | 原型规格有记录 | 四份原型源码存在，哈希见 evidence-inventory.json；历史 2026-11-03 记录 Pool/Bond 各 25 项 | 本轮静态核验产物，未重跑历史版本。仅原型层面，不证明现有 runtime 集成、性能或 C++/Python 双端等价 |
| FactType/Resolver/规则包/L2–L5 Inventory | v2 定义 | 本轮未实施 v2 参考链路 | G3/G4 待验；不能借现有 Inventory runtime 测试宣称分水岭实验通过 |
| UE / Agent 权威对齐 | v1/v2 均有接入契约 | backend 协议测试不是 UE PIE；本轮没有启动 UE | G5 未验，当前 Demo 接入状态不能由文档推断 |

D1 的 `cross_check_real_modules.py` 保留历史硬编码路径；重跑时要明确源版本和适配路径，不能让它误读旧 checkout。本次没有改原型，也没有将历史 50 项结果标作新运行。

## D2–D10 阶段门映射

来源：[待决清单](../10-待决/01-待决清单.md)。下表是依赖映射，**所有事项仍 OPEN**；“建议”不是已经批准的实现决定。

| 决策 | 必须先解决的工作 | 门与处置 |
|---|---|---|
| D2 writes_fact_types 严格度 | Resolver 注册/跨层写权校验 | G3 注册前；G4 用非法跨域写样本证明，不能擅自选择宽松 |
| D3 native Resolver 是否同表 | L3/L4 注册实现 | G3 前；G4 同等治理证据 |
| D4 resolution_order 分配 | L2 pipeline/偏序与冲突校验 | G3 实现前；G4 漂移/碰撞拒绝 |
| D5 native/stewarded 审批 | Owner 注册和升级流程 | G3 前；先明确批准人/证据，不能由代码抽取顺手裁定 |
| D6 可见性性能 | principal 读取强制/投影缓存 | G2 扩大读取范围前实测；预算须登记，不杜撰毫秒阈值 |
| D7 环境事实权威 | 温湿度/火烟等作为模型输入 | G3/G4 样例一旦依赖则先解决，G5 相关场景也需要；未依赖时不 blanket 阻塞 G1 |
| D8 士气聚合 | 群体士气结算 | G5 Demo 相关路径前；G3 样例若使用则提前，不把士气猜成 sum |
| D9 热加载时机 | 规则版本切换与回放 | G3/G4 版本生命周期实现前，禁止默认为运行时随意替换 |
| D10 容量验证时机 | 规模设计/外推与测量 | G4 架构结论/性能及 G5 容量验收；不用当前单机 pytest 代替十三州规模证据 |

## G1 定向回归输入

清单由正式收集的节点生成，包含精确参数化 ID、文件和基线 outcome；同一个测试可在多个域出现，不应相加冒充总测试数。文件计数与节点计数见 [清单索引](G0-20261109-5321266d/G1-regression-index.json)。这是最小已命名边界；开始每个迁移单元时，按实际调用者增补清单并冻结，不能只运行少数正例。

| 范围 | 冻结清单 | 必须保留的检查 |
|---|---|---|
| ownership | [JSON](G0-20261109-5321266d/G1-ownership-regression.json) | 所有权事实/合同；当前非历史数量 |
| modifier / effective stats / resource bridge | [JSON](G0-20261109-5321266d/G1-modifier-regression.json) | Decimal 摘要、定向撤销、投影和 bridge |
| equipment / command / prediction / recovery | [JSON](G0-20261109-5321266d/G1-equipment-regression.json) | 幂等重放校验、body revision、旧交易副作用恢复 |
| inventory | [JSON](G0-20261109-5321266d/G1-inventory-regression.json) | reservation、projection、cadence；现有 3 项失败照录 |
| 公共事件/回放与阻断回归 | [JSON](G0-20261109-5321266d/G1-shared-replay-regression.json) | EventStore、world replay、economy 坏收据、population 恢复身份 |

每个清单旁的 `G1-*-nodeids.txt` 可由脚本读取为 pytest 参数；Windows 上避免把所有节点拼成可能超长的命令。仍使用本基线的 cwd/sys.path/依赖，不以悄悄换环境后的通过替代原对照。未知新增失败立即阻塞当前迁移。

## modifier 与 equipment 专门保护

modifier 的 `_digest`（`backend/app/gameplay/modifier_runtime.py:159`）自有 Mapping / __dict__ / Decimal(str) 处理，不能用 generic JSON/default 代替。已有 `test_modifier_source_replay_deactivates_only_the_matching_instance` 使用 Decimal 注册并验证撤销边界；`test_equipment_durable_reopen_replays_receipt_and_unequip_preserves_learning` 覆盖 durable reopen/unequip/学习不丢失。**这不是所有 Decimal 摘要边界已经覆盖**：G1 抽取前补充混合 Mapping、嵌套 Decimal 精度、尾零/符号与原摘要逐字对照方案；不在 G0 修改 runtime 或新写行为测试。

equipment `_duplicate`（590–604）在校验收据后仍会重调 `resource_modifier_bridge.sync_equipment_transaction`；append 后也有 bridge 副作用（743 附近）。共享化不可删除重复请求修复 bridge 的行为。已有 `test_equipment_lost_bridge_response_recovers_on_exact_duplicate` 必须保留。

`_validate_replay_receipt`（606–647）按当前代码分成八组，不把不存在的 revision/outbox 校验算进去：

| # | 现有保护 | 当前专用覆盖/补充计划 |
|---|---|---|
| 1 | committed、非空 refs、result.command_id 匹配 | 正常重复重放已有；每个反例分别变异，G1 前补足 |
| 2 | event refs 唯一 | 补重复引用反例，且验证零写入 |
| 3 | transaction 存在、batch event IDs 精确同序 | 补 missing transaction / 少项 / 重排反例 |
| 4 | 每个 event ID 可解析 | `test_equip_duplicate_rejects_corrupt_event_reference_without_writes` 已有；仍须确保没有只因 #3 提前拒绝而漏验 #4 |
| 5 | event command/causation/correlation/transaction 一致 | `test_equip_duplicate_rejects_changed_causal_identity_without_writes` 有 causal 覆盖；其余身份分别补 |
| 6 | stream 只能是该 actor 的 inventory/equipment/ability/modifier | 补另一 actor / 非法 stream 反例 |
| 7 | 各 stream 的 event_type 合法 | `test_equip_duplicate_rejects_event_type_moved_to_wrong_stream_contract` 已有 |
| 8 | visibility_policy=authority_only | 补 visibility 变异反例 |

另有 `test_stale_body_revision_rejects_before_any_stream_changes`，这是 body 前置 revision 校验，不能误称 #1–#8 中有 replay revision 校验。上表所有补充项在实施批次前转为独立保护测试；现有绿灯不能代替逐谓词 coverage。

## 当前放行条件

1. 保留两轮完整基线与差异解释；若集合/类型/语义堆栈不一致，标记不稳定并定位。
2. 独立处理 [分类记录](baseline_failures_classification.md) 中 B1；对 B2/B3/B4 提交修复/契约决定或精确边界排除证据。
3. 更新并重复相关回归，冻结 G1 源版本与环境；审批仅对具体门和范围生效。
4. 本报告不批准 G1，不关闭 D2–D10，不宣称 v2/UE/Demo 已验收。
