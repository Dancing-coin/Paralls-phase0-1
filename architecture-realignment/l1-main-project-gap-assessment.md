# L1 Main-Project Gap Assessment

这份文档把主项目《开本 / Paralls》里对 `L1` 层的定义，与当前 `paralls-phase-0-demo` 仓库里的实际实现做一轮对照评估。

目的不是重写主设计，而是回答三个工程问题：

1. 当前 demo 仓库里的 `L1` 到底做到哪一步了
2. 哪些地方已经对上主项目方向
3. 哪些地方还只是最小骨架，距离主项目定义还有明显缺口

## 对照基线

本评估主要对照这些主项目文档：

- `D:\Projects\Paralls\docs\phase1\core\00-总纲\Godot源码底层基础设施与运行时约束.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\01-事件总线总纲.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\04-感知链路与候选事件设计.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\07-视觉事实系统接入总线规范.md`

## 一句话总评

当前 demo 仓库里的 `L1` 已经达到：

- **方向正确**
- **边界基本正确**
- **跨边界事实出口已成立**
- **最小低层状态投影已成立**

但还没有达到：

- **完整 Phase 1 `L1 -> 候选感知 -> Per-Character 过滤 -> 角色感知` 主链**
- **多感官候选层**
- **大规模 fact family 覆盖**

所以当前判断应是：

> 它已经是一个成立的 `L1` 最小骨架，但还不是主项目完整定义中的成熟 `L1`。

## 对照表

| 主项目要求 | 当前 demo 实现情况 | 评估 |
| --- | --- | --- |
| `L1` 是本地高频具身执行器、玩家输入终端、原始世界事实生产层 | Godot 端已经承担本地输入、场景采样、事实发射和本地表现桥接 | 基本达到 |
| `L1` 不是角色认知宿主，也不是世界真值解释层 | 认知推理没有下沉到 Godot；事实进入 backend 后再路由和投影 | 基本达到 |
| 原始骨骼/表情高频流不跨边界，跨边界的是结构化语义事实 | 当前跨边界主路由是 `raw_fact_event`，承载 `visual_fact` / `spatial_access_fact`，而不是骨骼流 | 已达到 |
| Godot 侧应有明确跨边界事实出口 | 已统一到 `FactEnvelopeBuilder.gd` + `RawFactEmitter.gd` + family emitters | 已达到 |
| 视觉事实系统本体归属 `L1`，总线接收的是结构化视觉事实 | `VisualFactEmitter.gd` 已变为 shared raw-fact 路线兼容壳，`visual_fact` 进入 backend authority 路线 | 已达到 |
| `L1` 事实需要进入后端权威叙事/事实总线，而不是留在 Godot 本地当真值 | 当前事实进入 backend `main.py -> fact_router -> handlers`，并参与 runtime projection / candidate / Siming | 已达到 |
| `L1/ESM` 应产出可工程化的候选事实，而不是直接把世界塞给角色 | 当前已能产生低层事实和部分 relationship candidate，但主链只覆盖了很小子集 | 部分达到 |
| 候选感知层应承接视觉事实、听觉事实、空间关系事实等 | 当前只比较像样地覆盖了视觉事实和空间接入事实 | 部分达到 |
| 角色默认不直接消费全局原始事实流，而是消费过滤后的角色私有感知结果 | 当前 repo 还没有完整的 `Per-Character` 感知过滤器和正式角色私有感知事件层 | 明显未达到 |
| 会话接入、偷听、私密边界等要落入感知链，但候选层不直接做成员资格结论 | 当前 `privacy_band` / `zone` / `nearby_actor_refs` 已经进入低层事实与投影，但只到最小接入证据层 | 部分达到 |
| Godot 本地表现总线与后端权威事实总线职责必须分离 | `BackendBridge` / `LocalPresentationBus` 与 backend authority lane 已分开，职责比早期更清楚 | 基本达到 |
| `L1` 需要可 replay / 可审计 / 可调试 | 当前有 debug trace、verification audit、Phase0/Phase1 slice 报告、L1 edge runtime-verification probe | 已达到最小可审计水平 |
| `L1` 需要在 reconnect / runtime reset 下可恢复最小状态 | 现在已验证 zone reseed、privacy reseed、environment cycle、disconnect signal clean path | 已达到当前 demo 所需水平 |

## 当前已经做对的关键点

### 1. 跨边界出口已经统一

这是当前实现最重要的正面结果。

