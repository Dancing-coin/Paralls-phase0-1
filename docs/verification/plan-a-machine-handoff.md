# 计划 A 换机验收交接（2026-10-12）

用户已明确要求先合入 main，暂不在当前机器运行验证。本次合入交付已实现代码与已知限制，不宣称计划 A、性能或六项闭环全部验收通过。后续在有 Godot 的另一台机器复验。

## 源码身份

- 集成起点：main `6a03a0fdcbba66096b2756a1a500442209af48eb`。
- 接收内容：候选 `bc016b8ea1c7d6c5e52fd426f34f6b88506457d7` 及之后的计划 A、最小 B/BM1、回归与优化改动；通过 cherry-pick 汇集为 main 的一次提交。
- 合入前最近验收的生产源码摘要：`sha256:bc9c12b6caf9f67709a76f0d7e69f220ad8ab50d2b73ba36e2bd21418c121081`，原清单 1190 文件。
- 原证据绑定 dirty 候选，不能因后来提交而改写成干净提交的正式验收。新机器记录实际 HEAD，并重新生成对应证据。

在新机器先保存 `git status --short`；存在改动时记录差异并保留。工作树干净且位于 main 时执行 `git pull --ff-only origin main`、`git lfs pull`，核对交接提供的最终 SHA。不要复制 linked worktree 的旧 `.git` 指针。

## 已有结果与剩余工作

下列数据来自旧机器的同一候选，均不是本次合并后重新运行：

| 项目 | 已有结果 | 新机器要求 |
| --- | --- | --- |
| 完整 pytest | 8086 passed、2 skipped、19 warnings；历史两个 spawn 在全量通过 | 重跑完整 `python -m pytest -v` |
| 14 个后端 profile | 执行通过；scale 的 `all_performance_gates_passed=false` | 核对执行与性能字段，分别报告 |
| 100 人 10× | 30 窗完整性/性能通过；p95 46.9735ms、max lag 0.938643、最终 backlog 0 | 原合同完整复验 |
| 1000 人 10× | 完整性通过、性能失败；p95 80.6232ms、max lag 7.081314、最终 backlog 7 | 定位失败；原门槛复验 |
| 1000 人 180 秒 short | 完整性/性能通过；18 次合格真实 provider 调用 | 实际 provider 资格检查 |
| 1000 人 1× 两小时 | 7200 测量窗、8 drain；完整性/性能子门通过；p95 110.8878ms、lag 0.6180254、最终/最大积压 0；481 次合格真实调用 | 干净新提交的完整正式复验 |
| 两小时 RSS | 首末中位增长 32,626,688 B，上限 33,554,432 B，余量 927,744 B | 保留历史失败，不能据一次通过声称长期增长已解决 |
| 本机历史四局各 600 秒 | main 6a 已通过并由用户确认完成 | 保留该记录；新源码/新机器 2/4 局各 600 秒单独复验 |
| Godot、all、B5 场景 | 本机暂停，缺最新场景证据 | 在新机器恢复真实可见窗口与完整验收 |
| HM1/HM2 | 真实路线、供应流程、承诺优先级、完整名单及生产 ModelRunGrant 未齐 | 不以合成输入代替真实来源，继续 blocked |
| Archive Door / VLA | 分别缺获批准 char_c IK / 真实凭据 | 保留 blocked；禁止替代资产或虚构调用 |

公共帧/参与合同、成员账本、唯一推进权与交接、受控读取、公共接线及最小日供给计算已有后端实现。C3 安全群体分摊仍 deferred；active/E/F 不因本次合并自动开放。

## 验收环境与入口

先读 `AGENTS.md`、`docs/INDEX.md`、`docs/harness.md`、`docs/harness-playbook.md`、`docs/ai-engineering-workflow.md`、`docs/verification/population-runtime-closure.md`，以及 9/18 整合规格和计划 A/B。

