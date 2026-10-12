# 默认人口链不可变帧复用设计

Status: awaiting-user-review

本文件是现有性能 Goal 的候选设计扩展，尚未获实现批准。基线为 74f91d13eea5b4ac009dc88fe5895f999a466cc8；main 为 6a03a0fdcbba66096b2756a1a500442209af48eb。此稿只新增设计文件，不修改运行时代码或旧证据。未经用户审阅，不进入生产实现或新增产品依赖。

## 目标与已知事实

目标仍是两档人口 10× 各 30 个完整窗口通过原 verifier，保持 28 人常规输入、fixture 每组最多 16 人的合法事务、FULL/WAL、单 owner 写入、幂等/CAS/回滚、公开对象原有可变及别名行为、独立消费者视图、原 canonical hash、完整恢复检查点和持久确认后可见性。

最新无阶段探针的真实装配诊断千人每窗 125.5023ms，全部 30 窗超过 100ms，到结束积压 9 窗。近期完整阶段诊断包含原 backend/WS/fact/writer probes，每窗 fixture/cadence 根约 41.2590/92.1872ms，原离线 verifier 完整性通过、性能失败。CPU 根时间接近墙钟，不能把当前吞吐缺口只归因于刷盘或 provider；该 3 秒窗口 provider calls=0。

证据：

- `D:/ParallsEvidence/paralls-performance-closure-20261002T032000Z/io/cpu-selection-74f91d13/report.md`
- `D:/ParallsEvidence/paralls-performance-closure-20261002T032000Z/io/formal-stages-74f91d13/report.md`
- 阶段证据封存 SHA256：`fc24c1c9cf96f493dd891969540ea137630ba04fdb4ec94725ea747af971023e`。

已停止的 native 容器复制候选整链三对平均收益约 0.97%，且仍有安装/默认语义缺陷；B0 跨进程预计算可移走的已测路径约 7ms，传输和重建成本尚未扣除。二者均不作为本方案依赖。

## 选择

推荐评估同一 owner 内的不可变帧复用。减少默认闭合链中对同一 B0 事实反复进行的表示转换；不以跨进程预计算为前提，也不新增异步 writer。

另一路是继续替换通用 deepcopy/JSON 实现。已有差分反例和整链计时否决了具体候选，当前没有足够证据支持为通用替换继续付出成本。因此本设计先处理数据在组件之间的传递方式，保留通用接口处理扩展输入。

这不是已证实的收益方案。下述正确性和整链阶段门失败即停止候选，原正式失败不改签。若仍不能补足吞吐预算，Goal 继续保持未完成。

## 数据形态

新增 private `PreparedPopulationFrame`，只供生产默认 publisher/bus/Siming 组合使用。生成者是 publisher，输入是原 world 公开构造方法实际返回的当前投影及已校验的领域投影；不增加 world 私有预览入口，也不提前缓存 world 的可变返回值。帧记录 cadence 身份和实际输入 pins，分别保存发布阶段的 typed B0 表示、其完整 JSON 片段，以及实际事件边界信息。

帧只含 bytes、builtin 标量、tuple 和 frozen dataclass。不得保留调用方模型、list/dict、MappingProxyType 的可变底层、闭包、服务、SQLite 连接或 provider。frozen Pydantic 模型内的 dict 不视为深度不可变。帧有固定单窗口生命周期；正在处理及重试所需保留量至多两个窗口，且不得形成按 cadence_id 无界增长的缓存。

原模型的公开字段及 Python 类型是合同的一部分。`False == 0` 不能证明表示相同；向量规范化、Any 值、tuple/list、Unicode、NaN/infinity、自定义 serializer/copy hook 都必须在资格和差分检查中显式覆盖。原型先只接受原默认 B0 结构及确切 builtin 类型；扩展值、自定义 hook 和不满足资格的领域行走原路径。每份复用字节绑定它实际经历的规范化阶段，不能将 raw 字段、typed JSON 和 read-set 的字节混用。

## 默认链与公开边界

