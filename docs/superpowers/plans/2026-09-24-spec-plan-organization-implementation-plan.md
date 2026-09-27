# Spec/Plan 文档整理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task.

**Goal:** 在不破坏现有链接和近期设计输入的前提下，建立可检索、可审计、可逐步迁移的 spec/plan 文档体系。

**Architecture:** 先用治理入口和保护清单建立非破坏性导航层，再补齐 spec ↔ plan ↔ evidence 关系，最后才做链接验证后的物理归档。当前主线和增量专题保持独立，历史文件不直接删除。

**Tech Stack:** Markdown、PowerShell/rg 只读盘点、Git diff、Harness 文档检查。

**Spec:** `docs/superpowers/specs/README.md` 与 `docs/superpowers/specs/_governance/protected-recent-2026-09.md`

## Global Constraints

- 保留根 Godot 项目、backend 和既有运行时边界。
- 2026-09-10 至 2026-09-24 的 12 份近期 spec 在链接迁移完成前不移动、不重命名、不归档。
- 不把窄垂直验证升级为整域完成。
- 不删除历史文档；历史文档必须有替代关系或 archive 入口。
- 不覆盖用户已有未提交修改。
- 任何物理搬迁都必须先通过链接检查并保留 F 盘备份。

## Review Focus

- 近期保护文件是否全部仍在原路径，且保护清单没有遗漏。
- README 入口是否能区分主线、增量专题、历史平铺和治理资料。
- spec、plan、audit、freeze、execution-prompt 是否被错误地互相当作替代品。
- 文档状态是否把实现、证据和阻塞混在一条自由文本里。
- 物理搬迁前是否存在失效相对链接或 `/d:/...` 绝对链接。

---

### Task 1: 建立治理入口和近期保护清单

**Files:**
- Create: `docs/superpowers/README.md`
- Create: `docs/superpowers/specs/README.md`
- Create: `docs/superpowers/plans/README.md`
- Create: `docs/superpowers/specs/_governance/README.md`
- Create: `docs/superpowers/specs/_governance/protected-recent-2026-09.md`

- [x] **Step 1: 写入入口与保护边界**
- [x] **Step 2: 检查 Markdown 空白和路径格式**

验证命令：

```powershell
git diff --check
rg -n "protected-recent-2026-09|world-character-siming-authority-mainline|current-project-intelligence-upgrade" docs/superpowers
```

### Task 2: 建立 spec ↔ plan ↔ evidence 注册表

**Files:**
- Create: `docs/superpowers/specs/_governance/spec-registry.md`
- Create: `docs/superpowers/plans/_governance/README.md`
- Modify: `docs/superpowers/specs/README.md`
- Modify: `docs/superpowers/plans/README.md`

- [ ] **Step 1: 统计所有 spec/plan 文件和树级 README**
- [ ] **Step 2: 为每个当前树入口记录 parent、matching plan、status、evidence**
- [ ] **Step 3: 记录无匹配 plan、无状态和疑似历史文件，不自动补写状态**
- [ ] **Step 4: 运行链接检查并记录结果**

### Task 3: 规范状态字段并标记历史关系

**Files:**
- Create: `docs/superpowers/specs/_governance/status-vocabulary.md`
- Create: `docs/superpowers/specs/_governance/supersession-register.md`
- Modify: 各树级 README，仅补导航和状态说明

- [ ] **Step 1: 定义 lifecycle、implementation、evidence、blocker 四维状态**
- [ ] **Step 2: 只为当前入口和保护文件建立映射，不批量改写正文状态**
- [ ] **Step 3: 将明确 superseded/historical 的关系登记到替代表**

### Task 4: 修复链接并准备物理归档

**Files:**
- Modify: 受链接检查发现影响的 Markdown 文件
- Create: `docs/superpowers/archive/README.md`

- [ ] **Step 1: 修复 `/d:/...` 绝对路径和失效相对路径**
- [ ] **Step 2: 对每次路径变更运行全量 Markdown 链接检查**
- [ ] **Step 3: 只在保护文件、注册表和链接检查稳定后提出移动清单**

### Task 5: 执行可回退的目录收敛

**Files:**
- Modify: 经过用户复核的文件路径和引用
- Preserve: `F:\paralls-phase-0-demo-spec-plan-backup-2026-09-24-1030`

- [ ] **Step 1: 将根目录历史 spec/plan 分批移动到明确的 legacy/archive 目录**
- [ ] **Step 2: 更新 registry、README 和所有引用**
- [ ] **Step 3: 运行 docs Harness、链接检查和 `git diff --check`**
- [ ] **Step 4: 输出移动清单、未处理项和回滚路径**
