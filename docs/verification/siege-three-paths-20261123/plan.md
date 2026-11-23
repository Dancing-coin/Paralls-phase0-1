# 守城三条生产路径实现计划

> **执行说明：** 项目负责人已要求继续交付三条路径。执行按 B 域实现与 A 共享调度接线分界。

**Goal:** 为 casualty→Morale、facility breach→Presence、report delivery→Information 提供可组合的已提交 Owner 输出。

**Architecture:** B 实现三个域处理方和各自的域 schema。A 的 Gateway、L5、生产 EventSchema registry 和 main dispatcher 负责调度接线。输入事实必须来自已有 Owner 的已提交事件。

**Tech Stack:** Python 3.12.2、现有 Gameplay EventStore、Pydantic、pytest。

**Spec:** [三条路径设计](design.md)

## 全局约束

- 不修改共享 registry、validator、storage、main.py 或 A 独占的 L5/Pool 文件。
- 不修改未拥有的 Organization、Facility writer。缺少事件或 owner contract 时登记依赖，不生成假事件。
- 每个写入事件需要域内 schema 声明及 P-3 实际投影断言。
- 所有验证产物写入 F 盘的新目录，使用固定 Python 3.12.2 并先核验 app.__file__。

## 风险输入

- 未注册、已撤销或过期的 SocialDelivery 不得触发 Information 写入。
- 更换 recipient 或重复送达不得造成额外知识事件。
- 过期 source revision 不得产生跨 Owner 输出。
- 未定义的守军名单、D8 模型或设施破口事件保持阻塞。

## 单元

### Information B 域写入

- 已实现于 information_runtime.py，测试覆盖真实 SocialDelivery event、recipient 隔离、撤销和精确重放。
- A 接 EventSchema factory 与 Gateway 命令前保持 B 单元待门禁，不声称守城端到端完成。

### Morale

- 使用真实 LifeState receipt 和可回放 Organization membership 输入。
- D8 先定版本化 resolver 输入/算法，再提交 Pool 输出。当前等待 Owner 的 Pool 机制进入共同 integration 基线。

### Presence

- 使用 Facility Owner 已提交的 breach/threshold 事件作唯一 trigger。
- Presence 自己解析通行性并提交事件，不从设施破损直接推断通行性。
- 当前等待 Facility breach writer 与 resolver 输入合同。

### 验证与交接

- 每个可交付单元先写真实输入/输出测试，观察正确的 RED，再实现并验证 GREEN。
- 对新增持久事件运行定向、完整回放、checkpoint+tail、exact retry、过期 revision 拒绝、P-3 和登记选择集。
- 交付每个单元 SHA、证据路径和 A 所需的 EventSchema/command/output 接线项到 handoff.md。
