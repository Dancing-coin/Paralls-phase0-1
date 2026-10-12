# 人口剩余性能修复实施计划

> 执行：沿 superpowers:test-driven-development 逐项实施；独立诊断使用 native subagents，主代理集成并执行统一验收。

**Goal:** 在原合同下修复 10× 吞吐和两小时 RSS/lag，四局最新本机验收标记完成。
**Architecture:** 沿用单 owner、现有事务和恢复结构，只减少实测重复工作；未知增长来源先采样。
**Tech Stack:** Python 3.13.9、SQLite 3.53.4、Pydantic、pytest、原 harness。
**Spec:** docs/superpowers/specs/2026-10-02-population-performance-closure-design.md

## 全局约束和审查

保持 28 人 fixture、16 人事务前缀、FULL、幂等/CAS、返回及跨字段隔离、checkpoint 哈希/损坏拒绝、owner 唯一写者及恢复；不通过改变输入、计时、门槛或周期重启取得通过。秘密只留在进程环境，诊断不记录 locals 或明文配置。

## 可独立验证的任务

- [x] 1. 记录干净 6a 基线和四局完成证据；创建独立仓库外证据目录与进度。
- [x] 2. 第一批 10× 热路径候选：静态合同、持久批次快照、Organization 私有 batch 更新已分别 RED/GREEN，返回隔离与哈希一致；完整 owner 对照 186.615→170.675ms。仍超 100ms，此项只表示候选实现与诊断完成，正式 10× 修复见第 6 项。
- [ ] 3. 内存：用仓库外诊断脚本驱动原 runtime，取得阶段 tracemalloc 差值和 RSS，核对保留引用/native 分类。定位后只修改所属模块；回归必须复现真实保留模式。
- [ ] 4. 写入长尾：在仓库外重放/采样脚本测量 native SQL、graph/session 持久化及 owner 排队；确认根因后最小修复。原子提交、失败闭合和硬退出恢复必须有 GREEN 证据。
- [ ] 5. 集成审查：受影响回归、全量 python -m pytest -v、原人口 correctness/change-lifecycle/all，保持每项退出码与完整原始输出。
- [ ] 6. 短测通过后冻结提交：原 100/1000 两档各 30 个完整 10× 窗，千人 1× 两小时真实 provider 原验收及离线复验。必要时覆盖原三十分钟档和受影响容量合同。
- [ ] 7. 报告每项通过/失败/阻塞及证据；清理本轮拥有资源；diff/check/status；验证与报告完整后中文提交、cherry-pick 合入 main 并推送，核对远端 SHA。只有原目标达成才 Goal complete。

证据根：D:/ParallsEvidence/paralls-performance-closure-20261002T032000Z。上一轮及原机器记录不覆盖。

## 当前验证记录

第一批候选全量回归（重角色归档分页和同窗 stream 去重之前）：7561 passed、2 skipped、19 warnings，788.27s，退出 0；两项真实 spawn 顺序回归均通过。证据：pytest-full-final-candidate。

第二批仅处理已定位工作：同窗组织 stream-head 查询去重已通过 47 项回归；重角色全史正文瞬时 list 已改为固定前缀分页，143 项相关回归及最终 9 项分页回归通过。只 sanitize 而跳过 typed fold 的快捷路径已由损坏数据 RED 否定并撤回，保留原 actor/confidence 等拒绝语义。最终源版本需统一重新验证；不能将局部峰值或旧候选全量通过重签给最终版本。

最新原 collector dirty 候选诊断：两档 10× 各完成 30 窗且完整性通过，仍分别 backlog 9/22、性能失败；千人 1× 30 秒完整性及性能子检查通过，实际只有 2 次 qualified provider calls，每类 scheduled live_tasks 为 0，first_three_live_tasks_passed=false。原 verifier 对 seconds<180 豁免此项，不能据此声称每类前三任务真实调用通过。全部独立保存 source-before/after 与原日志，仅为短诊断；两小时及正式 10× 尚未通过。SQL 拆分探针自身高开销，仅用于查询数量/调用链，不据此宣称原生 I/O 占比。

最终审查发现 typed SQL 类型过滤可能隐藏正文 correction；三个真实 SQLite RED 已复现。已增加仅保存身份异常行的 partial index，并通过旧库重开、范围边界、损坏 JSON 保留和查询计划回归。最终统一全量 pytest 为 7577 passed、2 skipped、19 warnings，767.50s，退出 0，源码前后身份一致；两个历史 spawn 用例在全量原顺序中均通过。证据为 pytest-full-third-candidate。正式 profile 与性能复验仍待冻结提交后运行，all/Godot 按用户要求暂停。

## 冻结 54021f63 的正式结果及下一项

