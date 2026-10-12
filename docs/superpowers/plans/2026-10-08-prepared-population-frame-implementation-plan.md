# 默认人口发布链单窗片段实施计划

Status: implementation_in_progress

用户已要求继续优化并实施计划 A；本计划落实现有性能 Goal 的默认链表示复用，不扩大角色规则或 Godot 范围。约束沿用 2026-10-04 不可变帧设计与 9/18 主线计划 A。原设计文件的旧 awaiting-user-review 记录不覆盖后续授权。

先验：仓库外 K 原型的最终 34 项有限回归、百人/千人各 30 窗字节 oracle 和 cold audit 通过；三组完整 owner 均改善、平均 5.246196%。最终约 118.6ms/窗仍超 100ms 周期；不是正式通过。原型源码和证据见 D:/ParallsEvidence/paralls-graph-difference-20261008T051404Z。

## 约束

- 原公开 mutable event/projection、native pickle 快照、subscriber 隔离、路由/顺序、同 ID 冲突、成功后去重与异常后重试保持。
- 原 typed/ASCII canonical digest 与 world raw digest、fixture 28 人/每事务 16 人、checkpoint 每 16 个 revision、FULL/WAL、单 owner 和持久确认规则保持。
- 帧只含 bytes、builtin 标量和 tuple；只供本次 fresh 首发的明确内部链，不能从 event hint、cadence ID 缓存或外部配置自签来源。恢复/同 ID 重投及修改输入的扩展走原路径。
- 原 publisher/bus/consumer/runtime/builder、JSON-mode serializer/validator 和 codec 绑定被覆写时按其实际入口回退，不能用全局 patch 作为生产接线。
- Goal 仍包含原两档 10×、owner 长尾与 RSS；A1 后端合同、旧两小时/容量通过和本轮帧开发分别记账。Godot/all 暂停，Archive Door/VLA 独立 blocked。

## Task 1：生产首发与重投合同

Produces: backend/tests/test_population_prepared_delivery.py。

先用真实 WorldContinuityRuntime/DurableGameplayEventStore/RuntimeCadencePublisher 和 InMemoryAuthorityEventBus 写 RED：首发内部接收者取得不可变片段；其他消费者和历史副本独立；后续消费者失败后重投不重用旧帧；dispatcher/codec/变更入口原路径生效。

Expected: 原实现缺内部片段投递，行为测试失败；实现后所有新测试及原 bus/dispatcher/durable cadence/domain 回归通过。

## Task 2：生产者来源、不可变片段及显式 bus 交付

Consumes: Task 1 原接收和重投合同。Produces: private PreparedPopulationFrame、实际 native JSON dump 的单次来源捕获；publisher 本次首发传入 dispatcher 的明确发送函数；bus 内部 fresh 发布和受信接收入口。

保留原 _digest 异常/摘要顺序与公开 publish(event)。只复用原 native JSON-mode 完整行的字节，不递归重扫万人 Any 树，不将 raw/typed 编码混用。帧随本次调用栈传递，重试/异常清除；bus 保留原 pickle/存储/淘汰/独立 decode。

Expected: bytes 与原完整编码一致；同 ID 原快照重投，任意单参数 subscriber 不继承帧；原单参数入口与故障回调生效。

## Task 3：Siming 默认装配和最终 read-set

Consumes: Task 2 同窗片段。Produces: pipeline 内部接收入口、单次 builder scope、main 原 handler 的对应内部注册。

沿用原 handle_event ingress lock 和成功去重；原 outcome/reconcile/consumer/tick/finish 顺序不改。只有原闭合绑定且实际事件未受调整才复用；owner receipt/plan/schedule-gated 调整、未知转发和覆写回退。共享上下文只允许最终 builder 消费一次，不泄漏至 finish/output 回调或嵌套发布。

Expected: 新旧 canonical、typed 值/别名、审计与副作用相同；K 五项反例和原 Unicode/非有限数/Any/serializer/copy/重试/故障/恢复边界通过。

## Task 4：收益、正式验证和集成

Consumes: Task 1–3 最终代码。先做 focused 回归、完整 owner 对照与 30 窗字节 oracle；所有新成本计入。无收益或不等价则修正/停止具体候选，不降低验收门槛。

冻结源码后运行完整 pytest、population-runtime-correctness、change-lifecycle、原两档 ten_x 各 30 完整时钟窗/原 verifier。涉及保留/内存后仍需真实 provider 完整 7200 秒；必要容量复验为原 600 秒。Godot/all 按用户暂停明确 not_run；阻塞独立报告。

Expected: 只有原完整性/性能窗口均通过、报告及证据完整后才处理中文提交与 main cherry-pick/推送。原机器失败不改签。每次运行导出仓库外独立证据，结束后仅清理本轮 owned TEMP/进程，失败归档标记可清理。

## 执行记录

Pre-flight: Task 1 锁定 Task 2 的 fresh 帧及回退；Task 2 的显式单窗交付由 Task 3 消费；Task 3 的最终 read-set scope 在 Task 4 实际 owner/正式窗口内验收。无跨 task 公共 mutable 缓存。

Ruling: 沿用已有隔离候选 worktree 和仓库外 evidence ledger，不新建另一工作树或提交中间步骤；用户已要求最终完整验证/报告后才提交推送。代价是未提交开发状态需额外保存 source/diff 快照。

