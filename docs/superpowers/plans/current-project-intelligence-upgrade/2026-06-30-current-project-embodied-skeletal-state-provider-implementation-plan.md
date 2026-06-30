# 当前项目具身骨骼状态提供层实施计划

> 对应规格：
> [2026-06-29-current-project-embodied-skeletal-state-provider-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-embodied-skeletal-state-provider-design.md)

**目标：** 把本地身体/骨骼链掌握的骨骼空间真相抽象成稳定 Provider 层。

## 任务

- [ ] 定义高层具身状态导出
- [ ] 定义中层骨架参数导出
- [ ] 定义低层骨骼快照导出
- [ ] 明确哪些进入主感知链，哪些只进入调试/回放
- [ ] 设计 focused verifier，证明这层不会把整副骨骼快照直接灌给后端角色智能体

## 产出

- 骨骼状态 Provider 层协议
- 三层导出边界
- 与 `Perception Query Frame` 和多模态链的关系