54021f6367cc76613eb0f474dd01abfe20fc46c5 的 correctness/change-lifecycle 和真实 provider short 已通过；两档 10× 各 30 完整窗口仍性能失败。千人 1× 完整两小时原 verifier passed，7200 窗、max lag 0.8851177、backlog 0；owner/paired RSS 增长 23.86/25.78 MiB，均低于原 32 MiB 门槛。完整性、故障恢复、真实 provider 每类前三任务全部通过。上述结论绑定 540 提交，不能重签到下一项修改。

下一项仅将既有 Gameplay runtime 页缓存上限 256→2048 KiB，不增加配置项或依赖。原 FULL、WAL、16 人物理分组、后台 checkpoint、幂等/CAS/同步确认保持。此前 12 组新进程配对全部严格 SQL 正文、快照、冷恢复和 FULL 提交一致；千人 2048 候选完整 owner 配对中位改善 31.117ms，3/3 改善，但仍约 146ms，不能宣称 10× 通过。该有界缓存调整用真实同输入前后对照和现有存储/恢复回归验证，不增加只复述常量的测试；需要新源码正式窗口及长时 RSS 复验。证据 io/cache-54021f63/cache-conclusion.md。

多行 VALUES 因变慢及 trigger changes() 行为变化被否决；Zstd 完整 owner 收益有限、千人 1/3 变慢且数据库扩大，未进入生产。Godot/all 继续暂停，1800 秒两档矩阵未在本候选运行，Goal 保持 active。

2048 KiB 候选的现有存储、持久 cadence 恢复、组织 due、返回隔离和 WAL checkpoint 回归已通过：69 passed、2 warnings，5.74s，退出 0、source_unchanged=true。证据 cache-2048-regressions；下一步全量回归和对应源版本复验，尚未据此关闭 10× 或长时 RSS 门禁。

2048 KiB 候选全量 pytest 已通过：7577 passed、2 skipped、19 warnings，792.75s（wrapper 794.042823s），退出 0、source_unchanged=true；两项历史 spawn 顺序回归均通过。证据 cache-2048-pytest-full-candidate。冻结本地提交用于原合同 fresh 采集；未集成或推送 main，新 short/10×/长时性能状态以对应新证据为准。

## 单 store 正文复用候选

冻结 caee8f3e 的两档正式 10× 仍失败。重新按原始 clock windows 复算，千人 fixture+cadence 平均 140.7306ms，三十窗工作合计 4221.9175ms，超过原三秒窗口 1221.9175ms；即使窗外工作为零也超预算。百人平均 95.1511ms，仅剩 4.8489ms，第二窗前有 34.392ms 窗外间隔，不能把该间隔全部归因于 IPC 或 SQL。证据 formal-window-headroom-caee8f3e.json/.md。

原压缩字节重复解码已实测；有锁、2 MiB/512 项 exact bytes→exact str LRU 外部完整 owner 两档各三对，SQL 正文、冷恢复、每模型/阶段 JSON 校验次数和 FULL 提交严格相同。千人配对 owner median 改善 4.177ms、百人 1.913ms，均 3/3；千人一对 p95 变差，末 RSS 增加约 3.6–4.4MiB，不能据此关闭长时门禁。simplejson、ASCII bytes 已否定；没有引入全域 circular=False、模型缓存或新依赖。

下一候选仅在 DurableGameplayEventStore 内复用不可变正文，每次仍实际 SQL 查询和 Pydantic 校验；按原 RLock 保护，预算计正文/字节对象及保守节点开销，关闭清空，非 exact 输入及失败走原 codec。事务回滚后正文缓存不生成事实，离线审计和快照仍用原 codec。七项新增回归先 RED；受影响存储、恢复、故障和验证入口共 205 passed、6 warnings，40.53s，退出 0、source_unchanged=true。证据 decoded-json-cache-storage-green-with-verifier。首次 GREEN 的关闭异常断言误把外层 row_invalid 当成 closed，修正为检查原原因链；后端独立收集另有三个旧 verifier common 导入路径失败，原日志均保留，包含正常验证测试集合的重跑通过。

当前只表示最小候选与受影响回归完成；全量 pytest、实际生产完整 owner 对照和本版本正式 profile 尚待执行，不将 caee/540 证据重签。Goal 保持 active；Godot/all 按用户要求暂停，历史四局 600 秒通过继续绑定 6a。

单 store 正文复用候选全量回归：7584 passed、2 skipped、19 warnings，807.85s（wrapper 809.3482126s），退出 0、source_unchanged=true；两个历史 spawn 顺序用例通过。证据 decoded-json-cache-pytest-full。全量期间墙钟与 monotonic 差值 0.10256s 已记录，源码未变化。新增七项回归文件 SHA-256 为 bd6b083e37df7bebe427e08b262138081a823efa37483b3dde5a4747a28780b9。冻结本地候选以绑定下一轮实际生产 owner 对照和正式 short/10×，本次没有合入或推送 main；本候选长时 RSS、完整 profile 仍待对应源码复验。

