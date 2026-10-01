# 人口运行热路径优化

Status: execution-active

授权：用户在四项优化方案后要求“优化上面的点，作为 goal 实现”。本设计记录已确认的局部优化范围，不新增业务行为或接口。

## 目标与约束

减少事件写入 schema registry 的重复导出/序列化、记忆召回的复制/排序和人口检查点的序列化往返；通过分阶段测量定位四局同时长尾，只保留有证据支持的优化。

保持事件顺序、schema 更新、幂等、CAS、事务回滚、返回数据隔离、必需记忆失败闭合、canonical digest 和冷恢复行为。保留现有 16 窗完整检查点、输入 fixture、FULL durability 与原 verifier 门槛。Python 3.13.9 / SQLite 3.53.4；不增加依赖。Godot 暂停，Archive Door 和 VLA 的原阻塞仍独立存在。

## 方案

1. registry 快照只在注册集合改变时重新构建/序列化；持久化状态只在事务提交后成立，分组回滚及重开必须一致。优先将复用限定于不可变 schema 身份。
2. 召回对原始条目只读评分，最终输出才复制；以标准库有界选择替代全量排序时，必须保持稳定 tie、缺失必需 refs 的顺序、别名隔离及 token 截断语义。先独立验证复制优化，再测量 Top-K 收益。
3. 用等价模型验证减少 JSON 往返；JSON/Python 验证差异通过实际 schema 检查。保留正式 canonical hash、损坏拒绝、checkpoint 原子性和恢复等价。
4. 分别定位 fixture、append、commit、checkpoint、发布/确认与 owner 等待的耗时。四局同步停顿尚未归因，不能预先改变 checkpoint 周期、并发或 writer 所有权。

## 完整复验后的局部修正

第一轮候选 e26d0e19 的正式窗口已完整结束：两局容量通过，四局同步提交长尾、10× 累计落后及两小时 RSS 增长仍失败。物理盘排队与四局提交等待相交，但没有唯一底层根因证据；微基准收益不保证正式门槛通过。

继续删除两处可直接证明的重复工作：新建 transactions 表只保留命名唯一索引，已有库不重建或删除索引；每个 Siming provider 惰性持有锁保护的 SSLContext，沿用 HTTPX 原信任环境规则，保留每请求临时 Client 的关闭和隔离。首次成功构造后 CA 环境变更在 provider 重建后生效，不引入跨实例 context 或长寿命连接池。

验收 WS 客户端在 resync/subscription send 阶段遗漏既有受控关闭恢复。发送阶段沿用 recv 的精确关闭码 4403 和原因 mirror_delivery_unrecoverable；其余关闭继续失败。重绑仍需新 epoch、实际基线与最新 tick 证明，原预算和暂停合同保持。第一轮失败请求没有关闭码证据，不能宣称已确定其原因。

## 验收

每项具有同输入的前后微基准与必要语义回归；新增回归先确认旧实现失败，性能数字不作为易抖动单元测试阈值。集成后冻结源码，执行全量 pytest、相关人口 correctness/recovery profiles、change-lifecycle 和 all；all 的 Godot 阻塞单列。

短测通过后按原合同采集：100/1000 人各 30 个完整 10× 窗，1000 人 1× 完整两小时，2/4 局各 600 秒，以及 soak 矩阵原有 30 分钟档。使用项目 .env 的真实 provider，仅记录配置名称/timeout，绝不导出凭据。新证据在仓库外独立目录，原机器与上一轮失败保持不变。只有新原始证据及离线复验才支持通过声明。

源码和证据完成后才整理中文提交及推送 main；提交前 diff/check/status 和 .harness 实际产物检查，推送后核对远端 SHA。只清理本轮拥有且已导出的临时目录和进程。
