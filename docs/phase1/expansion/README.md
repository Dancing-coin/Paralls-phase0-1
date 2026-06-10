# docs/phase1/expansion 目录结构

## 定位

- `expansion = Phase 1 扩展 / Phase 2+ 预留`，不作为 Phase 1 验收硬门槛。
- 承载高潜但可后置的能力族、扩展玩法与中长期技术专题。

## 目录分层

- `02-创造系统`
  - 创造系统总纲
  - 建筑建造与蓝图系统设计
  - 世界创建与地图映射系统设计
  - 生物与物件创造系统设计
  - 创造运行时与规则封装设计
  - 创造表现层（L3）设计
  - 创造算力与部署策略设计
- 世界状态与证据链设计
- 证据与痕迹系统设计
- 算力与部署策略设计

## 与 core 边界

- `core` 只放 Phase 1 必做能力，`expansion` 不得反向定义 core 的验收门槛。
- expansion 文档可反哺 core，但若形成 Phase 1 新硬依赖，需先更新 `docs/consolidation/04-Phase映射表.md` 后再迁移目录。

## 维护规则

- 每次新增/迁移 expansion 文档后，同步更新：
  - `docs/phase1/README.md`
  - `docs/consolidation/04-Phase映射表.md`
  - 相关 `INDEX.md`（若存在）
