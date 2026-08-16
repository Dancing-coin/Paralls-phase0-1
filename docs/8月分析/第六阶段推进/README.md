# 第六阶段推进：创作者控制面与内容发布

状态：`phase-six workbench; incremental guidance; control plane remains planned`

第六阶段把八月分析中的创作者 UI、CLI/MCP、玩法包、版本激活、发布和远程运营收口为
产品控制面。它不是玩法 authority，也不是把闭源核心代码加入创作者 SDK。所有写入仍通过
受治理的 proposal、revision、签名和既有 authority/event store 路径。

```text
P5 verified gameplay packages
  -> P5 后续能力基础 F0-F2 fresh-green
  -> P6A reader/editor/admin capability surface
  -> P6B UI + CLI/MCP aligned authoring contract
  -> P6C package validation, staging, activation and rollback
  -> P6D creator workflow and remote operations gate
  -> P7 civilization/world-model research lanes
```

## 1. 双运行形态

| 形态 | 创作者可做什么 | 生产事实由谁拥有 |
| --- | --- | --- |
| 本地创作/预览 | 编辑内容草案、规则参数、角色/资产绑定、模拟和 Harness | 本地受限 preview authority，不能写正式运行世界 |
| 远程正式运行 | 提交已签名 revision、启停规则 profile、调整公开数值和发布内容更新 | 远程闭源 authority、active revision、正式 event store |

远程运行不是“可以远程改数据库”。它只接受经过 schema、权限、兼容性、迁移、回滚和
审计验证的 revision；玩家真实状态不能被创作者直接覆盖。

## 2. 三档权限

- `reader`：读取已授权的 schema、公开 projection、验证报告和运行摘要；不能写草案或发布。
- `editor`：在授权项目内创建/编辑/模拟草案，运行 lint/preview/Harness，提交 review；不能
  签名激活、读取闭源实现、修改正式玩家事实或越过 capability allowlist。
- `admin`：管理项目成员、数据分类、审批/签名、staging/canary、激活/回滚和审计；仍不能
  直接读取或替换闭源 core 的内部算法、私有记忆、密钥或 event store 原始写入口。

权限结论由同一 authorization decision contract 服务 UI、CLI 和 MCP，不能靠前端隐藏按钮。

## 3. 正式化路径

建议建立 P6A capability/permission、P6B authoring adapter、P6C package lifecycle、P6D
creator vertical spec，并为 local preview、remote staging、admin activation 分别配置 Harness。

文档导航：

1. [01-第六阶段控制面范围与闭源边界.md](01-第六阶段控制面范围与闭源边界.md)
2. [02-UI、CLI与MCP对齐契约.md](02-UI、CLI与MCP对齐契约.md)
3. [03-玩法包、激活、发布与远程运营契约.md](03-玩法包、激活、发布与远程运营契约.md)
4. [04-创作者流程与第六阶段门禁.md](04-创作者流程与第六阶段门禁.md)

正式 SDD 入口：
[Phase Six Creator Control Plane Specification Tree](../../superpowers/specs/world-character-siming-authority-mainline/phase-six-creator-control-plane/README.md)
；对应实施计划见同名 plan tree。当前仍为 `design-only; implementation not authorized`。
