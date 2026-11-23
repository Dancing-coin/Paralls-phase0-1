# 守城三条生产路径的 B 域交付

- 基线：B `155d496c7d26ab0b8f49f67805a2cce728a29692`；integration `810a46c1249918c09b42fa1fe0c12d7d784579d2`；A `691792c72c65335dedfdf0030a5ab6f6c04fcd24`。
- 结论：Information B 域 writer 已实现并通过定向验证。Morale 只有 LifeState 触发合同与 Pool 适配探针，未实现 Morale writer。Presence 未实现通行性 writer，生产设施破口事件不存在。
- 范围：为 M6-5 提供三个 B 域的命令处理方和可信输出事实。A 的 Gateway、L5 注册、main.py 与共享 EventSchemaRegistry 启动接线由 A 处理。生产组合尚未验收。

## 现状和接口

| 路径 | 已有 B 域输入 | B 侧结果 | 状态与缺项 |
|---|---|---|---|
| casualty → Morale | LifeState v2 的真实死亡提交。Organization 有 membership_delegation_recorded@1，但当前无经定义的守军编制合同。 | 候选 Pool fact:unit:<group>:morale，按候选 morale_refold@1 计算。 | 未完成。Owner 的 Pool 尚未进入 B integration。D8 没有权威模型。四人名单 1 人死亡得 75 是仅用于评审的候选向量。 |
| facility breach → Presence | 未发现设施完整度破口的生产事件或 writer。Construction Production 目前记录 acquire/repair 等，repair 将 condition 提高。 | Presence 应基于已提交破口事实独立提交 passability。 | 未完成。必须先确定 breach 来源和 resolver 输入，不能用现有环境可通行性推导代替设施事实。 |
| report delivery → Information | SocialDelivery 已提交事件 v2，包含收件人、报告源事件、来源 stream/revision、送达时间；视图验证可见性和撤销。 | B 新增 gameplay.information.knowledge_updated@1，按收件人私有可见性持久记录已送达报告。 | B 域 writer 已实现。需要 A 将 EventSchema 注册器的生产构造纳入 register_information_event_schemas，并登记 M6 的输入触发、命令、目标与具体输出 FactType。 |

## 所有权

~~~mermaid
flowchart LR
    L["已实现 · LifeState"] --> M["未实现 · Morale Owner"]
    O["Organization delegation 候选 roster"] --> M
    F["未发现 · Facility breach writer"] --> P["未实现 · Presence Owner"]
    S["已实现 · SocialDelivery"] --> I["B 已实现 · Information Owner"]
    M -. "A Pool 尚未进 integration" .-> A["A · Pool / Gateway / L5"]
    P --> A
    I --> A
~~~

## 时序

~~~mermaid
sequenceDiagram
    participant L as LifeState
    participant O as Organization
    participant M as Morale
    participant F as Facility
    participant P as Presence
    participant S as SocialDelivery
    participant I as Information
    participant A as Gateway / L5
    L-->>A: 已提交 death receipt
    O-->>A: 候选 membership facts
    A->>M: 待接线 recompute_morale
    M-->>A: 待交付 Pool receipt
    F-->>A: 当前无 breach receipt
    A->>P: breach 后 reevaluate_passability
    P-->>A: 待交付 passability receipt
    S-->>A: 已提交 recipient delivery receipt
    A->>I: update_knowledge(delivery_event_id)
    I-->>A: 已实现 knowledge receipt
~~~

## 数据流

~~~mermaid
flowchart LR
    D["LifeState committed event"] --> R["L5 casualty trigger"]
    R --> G["Organization roster + casualty inputs"]
    G --> C["D8 refold model · 未定"]
    C --> PM["Morale Pool commit · A 依赖"]
    B["Facility breach event · 缺失"] --> RP["Presence reevaluate command"]
    RP --> E["独立 passability resolver · 输入未定"]
    E --> PP["Presence commit · 未实现"]
    SD["SocialDelivery committed v2"] --> V["recipient / time / revocation validation"]
    V --> IU["Information.update_knowledge"]
    IU --> IE["Information knowledge_updated@1"]
    IE --> PV["actor-private outbox + graph projection · 定向验证通过"]
~~~

## Information 已实现合同

- 输入为 gameplay.social.delivery_recorded@2 的已提交事件。必须通过交易和 idempotency receipt 校验，recipient 必须与命令一致，且 SocialDelivery 视图当前仍包含该送达，排除撤销和过期。
- 输出为 gameplay.information.knowledge_updated@1。payload 引用 report event、delivery event、delivery ref、known tick、报告 source stream/revision。stream 按 recipient 与 report 唯一定位，visibility 和 outbox audience 均为 actor:<recipient>。
- 写入同时 read-pin delivery stream 与 source report stream。相同 command 身份精确重试返回原提交，不重复写事件。
- 域 schema 自声明于 backend/app/gameplay/information_event_schema.py，事件可被 FactTypeRegistry 自动发现。生产 EventSchemaRegistry 的具体 factory 需由 A 接线。
- 具体 FactType 候选为 fact:information:<report-scope>:report，需要 A 按权限规则完成声明。该 Owner 事实表示收到报告，不表示报告内容为真或角色内在信念。

## 验证

Python 为 3.12.2，app.__file__ 指向 B worktree。B 的新 Information 测试 5 项通过，包括真实 delivery 输入、重放、错误 recipient、撤销拒绝与 outbox 图投影。联合 SocialDelivery 读路径测试共 6 passed, 2 warnings in 0.26s。原始日志位于 F:/paralls-verification/thread-b/siege-three-paths-preflight-20261123/information-green2.log。B 端未接到 M6 Gateway。

Morale 和 Presence 未验证生产写入，不计入上述测试数量。