当前事实出口已经不再是多个脚本各自拼 payload，而是统一经过：

- `scripts/l1/facts/FactEnvelopeBuilder.gd`
- `scripts/l1/facts/RawFactEmitter.gd`

这非常符合主项目文档里对：

- `Visual Fact Emitter`
- `L1` 结构化事实出口

的要求。

### 2. `L1` 已经有 shared contract，不再只是零散事件

当前 repo 已经有统一共享字段：

- `effect_kind`
- `subject_key`
- `ttl_ms`

这说明现在的 `L1` 不只是“发事实”，而是已经开始表达：

- 这条事实是设置状态
- 清空状态
- 替换状态
- 脉冲型事实

这比主项目对“可工程化事实”要求更接近了。

### 3. 低层空间接入事实已经开始像真正的 `L1`

`spatial_access_fact` 这条线现在已经能表达：

- 进入 zone
- 接近 actor
- 离开 actor 近距范围
- privacy band 变化

并且这些事实已经可以：

- 投影成 backend 当前低层状态
- 在 reconnect 后重新播种
- 在 clear 丢失时通过 TTL 兜底过期

这已经不是“临时 demo 信号”，而是标准的低层接入证据层。

### 4. 运行时验证面已经比普通 demo 强很多

当前不仅有 backend tests，还有：

- `verify_phase0.py`
- `verify_phase1_slice.py`
- `verify_l1_runtime_edges.py`

这说明当前 `L1` 已经具备：

- 可回归
- 可审计
- 可复跑

的最小工程形态。

## 当前明显还没做到的部分

### 1. 还没有完整的候选感知编译层

主项目要求的是：

`L1/ESM 原始事实 -> 候选感知事件 -> Per-Character 过滤 -> 角色感知事件`

当前 repo 只做到：

- `L1` 原始事实生产
- backend 低层投影
- 局部 candidate 生成

但还没有系统化的：

- 候选感知事件层对象
- 候选感知编译器
- `Per-Character` 感知过滤器
- 正式角色私有感知事件

所以当前阶段更像：

> 完成了主链入口，但没完成主链全程。

### 2. 事实 family 仍然太少

当前真正成体系的只有：

- `visual_fact`
- `spatial_access_fact`

距离主项目中更广义的 `L1` 候选事实空间还差很多，例如：

- 听觉候选
- 嗅觉/热感/触觉类候选
- 更完整的 `object / environment / spatial_relation / evidence_projection`

### 3. TTL 只是第一条试点，不是完整时序系统

当前 `ttl_ms` 已经不是空字段，但它只真正落在：

- `nearby_actor_refs`

而且是：

- backend-local
- opportunistic prune

这对于当前 demo 足够，但离主项目里未来可能需要的更广义低层时序控制还差很远。

### 4. 角色私有世界版本还没成形

主项目文档最强调的一点是：

- 角色不应该默认看到全局同一份世界
- 必须经过 `Per-Character` 过滤

当前 repo 虽然已经开始做 runtime projection 和 candidate 编译，
但还没有真正长出“每角色独立感知裁剪”的完整层。

## 成熟度判断

如果按主项目 `L1` 的完整目标来打分：

- 当前不是“还没做”
- 也不是“已经完成”

更准确的判断是：

### 完成度大致在 60% 到 70%

理由：

- 最重要的边界已经对了
- 最关键的跨边界出口已经统一了
- 最小低层事实层已经能工作并有运行时证据
- 但完整候选感知主链、多感官覆盖、角色私有裁剪层还明显没到位

## 适合怎么理解它

最准确的大白话不是：

- “L1 已经做好了”

而是：

- “L1 的骨架、出口、低层事实投影和边缘状态修复已经做好了”
- “L1 到候选感知再到角色私有感知这条完整主链还没做好”

## 下一步最合理的方向

如果继续往主项目定义靠，优先级应该是：

1. 把 `L1` 原始事实正式接到“候选感知事件”对象层
2. 引入最小 `Per-Character` 过滤器
3. 让角色正式消费角色私有感知结果，而不是仅靠当前 runtime projection / candidate 混合层
4. 再扩更多 fact family，而不是先把 family 数量堆上去

## 最后一句话

当前 demo 仓库里的 `L1`，已经达到了：

> **主项目方向上“一个成立的最小 L1 骨架”**

但还没有达到：

> **主项目完整定义里的“成熟 L1 感知主链系统”**
