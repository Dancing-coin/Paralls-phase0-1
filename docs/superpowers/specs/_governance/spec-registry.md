# Spec Registry（阶段 1）

本表是整理入口，不是运行时注册表，也不替代各 spec 正文。阶段 1 只登记树级边界和保护范围；逐文件状态、matching plan 与 evidence 在阶段 2 补齐。

## 目录规模（2026-09-24）

| 范围 | Markdown 文件数 | 说明 |
|---|---:|---|
| `docs/superpowers/specs/` | 504 | 含本治理入口文件 |
| `docs/superpowers/specs/current-project-intelligence-upgrade/` | 36 | 主线外增量专题 |
| `docs/superpowers/specs/world-character-siming-authority-mainline/` | 399 | 当前主线及其子树 |
| `docs/superpowers/plans/` | 476 | 含本阶段新增计划入口 |
| `docs/superpowers/plans/current-project-intelligence-upgrade/` | 46 | 增量专题计划 |
| `docs/superpowers/plans/world-character-siming-authority-mainline/` | 332 | 主线计划及其子树 |

## 当前树级注册

| Spec tree | Matching plan tree | Lifecycle | Implementation | Evidence | Owner |
|---|---|---|---|---|---|
| `world-character-siming-authority-mainline` | `plans/world-character-siming-authority-mainline` | active | execution-active | mixed; read each child README | backend authority / Godot mirror / Character Core / Siming boundaries |
| `current-project-intelligence-upgrade` | `plans/current-project-intelligence-upgrade` | supplemental | implemented increments plus deferred follow-ons | mixed; provider-specific | L1 / perception / VLA / interaction orchestration |
| root-level dated specs | root-level dated plans or no matching plan | historical or unclassified | mixed | mixed | must not be inferred from filename |

## Protected recent set

近期 12 份 spec 的 canonical list 见 [protected-recent-2026-09.md](protected-recent-2026-09.md)。这些文件保持原路径，直到阶段 3 的链接迁移完成。

## 已知待处理项

- 现有状态字段是自由文本，不能直接用字符串排序出“已完成”。
- 主线 README 同时承载树索引、完成审计和历史快照，需要后续拆分导航与记录职责。
- `specs/` 与 `plans/` 存在类型错位文件，需在阶段 2 登记后再决定是否移动。
- `/d:/...` 绝对路径和部分旧相对路径需要阶段 3 统一修复。
- “窄垂直已验证”必须单独记录，不能提升为整个 INF/平台完成。

## 阶段 2 注册字段

逐文件注册时采用以下字段：

```text
id
path
kind
tree
parent
matching_plan
lifecycle
implementation
evidence
blocker
supersedes
superseded_by
evidence_refs
protected
```

缺失字段保持空值并进入待处理清单，不根据标题或日期猜测。
