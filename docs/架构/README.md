# 架构文档索引

状态：`current-code architecture baseline; August incremental guidance linked below`

本目录放仓库级和运行时级架构文档，避免把架构总纲继续平铺在 `docs/` 根目录。

## 目录结构

```text
docs/架构/
  README.md
  整体架构.md
  感知输入对齐层.md
  事实上抛链路与多模态链路.md
  VLA与多模态链.md
  运行时/
    README.md
    运行时总览.md
    运行时覆盖矩阵.md
    运行时命名边界审计.md
    图表/
      整体运行时时序图.md
      整体运行时数据流图.md
    模块/
      世界运行时.md
      SystemL1.md
      SystemL6事件总线.md
      Siming.md
      角色智能体.md
      ESM与交互编排.md
      Godot表现与角色入口.md
      VLA运行时通道.md
      模型服务通道.md
      Harness验证证据.md
```

## 阅读顺序

1. `docs/架构/整体架构.md`
2. `docs/架构/运行时/运行时总览.md`
3. `docs/架构/运行时/运行时覆盖矩阵.md`
4. `docs/架构/运行时/模块/GameplayFoundation与领域结算.md`
5. `docs/架构/感知输入对齐层.md`
6. `docs/架构/事实上抛链路与多模态链路.md`
7. `docs/架构/VLA与多模态链.md`
8. `docs/架构/运行时/运行时命名边界审计.md`
9. `docs/架构/运行时/图表/整体运行时时序图.md`
10. `docs/架构/运行时/图表/整体运行时数据流图.md`
11. `docs/架构/运行时/模块/SystemL6事件总线.md`
12. `docs/架构/运行时/模块/Siming.md`
13. `docs/架构/运行时/模块/*.md`

## 分层原则

- `整体架构.md`：仓库级总纲，覆盖运行时、非运行时支撑面和验证体系。
- `运行时/运行时总览.md`：运行时级总纲，只讨论运行时内的结构、时序和数据流。
- `运行时/图表/`：只放跨域可渲染图。
- `运行时/模块/`：按 owner 或运行时模块拆分的局部文档。

## 与 8 月增量设计的关系

本目录以正式 spec/plan、当前代码和 Harness 为当前架构事实来源。以下文档在此事实
基线上讨论待建 owner、玩法域和补强优先级，不是并列运行时或实现授权：

- [全域架构导航](../8月分析/全域架构/README.md) 与
  [系统边界与责任矩阵](../8月分析/全域架构/00-系统边界与责任矩阵.md)：增量 owner
  导航，明确已实现、可复用与 planned 的分层；
- [架构审计](../8月分析/架构审计/README.md) 与
  [缺漏审计与补强路线](../8月分析/架构审计/23-缺漏审计与补强路线.md)：对该基线的
  缺口和 backlog 审计。

如出现矛盾，仍以 `docs/superpowers/` 的正式 spec/plan、代码和
`.harness/verification/` 报告为准。