1. world 继续调用原 `build_population_projections()`，保留缓存 tuple 的身份及其嵌套可变模型。此前调用方对缓存的修改必须进入本次 publisher 读到的实际值。确认仍调用原方法并以确认当时的 `projection.__dict__` 计算 raw hash，保留覆写、别名和修改后确认行为；这条路径不复用帧摘要。真正提交时仍复核 hot-state 对象身份、actor revision/generation、cadence/source/rules pins，以及实际 due entries；due-index generation 不能单独充当有效性令牌。
2. publisher 在原领域读取、权限及 admission 检查所在位置完成这些检查，再从实际投影生成发布表示及帧。帧与公开事件分别拥有数据，不能共享可变容器。候选内部调用名为 `_publish_prepared_population(event, frame)`，参数直接传递本次新生成的帧，不能从 cadence_id/hint 旁表取回旧帧。冷恢复、旧 record 重建及无资格重试仍调用原 `publish(event)`。
3. bus 的内部入口复用原发布顺序：同 ID 原 canonical 冲突检查、原 pickle 快照、历史登记及淘汰，随后按 event-type、wildcard 顺序执行原路由筛选和投递。只要命中已存 ID 就弃帧，包括内部 prepared 重投；同 ID 等价事件继续从旧 pickle 重投，不能将新帧配上旧快照，tuple/list 等 canonical 相同而 Python 类型不同的输入也保持原行为。帧不改变公开事件 payload、pickle 字节、历史视图或各 subscriber 的独立 mutable event。帧只在该次调用栈内随显式注册的默认接收接口 `_handle_prepared_population(event, frame)` 传递；其他 subscriber 仍收到原单参数事件。
4. 默认 Siming 内部入口沿用原 ingress lock、冲突及成功后去重，再依原顺序执行 authority outcome、reconcile、consumer、tick 和 finish_result。只在 tick 内原 builder 的位置接入 prepared builder；builder 仍先于 selector admission。owner receipt/organization 替换投影及 schedule-gated 领域调整先按原逻辑完成，随后才生成属于最终 read-set 的表示，不能直接以 publisher 行签署 read-set。
5. world 确认、receipt/checkpoint 和审计仍由 owner 按原事务同步写入。公开 projection API、任意可变 payload 输入以及冷恢复/重试入口继续原行为。候选不改变 world 缓存为每次返回新副本；需要为独立消费者物化对象时，维持原消费者隔离语义。

帧的拥有者依次为 publisher 的当前调用、bus 当前投递、Siming 当前 tick；无阶段保留上一阶段的可变对象。publisher 只从本次当前投影建立帧，bus 仅在首次发布时将它绑定本次新生成的快照，Siming 仅在对应实际事件的默认构造链中消费。绑定的依据必须是生成及传递过程无可变逃逸且实际内容相同；单靠对象身份、配置名或摘要参数不够。原型需记录这些具体创建和逃逸入口，缺少所有权证明便不能进入快路径。

这是新的跨组件内部合同。内部方法名为候选名称，不是新增公开 API；与现有覆写、回调或注入入口发生冲突时回退，不绕过该入口。

## 安全复用与回退

仅复用与原算法生成的当前语义对象绑定的不可变表示。public mutable 模型或事件经过任意可修改回调后，build 阶段的 pins 不能证明当前内容仍等于早先内容。

选择明确限定为：world 公开缓存及确认原样保留，publisher 从当前实际返回值建立独立帧，默认内部链只消费自身拥有的不可变输入。不存在“公开 API 每次返回新副本”的分支，也不加入每次重新遍历任意可变对象的通用资格器。完整帧创建、类型及 pins 检查、物化和回退成本计入整链。

不能只比较对象 id、Pydantic frozen 标志、dict 相等、早先摘要、字段数量或私有 hint。资格必须覆盖实际绑定的方法和对象，不能仅检查 class 名称。自定义/被覆写的 publisher、bus、consumer、builder、policy、world/views、可修改输入的 outcome/reconcile 等回调，扩展 Any/serializer/copy hook、pin 变更、恢复替换、无对应帧或签名不符，均执行原路径。

具体弃帧入口包括：发布事件或帧的源对象交给可修改的扩展回调；subscriber 注册变化使默认接收路径不再闭合；任何同 ID 重投或 durable 重建；owner receipt/领域调整不符合已覆盖结构；异常、中止、取消、窗口结束或恢复替换。帧不会跨这些入口继续复用。world 公开 API 的后续修改不重写已发布事件快照，确认继续读取实际公开缓存。资格不足不是接受输入或修改拒绝原因的理由。

重试保留两个独立语义：后续 subscriber 失败后，bus 重投事件，已成功 Siming 按原成功去重返回，不重复副作用；Siming 自身失败时不得登记成功去重，重试必须允许再处理。帧登记或释放不得提前改变任何一个去重节点。

原有覆写/测试注入仍需生效。不能以“这是默认配置”为由屏蔽已有回调、故障注入、复制失败、SQL trigger 行为或异常回滚。不得全局 patch deepcopy、json、Pydantic、进程优先级或环境配置来满足资格。

## 字节与持久化

各阶段仍使用原 JSON 选项和规范。publisher 从原模型的当前 typed dump 建立发布行，保留原投影排序、record digest 及事件字段。read-set 的输入必须是 builder 最终投影，包括实际 owner receipt 替换和领域调整；其 typed dump、cadence+projection canonical ASCII JSON 独立生成或逐字节证明相同后复用。world raw Unicode JSON 始终走原算法，不计为可删除工作。

