# M2-1 Ownership 与 Credential 读取边界增量盘点

代码快照 `e349187e56be87b1df729cf807162657a886cff6`。沿用 [G2 读取路径盘点](g2-visibility-budget/read-path-inventory.md) 的主体与可信权威/恢复分类。覆盖 M1-1 涉及的读取链，其他域的全库计数沿用各自快照。

| 读取入口 | 分类 | 实际调用关系与授权证据 |
|---|---|---|
| `credential_runtime.py:192` `verify_right_holder_presentation` | 面向主体的决策接口 | 读取事件后重建 Credential、Inventory、Ownership，返回含凭证 ID、权利引用和拒绝原因的决策。参数 `presenter_ref` 表示被检查的主体。源码调用搜索只在测试中发现该公开方法的调用，生产认证及授权入口未核实。 |
| `land_right_runtime.py:126` `transfer` | 可信权威 | 一次读取事件快照，重建产权和凭证。第 154 行调用内部 `_verify_presentation_from_events`，判定结果用于拒绝或继续提交。调用链在 `adventure_basic_reference.py:802` 返回交易结果。 |
| `credential_reference_chain.py:97` `freeze_inputs` | 可信权威 | 第 143 行 `execute` 取冻结输入供 Resolver 决策，使用权益、凭证及持有者库存投影。投影值用于准备命令，入口返回提交结果。 |
| `credential_runtime.py:350`、第 419、456、623 行 | 可信权威 / 幂等恢复 | 授权提交前重建旧记录与当前投影。重复命令按原批次的事件 ID 查回提交凭据。 |
| `adventure_basic_closure.py:67` `capture_adventure_basic_closure` | 可信恢复 / 验证 | 从在线、全量重放和 checkpoint-tail 的事件序列构造领域 facade，核对 Ownership 与 Credential 投影的序列化结果。主体接收方未发现。 |
| `adventure_basic_reference.py:821`、第 1102 行 | 已知样例读取，应用去向未核实 | 样例公开方法直接返回 Ownership 投影。已搜索 Backend 入口与直接调用，未发现用于主体输出的生产证据。 |
| `fixed_offer_purchase.py:172`、第 263 行和 `gift_runtime.py:122` | 可信权威 | 发布交易、购买与赠与时重建 Ownership，检查卖方或赠与方的权利。此处只核对调用。 |
| `ownership_contract_debt_sample.py:103`、第 114 行 | 样例流程内部 | 从 Ownership 投影读取抵押物权利。其余域的生产下游留给对应迁移单元。 |

使用 `rg -n 'verify_right_holder_presentation|_verify_presentation_from_events|CredentialProjector\(|OwnershipProjector\(|CredentialReferenceChain\(|LandRightTransferAuthority\(' backend/app backend/tests scripts -g '*.py'` 枚举显式读者，并逐行阅读上表中的函数。动态调用与生产配置未核实。M2-2 的认证主体、资格解析、事件到可见性声明的映射及 `known_time` 仍待接入，见 H-A-005。此表为静态证据。