旧环境：Python 3.13.9、SQLite 3.53.4、Pydantic 2.13.5/core 2.46.5、pytest 9.1.1、zlib-ng 1.0.0。SQLite DLL/虚拟环境没有随 Git 提交；新机器核对 Python 实际加载的 SQLite 版本，按仓库约束及环境清单安装，不盲目升级所有依赖。Python 3.13.9 已获用户允许参与人口 Godot 验收。Godot 目标版本 4.6.3。

清除当前会话继承的 PYTHONPATH、PYTEST_ADDOPTS、PYTHONHOME，检查根目录与 backend 下的 `app.__file__` 来自新机器当前仓库。真实 Character/Siming 配置从项目 `.env` 安全加载；`.env` 和凭据不随本次 Git 提交，不打印或导出密钥。

每条命令使用独立仓库外证据目录，保存原输出/退出码、manifest、源码/依赖/硬件/物理磁盘布局、provider 配置名/timeout、开始结束时间与资源采样。依次执行：

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile character-population-integrated-loop --export-evidence "<新证据根>\plan-a-loop"
python scripts/verification/harness.py --profile social-model-compiler-contract --export-evidence "<新证据根>\model-contract"
python scripts/verification/harness.py --profile population-godot-runtime --godot-exe "<Godot 4.6.3 exe>" --export-evidence "<新证据根>\godot"
python scripts/verification/harness.py --profile all --godot-exe "<Godot 4.6.3 exe>" --export-evidence "<新证据根>\all"
```

依原 dispatcher 运行所需依赖；Godot 验收要求实际后端边界消息、可见结果、正常退出和当前 run_scope 的 InteractionSession 报告，不拿旧证据补齐。人口渲染通过不自动证明计划 A/B5 洪灾真实回流与场景完成。all 若 fail-fast，明确首个失败、blocked、not_run，并独立运行仍可运行的后续项。

真实 provider short 通过后，原 `population-mixed-soak` profile 必须包括 100/1000 人各 1800 秒 1×、两档 10× 各 30 个完整窗（原合同 3 秒）、1000 人 7200 秒；`population-multi-game-capacity` 包括 2/4 局各共同测量 600 秒。两档 10× 短窗口可能没有真实 provider 调用，不能以 live 配置冒充真实调用通过。不同独立验收串行执行，容量内部保持原并发。

采集结束后使用原离线复验器。逐项核对 `integrity_passed`、`performance_passed`、`ten_x_results`、每组 `capacity_passed` 和 scale 性能字段，不能只看 exit 0 或顶层 passed。保留原窗口、门槛、FULL 持久性、单 Owner、幂等/CAS/恢复，不以降负载、放宽门槛或修改静态报告获得通过。

## 历史与清理

最新旧机器原始证据：`D:/ParallsEvidence/paralls-correlation-prefix-qualification-20261011T020530Z`。原两小时复验见 `soak-1000-verification.json`，其 `formal_acceptance=false`、`result.passed=false` 是当时 dirty 来源门的真实状态，保持原文件不变。

原生刷盘长尾证据已封存于 `D:/ParallsEvidence/paralls-native-flush-soak-20261010232323Z`：实际 Owner 的 graph WAL `FlushFileBuffers` 单次约 1006.87ms，覆盖慢阶段约 99.78%。仅定位到系统调用区间，未证明具体磁盘、固件、安全软件或调度器原因。

原机器历史 `D:/ParallsEvidence/20260929T020900Z` 及既有报告中的 `paralls-six-closure-20260929T020900Z` 引用保留；未随迁的原始证据标明未在新机器复验，不猜测缺失内容。新机器通过不能写成原机器问题已解决。

本轮 CQ 的 16 个所属 TEMP 已清理、相关存活进程 0。后续只清本轮已导出的临时副本与所属进程；删除失败统一移入 `D:/ParallsCleanupArchive` 并记录路径/哈希/状态，移动失败也如实列明。旧证据和用户数据保留。

最终报告分列代码实现、后端回归、Godot 场景、真实来源与授权、性能、正式验收及机器差异。当前未完成项不因本次先合并而改变状态。