本轮执行证据：D:/ParallsEvidence/paralls-prepared-production-20261008T063003Z。任务仅凭实际测试/验收更新，不预先勾选。

Task 1–3：生产发布来源捕获、dispatcher 首发交付、bus 内部接收、pipeline/builder 单次消费和 main 原 handler 装配已实现；最终 focused 为 135 passed/6 warnings，退出 0。原 cadence dump 的求值顺序、实际 codec、快照 getstate/setstate、dispatcher sender 和 SimingInput 构造器五类具体缺口均有 RED→GREEN；公开 mutating event-type/wildcard 转发、覆写 parser/实例 validator（含执行中恢复原绑定）、九类 JSON-mode 规范化与异常/重投回收保持原路径。有限边界通过不证明任意动态扩展等价。

Task 4：生产源码摘要 sha256:ee30b167fad3168dfcf2da0b0724136d0f3675fe2b6d4e7167d3de5a96b2fb6d。百人/千人各 30 手动 owner 窗的字节、typed read-set 和 cold audit 一致；实际生产分支不使用原型 installer。三组千人交替对照均改善，平均 9.801715%，候选 128.2–129.9ms/窗仍超 100ms 周期。对照为同一冻结生产源码关闭片段编码的控制组，不冒称旧提交源码；oracle 和固定输入组不参与性能筛选。全量回归、原 correctness profile、完整时钟窗以及 Graph 原始表对照继续逐项取证。

Ruling：capability 中仍存在的 dump 是筛选后决策读集的原编码，不能仅凭总调用数称为全人口重复编码或删掉。此前测试期待总计 1 次是错误定位，改为保留发布/决策编码合计 2 次及 builder 片段消费 1 次；不改变任何验收性能阈值。

Ruling：原 require_formal=True verifier 要求 live 且干净提交；用户要求完整验证/报告后再提交。未提交候选先用原完整窗口与 require_formal=False 计算原 integrity/performance，另记严格正式入口的 dirty-source 阻塞，不改 verifier、不伪造 clean/source 或 passed；干净提交下最终正式验收仍须独立完成。

冻结前另补实际 AuthorityEvent 构造器及执行中恢复原绑定的两项 RED→GREEN：构造调用前后记录原 init/new/SchemaValidator 的资格，不以返回后恢复原绑定补签。最终 focused 为 137 passed/6 warnings，运行时源码摘要更新为 sha256:d9dc86e8f0c4d47e7e3fffee54e196818bda32fec007964ed2cc20352a28415c。上一段 9.801715% 只属于 ee30b167 的中间版本；最新源码收益、Graph 对照、全量及完整时钟窗口在新目录 D:/ParallsEvidence/paralls-prepared-final-20261008T071624Z 独立采集，旧结果不改签。

该 d9dc86e8 版本全量为 7716 passed/2 skipped，两个历史 spawn 超时测试在完整顺序下通过；两档各 30 窗 oracle、固定输入五个 SQLite 原始库事实对照通过。性能对照第二组与上一阶段清理/封存重叠，算术结果 11.610990% 不作为净收益结论，原数据保留。

独立最终审查提出两项已由 RED 复现的缺口：dispatcher 扩展 transform/sender 执行中恢复原绑定会给变更事件携带旧帧；个人 continuity_delta 未拒绝参与策略禁止维度与 group_summary_only 字段。修复记录实际执行的两个回调并在 finally 恢复嵌套交付上下文，个人增量接纳按 module.field 及字段策略拒绝。相关 106 项回归通过（随后合并重复 sender 参数，只保留三个不同回调场景）。新源码在 D:/ParallsEvidence/paralls-prepared-review-fixes-20261008T073958Z 重新冻结、独立测量及完整回归；不能沿用 d9dc86e8 的结果签署新版本。

后续优化次序：先量化完整 owner 的实际热点及 FULL 提交长尾；只消除同一窗口内已证实重复的表示转换。A1 on-demand frame 尚无批量业务消费者；共享 read-set 每批验证一次需待真实消费者接线后证明，当前不增加猜测性批量 API。A2 成员账本、A3/A4 接纳/读取及 AM1/A5 集成按原计划继续，不以单窗片段或局部回归宣称计划 A 全部完成。

审查修复版本 4ab907b0：focused 133 passed，全量 7725 passed/2 skipped（两个历史 spawn 测试在全量通过）。原生三组独立 owner 对照平均改善 5.248236%，候选 122.3–127.0ms，仍超周期。第一组 CPU 均值 120.8ms 接近 wall 127.0ms，fixture/cadence 分别约 40.4/86.6ms；不能把本机根因直接归为 SQLite 同步等待。

原 MixedWindowProbe.install 包装 publisher.__call__，按闭合资格合同会回退，因此不能用该包装器测量帧收益。新增真实 main/lifespan 反例先确认发布绑定被替换；适配后 attach 读取默认 driver 闭包的实际 publisher，保留原单调时钟、tick 前后计时、fixture、负载和阈值。相同测试同时要求首窗真的消费帧且 digest 与原算法一致，避免只移除包装却漏采样。适配后按受影响测试、correctness/change-lifecycle 与完整原时钟窗重新验证，证据在 D:/ParallsEvidence/paralls-mixed-observer-20261008T080015Z。
