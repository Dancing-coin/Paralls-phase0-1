# Asset Collaboration TODO

目的：

- 让项目协作者知道哪些资产留在主仓库，哪些资产应迁到独立资产源仓。
- 建立“改源文件 -> 导出运行时结果 -> 回写主仓库”的固定更新流程。
- 在不破坏当前 `Phase 0` 可运行状态的前提下，逐步减轻主仓库的体积负担。

关联文档：

- `docs/assets-policy.md`
- `docs/jeheno-third-person-controller-asset-audit.md`
- `docs/asset-injection-guide.md`
- `docs/blender-godot-asset-export-convention.md`

---

## A. 协作者分层

- [ ] 定义两类协作者身份并写入项目说明：
  - 运行协作者：只拉主仓库，负责 Godot / backend 开发、联调、验证。
  - 资产协作者：同时拉主仓库和资产源仓，负责 Blender / 贴图 / 导出更新。

- [ ] 在项目说明中明确：
  - 所有人都需要安装 `git lfs`
  - 只有资产协作者需要拉资产源仓
  - 主仓库不再默认承载未来新增的大型源资产

## B. 资产边界固化

- [ ] 以后新增资产前，先按 `docs/assets-policy.md` 分类：
  - Runtime Assets
  - Source Assets
  - Local Working Artifacts

- [ ] 把“主仓库默认只收运行时结果，源文件默认进资产源仓”定为团队规则。

- [ ] 保持以下本地产物继续忽略，不进入版本库：
  - `.codex/tmp/`
  - `goblend.log`
  - `push-*.log`

## C. Jeheno 资产拆分计划

- [ ] 盘清 `addons/JehenoThirdPersonController` 当前最小运行时依赖集合。

- [ ] 确认这些内容是否仍需留在主仓库：
  - `PlayerCharacter/`
  - 运行时必需的 `.tscn` / `.gd` / `.import`
  - 当前 Godot 打开项目必须存在的资源

- [ ] 准备迁出到资产源仓的优先级：
  - P1: `addons/JehenoThirdPersonController/ThroneRoom.blend`
  - P2: `addons/JehenoThirdPersonController/interior.exr`
  - P2: `addons/JehenoThirdPersonController/textures/`
  - P3: `addons/JehenoThirdPersonController/Arts/` 中与当前 demo 无关的样例资源

## D. 资产源仓落地

- [ ] 新建独立资产源仓，建议命名示例：
  - `paralls-phase0-asset-source`
  - 或 `paralls-assets-source`

- [ ] 在资产源仓中建立目录约定：
  - `environment/`
  - `characters/`
  - `props/`
  - `source/blender/`
  - `source/textures/`

- [ ] 把以下现有大源资产迁入资产源仓：
  - `ThroneRoom.blend`
  - `interior.exr`
  - `textures/016.hdr`
  - 高分辨率环境贴图源文件

- [ ] 确保资产源仓同样启用 Git LFS。

## E. 主仓库更新流程

- [ ] 固定以后每次资产更新必须遵循的顺序：
  1. 在资产源仓修改源文件
  2. 导出运行时结果到主仓库
  3. 刷新 Godot 导入产物
  4. 更新资产清单
  5. 提交主仓库 PR

- [ ] 约定主仓库只提交这些变化：
  - `.glb` / `.gltf` / `.bin`
  - 当前运行时需要的贴图
  - `.import`
  - 场景挂载更新
  - 资产清单更新

- [ ] 禁止以后把新的超大 `.blend` 直接先丢进主仓库再说。

## F. 资产清单

- [ ] 新建一份正式资产清单模板。

- [ ] 清单每条资产至少记录：
  - 运行时文件路径
  - 源文件路径
  - 源仓库地址
  - 源仓提交号或版本号
  - 导出日期
  - 导出人
  - 是否为当前 `Phase 0` 运行必需

- [ ] 先为 `JehenoThirdPersonController` 写第一版实际清单。

## G. 协作者操作说明

- [ ] 写明运行协作者拿仓库步骤：
  - `git clone`
  - `git lfs install`
  - `git lfs pull`
  - 打开 Godot 项目

- [ ] 写明资产协作者拿仓库步骤：
  - 拉主仓库
  - 拉资产源仓
  - 在资产源仓改 Blender / 贴图
  - 导出到主仓库
  - 验证 Godot 可导入

- [ ] 写明代码评审边界：
  - 主仓库 PR 主要审运行时结果和挂载变化
  - 资产源仓 PR 主要审源文件修改本身

## H. 验证与迁移完成条件

- [ ] 迁移前验证：
  - 当前 Godot 项目能正常打开
  - 当前 `Phase 0` 路径可运行

- [ ] 每迁出一批源资产后验证：
  - 主仓库重新 clone 后可打开
  - `git lfs pull` 后资源完整
  - Godot 不报丢失资源错误

- [ ] 本轮迁移完成标准：
  - `ThroneRoom.blend` 不再留在主仓库
  - 高精度环境源贴图不再默认留在主仓库
  - 主仓库只保留运行时必需资产和追溯信息
