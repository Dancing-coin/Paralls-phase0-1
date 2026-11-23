# M6-5 守城 Demo 最小集前置核对

依据 11-22 迁移计划 M6-5 与《守城 Demo 的组合定义》第二节。对 `abfe1443` 只读核查 `backend/app/gameplay`、`backend/app/models` 与 `packs/`。在代码与包中以命令名、触发字段和事实类型查找生产读写入口。

| 条目 | 已找到的生产路径 | 缺少的接线证据 |
|---|---|---|
| `casualty_to_morale` | `CanonicalLifeStateAuthority` 在 `life_state_runtime.py` 中写 `gameplay.character.life_state_changed`，共享事件 schema 已登记。 | 需要映射到触发 FactType 和可信群组目标，登记 Morale Owner 处理的重算命令与输出事实。代码中的 actor-private morale estimate 是不同数据面。 |
| `gate_breach_to_presence_reeval` | `rg -n 'reevaluate_passability\|passability\|gate_breach' backend/app/gameplay packs` 无命中。 | 需要以 Facility 完整度事实的已提交越阈为触发源，并接入 Presence 独立评估通行性的命令与回执。 |
| `report_arrival_to_knowledge_update` | `rg -n 'report_delivered\|update_knowledge\|report_arrival' backend/app/gameplay packs` 无命中。 | 需要 Information 的送达事实和收件人可见性路径。收到报告后才能触发知情变更。 |

按目录核查，当前 A 分支 `packs/` 只有 Credential 参考包。三个条目依赖相应域迁移和 M6-1 的提交后 Gateway 调度。守城简写 `fact_type`、`command`、`event`、`threshold_crossed` 需映射到接入时确认的正式字段与事件。M6-5 生产场景和探针未实施。

2026-11-23 在 `6e7da420221c8a7ca4f3fb762153b2542e5b004c` 重查上述命令名，并将范围扩到 `backend/app/models`，结果仍无命中。已找到的加载调用为 `rule_pack_validator.py:613` 的 `compile_reactions`、第 625 行的 `compile_play_pattern`，以及 `credential_reference_chain.py:74` 的 `load_pack`。原始命令、退出码与输出在 `F:/paralls-verification/thread-a/c-2a0a004b/static-evidence.json`。本表为静态名称与调用点核对，动态注册未核实。
