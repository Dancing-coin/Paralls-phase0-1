# M5-5 规则包校验器覆盖清单

以 `1f6aff2e3c4ec98809ba334b4f7085a0253162f0` 对照 Architecture v2《03-校验器规则》第二节。状态均为静态核对。代码里的实际拒绝码与规范不同时一并记录。

| 层 | 规范规则 | 当前状态 | 对应路径及缺口 |
|---|---|---|---|
| 原语 | `primitive_count_exceeded` | 结构性保证 | 代码登记表固定且 `test_fact_type_primitive_registry_has_exactly_six_code_registered_values` 锁定恰有六项；规则包不接受原语定义。当前没有运行态可变注册表，因此超限是代码目录变更，注册表数量回归会失败。 |
| 原语 | `primitive_unknown` | 部分实现 | 规则包加载对六种之外的值返回专用 `primitive_unknown`。FactType 编译仍只支持 Machine 与 Pool，Bond、Holdings、Process、Place runtime 需在对应 M1 单元接入。 |
| 原语 | `primitive_missing` | 已实现 | `FactTypeRegistry.compile` 对缺失原语返回专用拒绝码；规则包 shape 检查将该条目交由编译器诊断。回归见 `test_pack_rejects_fact_type_without_primitive_using_missing_diagnostic`。 |
| FactType | `facttype_visibility_missing` | 已实现 | 加载器检查字段类型，编译器拒绝缺失或空映射。 |
| FactType | `facttype_resolution_order_missing` | 已实现 | 每个 FactType 必须有边或显式列在 `unrelated`。循环由 `facttype_resolution_order_cycle` 拒绝。 |
| FactType | `facttype_resolution_order_duplicate`、`facttype_resolution_order_gap` | 编译结构保证 | 拓扑排序后由 `enumerate` 从 10 连续赋值，同一表内无重复或间隔。未建立按 authority scope 独立的顺序表。 |
| FactType | `facttype_owner_unknown` | 已实现 | 校验包内 Owner 名单和 FactType 对名单的引用。Owner 分类、写集与域别名没有随名单登记。 |
| FactType | `facttype_schema_unknown` | 部分实现 | 同名拒绝码检查 Machine 的 `state_set_ref`。规则包编译器未校验 `event_schema_ref`。 |
| FactType | `facttype_refold_missing` | 未实现 | 聚合和 refold 模型未纳入 FactType 编译。 |
| FactType | `facttype_naming_invalid` | 部分实现 | 拒绝段数、前缀或空段不符。域归属、精确字符集和长度尚未检查。 |
| FactType | `facttype_scope_missing` | 已实现 | `fact_type_registry.py` 将 `fact:domain:name` 与 `fact:domain::name` 分类为 scope 缺失；回归见 `test_rule_pack_validator.py::test_pack_rejects_fact_type_without_scope_using_scope_diagnostic`。 |
| Resolver | `resolver_writes_undeclared` | 已实现 | YAML 要求 `writes_fact_types` 列表，编译器检查事实存在及层写集为模型写集的子集。 |
| Resolver | `resolver_owner_mismatch` | 已实现 | 每层声明的 Owner 必须匹配其写入 FactType 的 Owner。 |
| Resolver | `resolver_input_undeclared` | 运行时实现 | `RestrictedInputs` 只保存已声明输入并拒绝越界访问。加载时无法判定注册的 Python evaluator 会访问什么。 |
| Resolver | `resolver_missing_determinism` | 部分实现 | 强制精度、舍入、结算顺序与禁用随机。其他可用策略未接入。 |
| Resolver | `resolver_not_pure` | 未实现 | 注册的 Python evaluator 属受信任代码，未检查其 IO、时间或随机副作用。 |
| 受击剖面 | `impact_layer_facttype_unknown`、`impact_layer_owner_mismatch`、`impact_profile_cycle`、`impact_atomic_cross_host`、`impact_layer_conflicts_order` | 未实现 | 加载器尚无 `impact_profiles`。跨宿主判定需要编译表保留 FactType host 或取得等价的权威声明。 |
| 管线与订阅 | `pipeline_revision_vector_mismatch`、`pipeline_cross_scope_atomic`、`pattern_declares_writes`、`pattern_command_unknown`、`pattern_workflow_cycle` | 未实现 | L5 的这组注册入口未接入规则包加载器。 |
| 规则包 | `pack_contains_logic` | 已实现 | 拒绝执行字段及环境变量替换。YAML anchor、alias 和显式 tag 单独报错。 |
| 规则包 | `pack_invariant_executable` | 未实现 | 未加载不变式表达式，通用执行字段拒绝仍生效。 |
| 规则包 | `pack_overrides_visibility_requirement` | 部分实现 | 所载 FactType 都需显式可见性。父包叠层尚未进入加载器，无覆盖路径可校验。 |
| 规则包 | `pack_defines_primitive` | 已实现 | 拒绝在包顶层声明 `primitives`，也拒绝在 `contents` 中声明原语内容。回归覆盖两种形式。 |
| 规则包 | `pack_cycle_in_parents` | 未实现 | 当前对非空 `parent_pack` 统一报 `pack_parent_unsupported`。 |
| 规则包 | `pack_content_hash_mismatch` | 未实现 | 既有加载器生成 `content_hash`，未接受存档钉定的哈希并在加载入口对比。 |
| Owner | `owner_overlaps_owner`、`owner_writes_denied`、`owner_native_without_resolvers`、`owner_stewarded_with_resolvers`、`owner_no_invariants` | 未实现 | 当前登记结构为 ID 允许名单，没有 L3 Owner 声明结构可供这些检查。 |

