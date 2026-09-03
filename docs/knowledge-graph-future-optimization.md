# 知识图谱后期通用化优化项

状态：`deferred; current runtime capability is usable`

## 当前结论

当前 Heavenly Graph 已是运行时可用的领域知识图谱：角色、司命和 Authority 可以通过现有内部端口真实写入、语义查询、恢复和回放。它服务于当前 `world-character-Siming-authority unified runtime`，不是独立的通用图谱平台。

这不是当前运行时闭环的阻塞项，也不影响现有角色连续性、行为回合、司命和 Authority 证据。

## 后期优化方向

1. **通用访问层**
   - 提供稳定的查询、写入、回放和诊断 API。
   - 将内部 `HeavenlyGraphPort` 能力整理为面向工具和服务的版本化契约。
   - 增加查询权限、分页、过滤和可观测错误模型。

2. **规模化存储**
   - 评估从单机 SQLite 扩展到多进程或分布式存储的边界。
   - 保留当前双时态、分支、修订、幂等和 replay 语义。
   - 用并发、数据量和恢复基准决定是否需要迁移，而不是预先引入新数据库。

3. **生产运维**
   - 补齐备份、恢复、迁移、归档和数据保留策略。
   - 增加索引、容量、锁竞争和长时间运行监控。
   - 定义故障时的 fail-closed、重试和重放操作手册。

4. **数据治理与演进**
   - 建立 schema 版本升级和兼容策略。
   - 明确冲突、撤销、删除、隐私擦除和 provenance 保留规则。
   - 为跨版本 replay、correction lineage 和 endpoint scope 增加迁移验证。

5. **全量覆盖证明**
   - 用长期真实业务流验证所有 Authority committed events 持续自动投影。
   - 覆盖新领域接入、重启、分支、回放、纠正和隐私过滤的组合场景。

## 未来完成标准

只有同时具备以下证据，才可将本项从 deferred 改为 complete：

- 版本化通用访问契约已发布并有权限边界证明；
- 目标规模下的并发、备份恢复和迁移基准通过；
- schema、删除/撤销、隐私和 provenance 治理规则已落地；
- 长期真实业务流的全 Authority 投影覆盖有可重放证据；
- 现有运行时 Harness 和历史证据保持通过。

## 当前不做

- 不因“通用化”提前替换 SQLite；
- 不引入 Neo4j、JanusGraph 或新的分布式图数据库；
- 不把 TTS、VLA 或其他 provider 就绪项混入本图谱优化项；
- 不把当前领域图谱重新描述为不可用或未完成。