## 兼容压缩编码器候选

755e 的完整千人 1× 7200 秒已通过，owner/paired RSS 增长 27.06/27.43 MiB，实际真实 provider 窗口与恢复检查通过；两档各 30 个完整 10× 仍性能失败。新候选不复用这些报告签通过。

固定九轮完整 owner 对照：三组 stock/ng1/ng2 顺序事前固定，ng1 的三组净收益为 2.602/11.403/7.006 ms/窗，均值 7.004；ng2 两组回退，不采用。Gameplay 六表旧 decoder 读出的原始 UTF8 正文及所有标量、schema、逐窗结果、冷恢复、每模型校验次数、FULL 提交次数全部相同。其它账本原始 UUID/时间戳差异只作观察，不以归一化报告伪造字节相同。ng1 正文 +26.56%、数据库 +13.84%、末 RSS 增量三组约 -1.43/2.84/0.32 MiB；第一组 owner p95 回退 5.70ms，其余改善 19.32/6.97ms。九轮诊断均非正式验收。证据 io/zlib-ng-round2-755e/matrix-analysis.json。

本候选仅替换普通 exact str 的压缩编码为 zlib-ng 1.0.0 level1，保留 v1 前缀、stdlib decoder、自定义 str.encode 路径、原 JSON 原文、SQLite FULL、WAL、缓存预算、失败顺序、CAS/恢复和所有输入/阈值。正式环境只从已固定 SHA 的本地 wheel 新增此依赖，其余版本没有变化。已有原正式 10× 失败是性能 RED；新增九项 codec 互操作/损坏/混合账本回归先验证既有语义基线，再验证候选，不增加时序脆弱或仅复述常量的测试。初次 pytest 参数名过长的 Windows 错误日志原样保留，修正仅用例 ID，输入不变。

下一步：受影响存储/硬退出回归、全量 pytest、实际生产 owner 配对；冻结本地提交后运行原 correctness/change-lifecycle、short、两档正式 10×，并在需要时对应源码完整长时复验。只有原合同通过才能关闭性能 Goal，不因三组改善或成功采集宣称 10× 修复。Godot/all 仍暂停，没有合入或推送 main。

## 成熟存档诊断暴露的初始化父进程丢失

802 的完整两小时 RSS 已低于原门槛，但两档 10× 和稳态 lag 仍失败。成熟存档的隔离副本还复现另一项生命周期缺陷：原启动过程同步排空历史 outbox，父进程退出后 watcher 只设置事件，正在初始化的 owner 仍可持有原存档锁。该缺陷不能解释或替代稳态写入长尾，不能据此关闭第 4、6 项。

最小修复仅在已有 watcher 判定 spawn parent 死亡且 startup 尚未完成时退出子进程，交由 OS 回收 lease 与 SQLite 未提交事务；活 parent、startup 完成后的正常 STOPPED/feeder 路径保持。回归使用原真实 spawn/main/owner，检查 FULL/WAL、已提交数据保留、未提交数据回滚、锁释放和正常活 parent 关闭。死亡信号为受控跨进程状态门，实际测试父进程仍存活，不能写成新测试实际杀死 OS parent。

- [x] 8a. 原源码 RED 在进入真实 owner 后五秒仍存活；修正清理门后的重复 RED 同样失败，退出 1。首次 GREEN 夹具的 Event 清理等待已死 waiter，经真实调用栈定位后仅改为 semaphore；该中止证据保留，不记为通过。
- [x] 8b. 独立只读审查未发现 P1/P2；42 项受影响回归通过，退出 0，25.17s，源码未变化，包括两个历史 feeder 回归。
- [x] 8c. 全量 pytest 7595 passed / 2 skipped / 19 warnings（784.97s）和原 population-runtime-correctness 均通过，退出 0，源码未变化；按代码内容身份本地冻结，不合入/推送 main，不将 802 的性能报告重签到新候选。

仓库外新增真实 OS parent 退出诊断：受控死亡门始终 false，实际 parent 退出 0、owner 退出 1；没有 ready/STOPPED，lease 可重获，已提交前缀保留、未提交事务回滚。退出请求信号至两个进程均终结为 43.70ms，不是独立测得 OS parent 死亡至 owner 响应的延迟。独立复核未发现 P1/P2。完整原始记录、源码/日志 hash 与报告见 io/startup-parent-death-802c/verification.json；全量/profile 执行于 dirty 802，冻结前后的代码内容须逐文件比对，不能静态改写原报告 revision。

证据位于同一外部根的 startup-parent-death-owner-red-r2、startup-parent-death-owner-green-r2 和 startup-parent-death-owner-green-py-spy。清理仍只处理本轮 owned 副本；不能删除时归档标记 archived_cleanable，移动失败则原位标记 cleanable_in_place。
