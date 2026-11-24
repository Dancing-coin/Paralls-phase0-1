# 守城三条路径和 Information 接线合同

- 2026-11-24。A 权威输入和生产接线基线为 8227e94c609247eaba1a663ee52d5ae69b1db90b。B 以 8b37e3ce49ff241625102bea857cc82215216503 为本次开工基线。
- 接线参数、生产缺项和交付分支见 [H-B-009](../../v2-coordination/handoff.md#h-b-009--守城-information-接线交付--2026-11-24)。验证范围见 [证据](evidence.md)。

## 接口和状态

| 路径 | 权威输入 | 输出 | 当前状态 |
|---|---|---|---|
| casualty → Morale | 已提交 LifeState casualty 与死亡位置的 Organization roster、LifeState 历史 | Morale refold 后提交 Pool | A 分支已有生产装配。B 在 A 分支及组合快照复验 |
| facility breach → Presence | Facility Pool 的 breach 阈值事件、独立已验签的通行性评估 | Presence Owner 提交 Place passability，缺乏可信评估时为 unknown 且零写入 | A 分支已有生产装配。生产 Gate profile 数值、impact_gate 持久义务和实跑待验证 |
| report delivery → Information | 已提交且可见的指定报告送达，权威当前 tick | Information 提交 gameplay.information.knowledge_updated@1，outbox 限定收件人 | B writer、声明及隔离组合探针已交付。生产 factory、报告来源识别、时钟与 L5 的装配归 A |

## 所有权

~~~mermaid
flowchart LR
    LY["LifeState 与 Organization"] --> L["A · Gateway / L5"]
    L --> M["A · Morale / Pool"]
    F["A · Facility / Pool"] --> L
    E["A · 签名通行性评估"] --> P["A · Presence / Place"]
    L --> P
    S["已提交 SocialDelivery"] -. "生产报告匹配待接" .-> L
    L -. "生产 handler 待接" .-> I["B · Information Owner"]
    I --> G["收件人私有事件与投影"]
~~~

## 时序

~~~mermaid
sequenceDiagram
    participant S as SocialDelivery
    participant L as Gateway / L5
    participant I as Information Owner
    participant O as EventStore / outbox
    S->>O: 提交送达 v2
    Note over O,L: 隔离探针已验证，生产报告来源映射待接
    O-->>L: 已提交送达事件和报告类型
    L->>I: update_from_delivery 与权威当前 tick
    I->>O: 核验来源并用 revision 保护私有提交
    O-->>I: 提交回执或原样重派回执
    I-->>L: 返回回执
    O-->>O: 向收件人发布
~~~

## 数据流

~~~mermaid
flowchart LR
    SD["SocialDelivery committed v2"] --> R["守城报告来源匹配 · 生产待接"]
    R --> C["稳定 command_id / idempotency_key"]
    T["权威当前 world tick · 生产待接"] --> V
    C --> V["Information：重新读已提交送达、可见性和撤销状态"]
    V --> CAS["检查 delivery / source / target revision"]
    CAS --> IE["Information knowledge_updated@1"]
    IE --> PV["actor-private outbox 与图投影"]
~~~

## Information 已实现合同

- 输入为 gameplay.social.delivery_recorded@2 的已提交事件。必须通过交易和 idempotency receipt 校验，recipient 必须与命令一致，且 SocialDelivery 视图当前仍包含该送达，排除撤销和过期。
- 输出为 gameplay.information.knowledge_updated@1。payload 引用 report event、delivery event、delivery ref、known tick、报告 source stream/revision。stream 按 recipient 与 report 唯一定位，visibility 和 outbox audience 均为 actor:<recipient>。
- 写入同时 read-pin delivery stream 与 source report stream。相同 command 身份精确重试返回原提交，不重复写事件。
- 域 schema 自声明于 backend/app/gameplay/information_event_schema.py，事件可被 FactTypeRegistry 自动发现。生产 EventSchemaRegistry 的具体 factory 需由 A 接线。
- 送达触发标识使用 fact:information:siege:report。B 包的可信输出声明为 fact:information:siege:report_knowledge，记录指定收件人收到了报告。

## 2026-11-23 原始验证

Python 为 3.12.2，app.__file__ 指向 B worktree。B 的新 Information 测试 5 项通过，包括真实 delivery 输入、重放、错误 recipient、撤销拒绝与 outbox 图投影。联合 SocialDelivery 读路径测试共 6 passed, 2 warnings in 0.26s。原始日志位于 F:/paralls-verification/thread-b/siege-three-paths-preflight-20261123/information-green2.log。B 端未接到 M6 Gateway。

Morale 和 Presence 未验证生产写入，不计入上述测试数量。
