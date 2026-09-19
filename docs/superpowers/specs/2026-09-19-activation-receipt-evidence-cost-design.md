# 激活回执的运行时证据与全历史审计

Status: awaiting-user-review

本提案只处理六项闭环中已发现的激活回执长局增长；不是通过报告，也不改变现行契约，用户确认前不实施依赖变更。

## 已确认的问题

`ProfileActivationAuthority._receipt_from_result` 为每次锁获取、释放等操作创建全局 `GameplayProjectionReplay` 结果。虽然只读取新事件，`continue_replay` 仍复制全部投影、版本向量和事件 ID，并对完整 canonical JSON 排序、序列化和 SHA256。缓存规模也随所有 Owner 历史增长。

2026-09-19 的 100 人 320 秒实时诊断中，单次回执由约20–30ms增至228.63ms，owner RSS由113.18MiB增至196.96MiB。RSS包含整个runtime，尚未按对象归因；回执阶段耗时来自原方法包装计时。同期SQLite事务退出与execute未记录到20ms以上的样本。插桩与同时进行的CI修复使此次采集只能用于诊断，不能作为正式性能通过证据。

旧全局hash包含按字典序排列的全部event IDs、全部stream最新state/vector和全局sequence。严格相同的SHA256不支持仅用新尾部修补该canonical JSON；局部少复制/少排序无法消除历史增长。

## 建议的具体行为

- 保留 `ActivationReceipt` 的提交状态、事件ID、版本向量、身份摘要、scope、幂等状态与锁释放语义。
- 明确区分 `commit` 与 `full_replay` 证据，不能把某个局部digest塞进旧 `replay_hash` 冒充全历史重放结果。
- 运行时的 `commit` 证据附带原 `AppendBatchResult.global_sequence_range`；`replay_hash` 留空，证据类型明确为commit。只从已成功持久化的AppendBatchResult构造，不额外读取全历史，不持有ReplayResult缓存。
- 显式审计仍生成原 `full_replay` 证据与原hash，包含其他Owner事件，结果与既有 `GameplayProjectionReplay.full_replay` 完全相等。恢复/幂等/权限仍按原权威事实和提交回执校验。
- 不改变事件正文、事务原子性、SQLite FULL durability、pending obligations、token/revision pins、重放算法或已有审计hash定义。不引入新事件总线、哈希树或数据库。
- 证据选择应在明确的运行时/审计调用边界完成，不引入环境变量或用户可控的证据降级开关。

## 验证要求

1. 跨Owner历史增长后，运行时锁获取/释放不调用全历史read/replay且不缓存历史投影；receipt的事件ID、global sequence和revision与持久AppendBatchResult一致。
2. 失败和重复请求仍为原zero-write/幂等语义；旧token不能释放新锁，释放失败仍保留清理义务。
3. 显式审计的hash与同一提交截面的full_replay一致；含其他Owner事件和字典序乱序event IDs。
4. metrics记录原遗漏的激活历史缓存；正式千人2小时仍按既定RSS上限与1×性能门槛，不能凭静态检查宣布通过。
5. 既有激活、认知continuation、恢复、混合负载与正确性门禁回归通过；Godot依用户本轮要求继续暂缓。

## 若保留现行契约

只做兼容的常数优化，保留完整history hash与cache；长局成本仍随历史增长，不能承诺该路径已满足有界缓存或千人2小时验收。
