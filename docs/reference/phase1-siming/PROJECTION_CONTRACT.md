# 权威事件图投影契约

`HeavenlyAuthorityEventProjector`（天道权威事件投影器）将已注册事件映射到 `HeavenlyGraphNode`（天道图节点）。主组合通过 FactType（事实类型）及已注册玩法类型显式订阅，启动验证类型覆盖率；不是通配订阅。图示见 [STATE_MODEL.md](STATE_MODEL.md)。

| 输入 | 输出字段 |
|---|---|
| event_id | node_id = authority-projection:{event_id} |
| room/scene/zone 与作用域解析器 | scope（作用域） |
| producer_ts | valid_from、recorded_at（时间，不是 Owner 版本） |
| 类型注册表 | attributes.domain / event_type |
| payload.owner_ref 或 source.system | attributes.owner_ref |
| payload.source_revision_vector | 保留完整向量；有效非负整数的最大值作为兼容 source_revision，缺省 0 |
| 原始 payload | committed_payload 的深复制 |
| event_id / causation_id / correlation_id / source | provenance（来源链） |

固定节点类型 `causal_event`，`record_kind=projection`（派生副本），`visibility_scope=siming_internal`（司命内部可见），`derivation_kind=authority`（由权威事件派生）。这不授予司命领域事实所有权。每个事件写入带稳定幂等键的批次。

聚合类型使用 world、visual、esm_world、character、conversation 等领域映射；玩法类型来自结构注册表。未注册事件不投影。节点语义注册器可按实例扩展，但不能替换保留类型或绕过命名空间、记录类别和可见性约束。

图保存派生副本和司命记忆，与 `SimingDataLayer` 的六张司命产出表不是同一存储；不能声称已实现“图→数据层→三个模型”的统一恢复链。

Phase 2: 图聚焦关系，事实读取走 OwnerFactQuery（权威事实查询）；完整修订向量对账和历史混合版本数据治理延期。本轮不改历史版本、不增加 Owner。