本次核对使用 `rg` 检索全部拒绝码并阅读 `backend/app/gameplay/rule_pack_validator.py` 与 `backend/app/gameplay/fact_type_registry.py`。修订版规则仍需满足 H1–H12。H7 提交权限、H11 版本回放与 H12 追加补偿的验证在写入与回放边界进行，本清单未核验。

当前 `load_pack(..., running=True)` 定向用例覆盖 `pack_runtime_reload_forbidden`。生产模块中只有 `credential_reference_chain.py` 的 `load_credential_pack` 调用加载器，`rg` 未找到 `backend/app` 内对该包装函数的调用。M5-4 的应用生命周期接线尚未验证。

## 余项的前置输入

- `command_catalog` 的条目形状和四种幂等键已定义，命令名前缀需要已注册的 Owner domain。目前允许名单不包含 domain，FactType 标识也不能反推该登记，例如 `fact:credential:*:link` 的 Owner 为 `Ownership`。处理 Owner 与命令归属须由 L3 声明提供，参见《Owner 定义》第二节与《Command 信封与回执》第三节。
- `impact_profiles` 已有实体类型、FactType、Resolver 和层序输入。安全加载还需要明确编译后 FactType 的 host，以及 Resolver 对该 FactType 的写集。参见《受击剖面》第四、六节。
- `temporal_effects`、`aggregation_models`、`bindings` 的清单入口已有定义。需要逐项核对条目 schema、引用空间和消费边界。父包、迁移事件与版本回放仍归 M5-2、M5-3。

本单元为 M5-5 静态盘点。U2、U4、U6 有静态证据，U10 为本文件。U1、U3、U5、U7–U9、U11 的域实现或运行验证未做。没有为本清单单独运行 pytest。

## 截至 `b7bb3605` 的增量核对

| 规范规则 | 当前状态 | 代码与边界 |
|---|---|---|
| `impact_layer_facttype_unknown`、`impact_layer_owner_mismatch`、`impact_layer_conflicts_order`、`impact_atomic_cross_host` | 加载校验已实现 | `rule_pack_validator.py:94` 检查 FactType、Resolver 写集、层序与 host。独立 `impact_profile_cycle` 诊断未做，当前只接收顺序层列表。 |
| `pack_overrides_visibility_requirement` | 加载校验已实现 | `rule_pack_validator.py:437`、第 493 行附近核对继承 FactType，只允许保留声明或收窄 `learnable_by`。 |
| `pack_cycle_in_parents`、`pack_content_hash_mismatch` | 加载校验已实现 | `rule_pack_validator.py:474` 和第 538 行分别拒绝父包环和钉定哈希不匹配。生产存档尚未提供钉定值。 |
| `pattern_declares_writes` | 离线校验已实现 | `l5_play_pattern.py:35` 返回规范拒绝码。其他 Pipeline、Reaction、Workflow 规则与生产接线待做。 |
| `facttype_refold_missing` | 未实现 | `rule_pack_validator.py:158` 已验证聚合模型条目，FactType 的必需 refold 关联仍未接入。 |

命令目录通过受信任调用方提供的 Owner → domain 映射校验命令名及处理方，见 `rule_pack_validator.py:204`。规则包加载器也已接入 `aggregation_models`、技能消耗 `bindings` 与 `impact_profiles`。运行态加载拒绝仍由调用方传入 `running`，生产装配待做。以上是代码静态核对，各切片的运行证据见对应验证文件。

## 截至 `6e7da420` 的 L5 增量核对

本表为静态读取代码与定向测试的映射。各版本实际执行结果见 [Pipeline](m6-2-pipeline-20261123.md)、[Workflow](m6-3-workflow-declarations-20261123.md) 与 [组合包加载](m6-composition-pack-loading-20261123.md) 证据。

| 规范规则 | 当前状态 | 代码与边界 |
|---|---|---|
| `pipeline_revision_vector_mismatch` | 输入绑定已实现 | `l5_pipeline.py:32`、第 40 行拒绝各层 revision vector 不一致或缺失。需要生产 Gateway 在结算前传入实际读向量并纳入既有 CAS。 |
| `pipeline_cross_scope_atomic` | 声明与输入绑定已实现 | `l5_pipeline.py:84` 拒绝声明中的明确跨 scope，`l5_pipeline.py:30` 拒绝实际绑定后的跨 scope。生产目标解析和提交未做。 |
| `pattern_declares_writes` | 编译与加载已实现 | Play pattern、Workflow 和 Reaction 各自拒绝直接写入声明。`load_pack` 已接入三种内容编译，见 `rule_pack_validator.py:598` 与第 617 行。 |
| `pattern_command_unknown` | 编译与加载已实现 | Workflow 用解析后的 `command_catalog` 校验命令。Reaction 还需要调用方提供可信输出集合，过滤到有效目录后校验命令与回路。 |
| `pattern_workflow_cycle` | 编译与加载已实现 | `l5_workflow.py:101` 将拓扑排序发现的直接、间接依赖环转换为该拒绝码。 |

父包、Owner 声明、FactType refold 关联与持久包版本的既有缺口继续见前表和 H-A-009/010。本次未修改生产代码或测试断言。
