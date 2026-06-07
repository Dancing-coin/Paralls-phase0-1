# Jeheno Third Person Controller Asset Audit

这份文档盘点当前 `addons/JehenoThirdPersonController` 目录中新增跟踪的资产，并给出仓库治理视角下的分类建议。

## 范围

盘点目录：

- `addons/JehenoThirdPersonController/`

当前规模：

- 总文件数：384
- 总体积：约 3601.11 MB

按一级目录拆分：

- `textures/`：230 文件，约 1693.09 MB
- `Arts/`：87 文件，约 2.91 MB
- `PlayerCharacter/`：60 文件，约 0.70 MB
- `Map/`：1 文件，约 0.01 MB
- 根目录额外包含：
  - `ThroneRoom.blend`
  - `interior.exr`
  - `LICENSE`
  - `README.md`

## 关键发现

### 1. 最大单体风险文件是 Blender 源文件

- `ThroneRoom.blend`：约 1904.22 MB

这不是运行时最适合直接消费的交付格式，而是典型制作源文件。它已经通过 Git LFS 入库，但不适合长期留在代码主仓库。

### 2. 最大体积区块是高分辨率纹理目录

- `textures/` 总量约 1693.09 MB

其中最大的 15 个文件几乎都在 25 MB 到 46 MB 区间，且主要是：

- `*_Normal.png`
- `*_BaseColor.png`

这说明当前贴图分辨率偏高，更接近源贴图或高保真导出，而不是轻量演示资产。

### 3. `PlayerCharacter/` 更像插件运行逻辑

`PlayerCharacter/` 目录主要是：

- `.gd`
- `.uid`
- `.tscn`
- 少量 `.ogg`、`.res`、`.glb`

这部分体积很小，更像第三人称控制器插件本身，而不是当前主要的仓库负担来源。

### 4. `Arts/` 是供应商自带示例资源

`Arts/` 目录内容主要是：

- 图标
- 网格/棋盘测试图
- 字体

这部分体积小，但多数不一定是当前 `Phase 0` demo 的正式依赖，更像插件配套样例内容。

## 分类建议

### A. 建议保留在主仓库的内容

这些内容更接近“运行必需”或“插件必需”：

- `PlayerCharacter/`
- `Map/test_map_scene.tscn`
- 插件运行会直接引用的脚本、场景、声音、着色器
- 当前 Godot 导入确实依赖的 `.import`

如果项目仍依赖该 addon 的现成控制器和示例角色，这部分可以继续留在主仓库。

### B. 可暂留主仓库，但应列入迁移清单的内容

这些内容当前已经入库，但从资产治理视角看应优先迁移：

- `ThroneRoom.blend`
- `interior.exr`
- `textures/016.hdr`
- `textures/*.png` 这一整批高分辨率环境贴图

原因：

- 体积大
- 偏源资产属性
- 对代码协作和 clone/pull 成本影响显著

### C. 需要确认是否真的有运行时价值的内容

这些内容可能并不值得继续跟着主仓库长期走：

- `Arts/` 下的原型纹理、logo、示例图
- 插件自带宣传/展示类图片
- 与当前 `Phase 0` 演示无关的样例资源

它们不大，但会增加资产边界的不清晰度。

## 建议的仓库角色划分

### 主仓库继续承担

- Godot 项目运行
- backend 联调
- 运行时导出结果
- 必需的插件脚本与场景

### 独立资产仓承担

- Blender 源文件
- 高精度 HDR/EXR
- 原始高分辨率贴图
- 后续环境与角色制作母版

## 迁移优先级

### P1

- `ThroneRoom.blend`

理由：

- 单文件 1.9 GB
- 是最显著的主仓库体积负担
- 明确属于制作源文件

### P2

- `textures/`
- `interior.exr`
- `textures/016.hdr`

理由：

- 总量接近 1.7 GB
- 明显偏环境源资产
- 很可能可以通过更轻的运行时导出结果替代

### P3

- `Arts/` 中与当前 demo 无关的样例资源

理由：

- 体积不大
- 但会让 `addons/` 同时承担插件、样例库、项目环境源仓三种职责

## 当前不建议立刻做的事

- 现在就从主仓库删除这批资产

原因：

- 当前还没补齐“哪些文件是 Godot 运行真正必需”的逐项追溯
- 直接删会打断现有可运行状态

## 推荐下一步

1. 确认 `Phase 0` 当前真正运行时依赖的 Jeheno 目录最小集合。
2. 建一个独立资产源仓，先迁移：
   - `ThroneRoom.blend`
   - `interior.exr`
   - `textures/`
3. 在主仓库保留：
   - 当前运行时需要的导出结果
   - 必要 `.import`
   - 一份源资产追溯表

## 结论

这批 Jeheno 资产已经可以上传，也已经成功走 Git LFS，但从长期治理角度看，它更像“临时留在主仓库的正式资产源包”，而不是适合持续扩张的主仓库结构。

短期可接受，长期应拆分。
