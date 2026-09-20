# main 审查四项修复与外机交接

范围：基于 `7ce40b6d` 的四项已确认问题。用户明确暂不处理 Godot 导入提前退出，`scripts/verification/common.py` 保持不变。执行步骤和本轮检查结果见[实施计划](../superpowers/plans/2026-09-20-main-review-fixes-implementation-plan.md)。

## 已实现的行为

- `CharacterMotor` 在 `move_and_slide()` 后，将实际平面速度投影回角色当前本地轴；本地正 Y 对应前进，碰撞阻挡和竖直坠落不再凭期望速度表现为前进。NPC 的本地 proposal 保留，交给 Composer 的 lease 使用世界 X/Z。
- Phase0 巡逻采集器逐物理帧测量实际平面位移及目标方向，分别记录 char_a、char_b。Motor fallback 只有两者同一行均满足 `distance > 0.01`、`target_alignment > 0.5` 才 proved；停止采样与解析器均使用导出精度。普通速度/marker 不再单独证明巡逻。
- Windows child Python 使用虚拟环境依赖优先；父进程禁用 user-site 时，child 显式继承 `PYTHONNOUSERSITE=1`，不会因改用 base executable 而重新开启。
- active Heavenly 所属事件族在 provider 超时、无效结果或图谱降级时，同步、continuation 与 durable accepted-plan 均返回 no-action，不继续 legacy candidate/state tree/narrative；保留原因审计及 receipt replay。shadow/off 和无关事件族保持原决策路径。

## Godot 未验证

本轮没有启动 Godot，也没有资源导入、场景运行或可见表现证据。Python 静态检查通过不代表 Godot 运行通过；`all` 和原六项总闭环仍未完成。本轮独立审查的一个精度边界问题已修复，不将斜坡/移动平台扩展语义或旧 root-motion 证据路径纳入本次改动。

在外部 Godot 4.6.3 机器使用包含本修复的干净 checkout，按机器既有资源准备步骤完成导入，然后执行：

```powershell
# 请使用该机器已配置的 Godot 可执行文件。
& $env:GODOT_EXE --headless --path . --script res://scripts/verification/CharacterMotorCoordinatesProbe.gd
python scripts/verification/harness.py --profile phase0 --godot-exe $env:GODOT_EXE --export-evidence D:\HarnessEvidence\main-review-fixes-phase0
```

独立坐标 probe 不依赖外部角色资产；检查 0/90/180 度前后左右、静止、竖直运动及实际墙面阻挡。要求进程退出码 0，`character_motor_coordinates_probe` JSON 的 `passed=true` 且 `failures=[]`。当前只交付可执行 probe，尚未取得这份运行结果。

Phase0 还需要其正常 backend/provider/资产环境；要求本轮 main log 中 char_a、char_b 的 `npc_patrol_probe` 都满足上述阈值。缺角色、位移为零、反向/横向、字段不完整必须保持未通过。检查角色前进时的动画方向与世界位移一致。导入准备问题已被用户排除；若外机在导入阶段阻塞，应如实记录，不能改成运行通过。

外机保存本轮源码身份、命令、退出码、日志及导出的 manifest；不要用旧版本的 Siming 或 all 报告替代。本轮后端模拟 provider 失败测试不表示进行过新的真实在线模型调用。


## 本机验证结果

- 后端全量：**6901 passed、2 skipped**，退出码 0，临时目录清理通过。
- Harness 工具最终全套：**421 passed**；静态 contract：**5 项通过**。
- 精度修正后相关检查：**95 passed**；独立审查发现项已处理。
- 原始日志/XML：`D:/HarnessEvidence/main-review-fixes-backend-20260920.*`、`main-review-fixes-tools-final-20260920.*`；最终 contract 证据根：`D:/HarnessEvidence/main-review-fixes-contract-commit-ready-20260920`。
- 全量后端运行时，最后只更新巡逻日志的 GDScript 精度与说明；最终脚本由后续 95 项定向检查及最终 Harness 工具全套覆盖。Godot/all 状态仍为未验证。