若尝试复用 JSON 片段，必须以结构化编码器生成完整片段，明确对象字段/数组排序、空数组、边界逗号和 ASCII/Unicode 选项，并逐字节与原完整编码比较。只复用阶段及实际最终行相同的完整片段，不能跨 raw/typed 规范复用。不得通过替换字符串、固定旧摘要、省略领域行或静态改报告证明等价。

持久 schema、事件/outbox/审计完整内容、FULL 和确认顺序不变。保留两个独立合同：fixture 每组最多 16 人的事务，以及 publisher 每 16 个 stream revision 写入完整恢复 checkpoint 的原规则和原恢复 tail 限制。不能将公开事件列表截短，也不能移动 fixture 出计时。恢复路径从原 durable facts 重建，不依赖帧幸存；进程硬退出不能改变恢复结果。

## 收益预算

同轮千人 cadence 独占观测约为：world B0/preview 合计 6.94ms，publication typed dump 2.87ms，read-set typed dump 2.82ms，read-set JSON 5.29ms，publisher JSON 5.90ms，world JSON 5.11ms，B0 校验/delta 4.34ms，bus 未进一步细分部分 6.67ms。

这些是阶段探针下的路径时间，不是全部可删除的工作，也不保证全部属于 B0 或能被帧复用。world B0/preview 和 raw JSON 明确保留，原 bus 快照及消费者隔离也保留；不能把上述时间相加当作预期收益。模型/字节创建、资格检查、公开物化和缓存保留均可能抵消节省。当前尚无证据证明本方案能补足约 25.5ms 缺口；先以完整默认链原型确认净收益，再决定是否进入生产实现。

首先证明收益来自减少重复表示转换，而非删检查/输入、改事务、过早失败、未完成工作或测量移动。单个函数快和微基准通过都不能签署整链性能。

## 验证与停止门

设计获批后先编写实施计划，列明原型、差分检查、停止门和有条件的生产步骤，按项目流程确认计划及执行方式。首个实施步骤是 private 链的有限整链原型，留在仓库外诊断范围；产品默认行为尚不切换。原型由冻结输入驱动，并记录完整创建、资格、转换、回退、公开物化、确认和清理成本。

差分覆盖真实 30 窗的每窗结果、原 typed/raw/canonical 字节、B0 deltas/stats、审计、Gameplay 六表和 cold reopen。raw Graph 比较若受真实时间/UUID影响，须另列差异来源并保留原值，不能擅自归一化后称完全相同。必须覆盖重试、dedup/conflict、所有消费者隔离和回调顺序；特别覆盖后续 subscriber 失败后重试、Siming 自身失败后重试，以及 Unicode B0 与有效 owner receipt 同时出现。

必须先有 RED 反例，覆盖公开嵌套变更、False/0、tuple/list、Unicode、非有限数、Any、自定义 hook、pin 改变、取消及同 due tick revision 更新、恢复替换热表、复制异常、写入失败回滚和硬退出。每个反例由原实现确认预期，再验证候选执行原行为或真实回退；只测试 hint 不能锁定边界。

正确性通过后运行三个交替顺序的同输入完整 owner 配对；每对都有一致的行为和持久化证据，全部成本入计时。候选需三对均有收益、平均减少至少 5% 完整 owner 时间；这只是进入生产实现的筛选门，不是性能合同。失败不靠增加次数盲重试，也不把不显著收益叠成通过。

整链原型合格后才执行计划中的生产步骤，覆盖明确的组件内部接口、测试、生命周期和回退；没有新增用户设置、无界缓存或通用兼容层。

生产实现后先受影响回归、短测试，再冻结候选源码：完整 pytest、population-runtime-correctness/change-lifecycle、原 100/1000 人 ten_x 各 30 完整窗及原 verifier。涉及存储/内存保留的路径后，完整两小时真实 provider 再验收。需要重跑容量时仍为原 600 秒；6a 旧四局完成不会签成新提交通过。all 的 Godot 暂停及 Archive Door/VLA blocker 独立报告。

只有最终原性能和完整性均通过、报告及证据完备后，才处理 main 集成和推送。既有原机器失败不改写，不把本机结果声称原机器已修复。

## 清理与当前边界

仅清理本轮拥有、结束且已导出的临时资源。删除失败先盘点并移动至新独立归档、逐文件 hash 一致后标记 archived_cleanable；不能安全归档时保存实际路径/错误并标记 cleanable_in_place。旧证据、用户数据和共享缓存保留。

当前没有生产帧、原型、产品依赖、进程池或新的验收通过。此稿待用户审阅；Goal 保持原完整目标，尚未完成。
