# DeepSeek 全部对话目录与动作底座吸收、边界及项目指导方向

日期：`2026-09-15`

状态：`分析与决策记录；不是新的运行时契约`

## 1. 文档目的

本文档吸收 DeepSeek 全部对话目录，并将其与仓库当前的角色动作底座、CharacterAgent、INF、ESM、Gameplay、物理和联网设计对齐。它包含两种证据层级：轮次 `44-89`（消息 `113-206`）有分享页原文级分析；轮次 `1-43` 目前只有用户提供的完整目录，因此只做目录级主题和决策分析，不臆造缺失的回答正文。

本文档解决四个问题：

1. DeepSeek 的每个问题和回答到底提出了什么方向。
2. 哪些方向可以进入当前 3D 角色动作底座第一期。
3. 哪些方向需要修正后才能吸收。
4. 哪些方向只应作为后续框架研究，或者明确不应进入当前主链。

本文档不是新的 Actor、Entity、Weapon、LOD 或网络运行时 spec。发生冲突时，以下文档仍然拥有更高权威：

- `AGENTS.md`
- `docs/superpowers/specs/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`
- 四份 `2026-09-14-character-*-subspec.md`
- `docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`

## 2. 阅读范围与证据等级

### 2.1 对话范围

通过 DeepSeek 分享页公开内容接口读取到消息 `113-206`：

- 共 `92` 条消息。
- 共 `46` 组可配对的用户问题/助手回答。
- 消息编号 `155`、`156` 在返回数据中缺失，本文不根据上下文臆造其内容。
- 阅读范围不是只包含 `113/114`，而是连续覆盖到 `205/206`。

目标起点：

```text
113 用户：带上武器呢？打斗和枪械战斗起来会怎么样？缺什么
114 助手：近战、枪械和缺失清单
```

完整目录另列出 `1-90` 共 90 个轮次。若按每个轮次一问一答连续排列，则目录轮次 `44` 与消息 `113/114` 对齐，目录轮次 `89` 与消息 `203/204` 对齐，目录轮次 `90` 是当前目录请求；这个对应关系只用于导航，不能替代原文证据。前 `1-43` 的结论均标记为“目录级推断”。

### 2.2 结论等级

| 标记 | 含义 | 处理方式 |
| --- | --- | --- |
| `ADOPT` | 与仓库边界一致且值得现在吸收 | 写入主 spec/plan 或第一期验证 |
| `CONSTRAIN` | 方向有价值，但原回答过度承诺 | 只吸收经过边界收紧后的版本 |
| `RESERVE` | 值得预留接口或记录方向 | 只增加扩展点、字段或验收前置条件 |
| `DEFER` | 合理但超出第一期 | 放入后续路线，不影响当前主链 |
| `REJECT` | 与权威边界、物理安全或证据不足冲突 | 不进入设计与实现 |

DeepSeek 回答中出现的性能百分比、实体数量、帧时间、组合数量和“业界标准”判断，除非有仓库 benchmark 或运行证据，否则只能视为假设，不得升级为项目事实。

## 3. 总体判断

DeepSeek 后续讨论实际上包含七个层次：

```text
武器与战斗
  -> 外部动画与实时组合
  -> 角色动作底座泛化
  -> 物体破坏与实体分级
  -> LOD、智能体、群体模拟、OOP/DOD
  -> 2D/2.5D 和跨类型游戏
  -> 体素、网格和远景表示
```

最终应吸收的核心不是“把所有东西做成一个万能控制器”，而是以下机制：

```text
语义意图
  -> proposal adapter
  -> claims-based arbiter
  -> immutable command/frame
  -> specialized executor
  -> presentation projection
  -> authority settlement
```

角色是当前第一期的特化执行对象。机制层应可扩展到机关、道具和其他实体，但不应在第一期提前实现完整的通用 Entity 世界。

## 4. 当前项目的正式基线

### 4.1 正式运行边界

当前正式设计已经冻结以下 ownership：

```text
Human / CharacterAgent / Program
  -> source adapter
  -> IntentProposal
  -> ActorActionArbiter
  -> CharacterIntentFrame
  -> MotionContributionComposer
  -> CharacterMotor
  -> CharacterPresentationInput
  -> RoleSkin / AnimationTree

contact evidence
  -> ActionAttempt
  -> ESM / Gameplay authority
  -> AuthorityResult
  -> runtime projection
```

- Godot 负责本地身体、输入、碰撞执行和可见/音频表现。
- `CharacterMotor` 是唯一的速度、重力、朝向、碰撞、root motion 消费和 `move_and_slide()` owner。
- CharacterAgent、INF 和 Siming 只能提交语义意图、约束、证据、催化剂或表现提示。
- ESM/Gameplay 负责命中、伤害、状态、能力、装备、库存、资源和世界对象后果。
- marker、collider、ray query、IK 和本地物理反应都不能直接成为世界真相。
- Phase 1 是本地 kinematic `CharacterBody3D` + Mode B 语义联网，不是 raw-pose 网络、rollback 或服务器权威刚体物理。

### 4.2 当前实现事实

仓库目前仍是迁移中的过渡实现：

- `CharacterMotor.gd` 已有规范的玩家 `move_and_slide()` 路径。
- `CharacterReplica.gd` 仍有直接坐标移动，存在第二条位移 truth。
- `KnightRoleSkin.gd` 有硬编码 clip map、root-motion sampling 和模型特定修正。
- `KnightCombatModifier.gd` 是剑盾专用 presentation modifier，不是通用 Weapon runtime。
- `EmbodiedActionController.gd` 有交互阶段，但不是全局并发仲裁器。
- `CharacterActionAssetDescriptor.gd` 和 registry 仍是窄的过渡实现。
- 后端已有 equipment、inventory、ability、action window 和 embodied settlement 碎片，但没有完整的弹药、弹匣、膛室、hitscan/projectile、近战 clash/parry 或通用武器结算域。

因此，设计可以承接武器，但当前代码不能声称已经完成可玩的剑战或枪战。

## 5. 全对话逐组目录与吸收决策

以下目录按消息编号保留每个可见问答组。每组包含：原始问题、回答方向、主要风险和项目处理。

### A. 武器、外部动画与实时组合（113-124）

#### `113/114`：带上武器后近战和枪械缺什么

**原始方向**：近战需要拔刀/收刀、攻击、连招、输入缓冲、取消窗口、格挡、弹反、拼刀、武器挂载和上半身与移动并发；枪械需要举枪、ADS、FOV、weapon IK、后坐力、hitscan/projectile、连射、换弹、枪械切换和枪口表现。回答建议新增 `WeaponLayer`、`WeaponData`、`WeaponComponent` 和后端 fire/reload/switch/clash 协议。

**判断**：需求清单基本正确，但独立 `WeaponLayer` 容易变成第二套 FSM，与 `ActorActionArbiter` 竞争动作所有权。

**处理**：`ADOPT + CONSTRAIN`。

**正式落点**：武器由 `EquipmentBinding`、`WeaponActionProfile`、canonical claims、可选 `WeaponRuntime` 和 ESM/Gameplay authority 组成。第一期只要求一个握持槽、一个近战动作闭环和一个 hitscan 语义验证 fixture；弹药、弹匣、膛室、散布、弹道、双持、拼刀和完整换弹延期。

#### `115/116`：随手拿道具能否当武器

**原始方向**：任意有质量、尺寸、形状和握持点的 `RigidBody3D` 都可以通过 `PropPhysics`、自动握持点、IK、原子动作和物理碰撞变成武器。

**判断**：这是远期沙盒能力，但“有物理属性就自动武器化”不可靠。还需要道具身份、custody/ownership、affordance、对象 revision、合法握持锚点、动作族兼容性、物理 profile、权威路由、持久化和网络策略。

**处理**：`CONSTRAIN + DEFER`。

**解决方案**：标准武器与临时道具分开。标准武器进入正式 `WeaponDefinition`；临时道具必须先获得 `ImprovisedToolProfile`，只允许已审查的动作族。未资格化的道具只能退化为 pickup、throw、push 或 presentation-only，不能自动生成自然攻击动作。

#### `117/118`：动作底座是否适合实时演算

**原始方向**：把实时物理、实时 IK、实时原子动作组合、motion matching、AI 生成姿态和 ragdoll 都归入动作底座。

**判断**：需要拆分 fixed tick、render sampling 和异步慢路径。当前架构不是每帧重新生成完整骨骼姿态，而是播放外部导入 clip，并在 presentation 侧采样 AnimationTree/IK。

**处理**：`CONSTRAIN`。

**解决方案**：

- fixed tick：proposal、claims、arbiter、motion command、contact evidence、ActionAttempt。
- render/update：AnimationTree、IK、camera、VFX、SFX。
- async：CharacterAgent、LLM、INF slow planning。
- backend：ActionAttempt 结算和 revision。

原子动作库、motion matching、AI pose generation、ragdoll authority 都不能被描述为当前已有能力。

#### `119/120`：有限动画资产产生无限涌现

**原始方向**：有限原子动作、风格变体、骨骼遮罩、IK、物理参数、后端变量和 AI 决策可以产生极大组合空间，并举出“44 个原子动作”和“10^80 组合”等数字。

**判断**：有限资源通过参数化、claims、物理 profile 和 authority 结果产生丰富表现，是有效产品愿景；具体数量和组合规模没有仓库证据。

**处理**：`ADOPT + CONSTRAIN`。

**第一期规则**：`atomic_sequence` 字段存在但必须为空；外部 clip 不能自动变成原子动作；任何未来原子扩展仍要经过 registry、claims、timing、cancel、recovery 和 authority 规则。

#### `121/122`：骨架权重与风格权重适配体型和风格

**原始方向**：骨架维度处理体型，风格维度处理动作表现，两者正交。

**判断**：骨架 mapping、retarget、canonical skeleton 和 build-time qualification 已进入正式设计；runtime proportion scaler、通用 style selector/mixer 尚未实现。

**处理**：`ADOPT + RESERVE`。

**解决方案**：比例适配必须受 IK、安全包络和实际骨骼约束；风格属于 presentation profile，不得进入 authority truth，也不能用速度/幅度参数保证动作自然。

#### `123/124`：此前方案是否已有体型和风格适配

**原始方向**：判断现有方案已有 canonical skeleton、BoneMap、导入校验，但缺少比例缩放、运行时 IK 和风格混合。

**判断**：这是对仓库现状较准确的差距识别。

**处理**：`ADOPT`。

**第一期解决**：把 canonical mapping、mask、track impact、root/pelvis、seam/support、hand/weapon anchor 和 fallback 作为 qualification report；不承诺任意运行时轨道手术。

### B. 角色动作底座泛化为通用状态驱动机制（125-142）

#### `125/126`：动作底座能否用于机关和道具

**原始方向**：把 `Actor` 抽象为 `Entity`，把 `Intent` 抽象为 `Trigger`，把 `Motor` 抽象为 `Executor`，让角色、机关、道具共享状态驱动机制。

**判断**：机制层同构成立，但当前仓库主线仍是角色 first。不能把未来 EntityBase、ObjectDriver、VehicleDriver 当成已实现能力。

**处理**：`ADOPT + RESERVE`。

**边界**：第一期保留 proposal、claims、executor、authority route、revision 和 lifecycle 的可扩展性；不提前实现完整物体/载具/机关 runtime。

#### `127/128`：是否需要统一角色和物体的底层标准

**原始方向**：统一生命周期、状态机容器、资源占有、协调器、后端通信和存档接口，但输入源、执行器、原子单元和表现层保持专用。

**判断**：这是最值得吸收的通用化表达：统一机制，不拉平内容。

**处理**：`ADOPT`。

**解决方案**：角色继续使用 `CharacterIntentFrame` 和 `CharacterMotor`；未来物体可以实现同一机制接口，但必须拥有自己的 executor、profile 和物理边界。

#### `129/130`：先做角色，后期再统一会不会形成技术债

**原始方向**：第一期按通用方向命名接口，后期提取 EntityBase；技术债大小取决于早期边界是否清楚。

**判断**：接口预留可以减少技术债，但仅靠改名不能获得通用性。

**处理**：`CONSTRAIN`。

**解决方案**：采用“角色实现层特化，机制层可扩展”，而不是第一期强行将所有 `Character*` 改名为 `Entity*`。

#### `131/132`：给动作底座计划执行者的提醒

**原始方向**：不要构建一个角色控制器，而要构建 `Intent -> Coordinator -> Executor -> Presentation` 的通用可组合系统；建议大量使用通用命名。

**判断**：作为设计提醒有价值，但通用命名不应覆盖现实边界。

**处理**：`ADOPT + CONSTRAIN`。

**项目规则**：每个第一期设计都要检查未来实体扩展点，但当前文件、节点和验收仍清楚标注角色范围。

#### `133/134`：通用系统的性能、高并发和联网价值

**原始方向**：声称单机低并发略慢、高并发更好、联网最好，并建议 LOD、休眠、事件驱动、批处理、DOD 和回滚。

**判断**：统一协议有维护价值，但通用抽象不会自动更快，联网也不会自动获得确定性。

**处理**：`CONSTRAIN`。

**解决方案**：先测量 Arbiter、claims、composer、Motor、presentation 和 transport；性能优化优先 interest management、更新频率、睡眠、事件驱动、渲染 LOD 和专用执行后端。第一期不承诺百分比、玩家数量或回滚。

#### `135/136`：是否适用于所有有动画的事物

**原始方向**：适用于绝大多数可离散状态化、状态转换明确、表现可描述的动画事物；不适用于连续、非离散或无法状态化的动画。

**判断**：这是通用系统应有的适用边界。

**处理**：`ADOPT`。

**解决方案**：门、炮台、机关、角色等可使用同一状态驱动机制；复杂 timeline、连续模拟或纯装饰动画保留专用路径。

#### `137/138`：UI 和摄像机是否也应使用这套系统

**原始方向**：UI 和摄像机虽然没有骨骼，但也有离散状态、优先级、资源竞争和控制权切换。

**判断**：状态竞争思想可以复用，但它们不应接入角色 Motor 或角色 ActionAttempt。

**处理**：`RESERVE`。

**解决方案**：未来可以复用 priority、lease 和 presentation cue 机制；当前不把 UI/Camera 纳入角色底座实现。

#### `139/140`：不做通用系统时各类动画对象的常规做法

**原始方向**：角色使用 CharacterBody3D/FSM/AnimationTree，机械物体使用 Tween/AnimationPlayer，载具使用 VehicleBody3D，各自维护状态、网络和存档。

**判断**：说明了统一机制的长期维护价值，但不证明所有对象必须共享一条 runtime。

**处理**：`ADOPT` 作为对比材料。

#### `141/142`：做两套系统还是一套多模式系统

**原始方向**：反对做两套，建议一套代码、多个模式。

**判断**：应当保留一套语义 contract 和多种专用 execution backend，不能维护两套 gameplay truth。

**处理**：`ADOPT`。

### C. 物体破坏、实体分级与物理（143-154）

#### `143/144`：踢椅子、模型替换、特效和物理

**原始方向**：角色踢击椅子，后端判定椅子状态，模型替换、特效、动画和物理共同表现破坏结果；角色和椅子都是 `EntityBase`。

**判断**：事件链方向正确，但本地踢击不能直接修改椅子状态。

**处理**：`ADOPT + CONSTRAIN`。

**正式时序**：

```text
角色踢击动作
  -> Motor/sensor 产生 PhysicsContactEvidence
  -> ActionAttempt
  -> ESM/Gameplay 校验 affordance、对象 revision、耐久和权限
  -> committed event 或 rejection
  -> 模型替换、VFX、碎片和本地 projection
```

#### `145/146`：椅子破坏成两部分是否造成舍本逐末

**原始方向**：提出完整实体、简化实体和纯表现实体三级，并承认把所有对象 Entity 化可能舍本逐末。

**判断**：质疑成立。实体分级是合理方向，但不是当前动作底座的第一期职责。

**处理**：`ADOPT + DEFER`。

#### `147/148`：什么对象需要完整实体

**原始方向**：网络同步、存档、多系统竞争、复杂状态、玩家交互、AI、authority 判定和长期存在等条件用于判断完整实体。

**判断**：这些是评估维度，不应简化为“满足三个条件就一定完整实体”的固定公式。

**处理**：`CONSTRAIN`。

**解决方案**：由对象 policy 综合决定 authority、持久性、交互性、复杂度、网络和 representation；分级是逻辑概念，不等于某种具体节点类型。

#### `149/150`：动态实体升降级的性能

**原始方向**：长期处于低等级的对象可带来净收益，频繁切换会造成卡顿、内存碎片、状态迁移和抖动。

**判断**：方向合理，但收益必须通过 profile 和设备基准验证。

**处理**：`RESERVE`。

**未来解决方案**：切换滞回、对象池、迁移快照、延迟切换、事件驱动休眠和硬件档位；第一期只保留 simulation tier 字段，不实现动态对象升降级。

#### `151/152`：动态分级的体验、开发和硬件适配

**原始方向**：破坏后的椅子可以持续存在、碎片可以被拾取，多人看到一致结果；设备能力决定细节层级。

**判断**：可作为沙盒体验目标，但多人一致性必须由 object authority 决定，不能默认本地碎片同步。

**处理**：`RESERVE + CONSTRAIN`。

#### `153/154`：中端游戏本的体验推演

**原始方向**：以 8 核 CPU、RTX 3060 Laptop、16GB 内存和 60 FPS 目标推演 CPU/GPU/物理/AI 预算。

**判断**：可用于讨论预算方法，但硬件规格和 4-8ms 等预算不是本项目测量结果。

**处理**：`CONSTRAIN`。

**解决方案**：建立设备 profile、采集真实 stage timing、使用动态更新频率/表现 LOD；不把推演数字写成承诺。

### D. LOD、智能体、DOD 与框架定位（157-182）

#### `157/158`：实体分级与 LOD 是否正交

**原始方向**：实体 tier 决定使用哪些系统，LOD 决定精度，二者正交叠加。

**判断**：这是可用的设计语言，但不应直接生成 12 或 36 条运行路径。

**处理**：`ADOPT + CONSTRAIN`。

**解决方案**：定义逻辑维度 `entity tier`、`presentation LOD`、`simulation frequency`，再由 profile 选择少量已验证执行模式。

#### `159/160`：智能体驱动角色与群体模拟

**原始方向**：玩家可见/重要角色保持独立智能体；远处非重要角色变为群体模拟数据点，而不是继续运行完整 Agent。

**判断**：与本项目 CharacterAgent 的成本模型高度相关，是值得保留的方向。

**处理**：`ADOPT + RESERVE`。

**必须补齐**：个体到群体的状态压缩、群体事件到个体的回填、重新激活快照、重要性/距离/任务优先级阈值、权威事件顺序和隐私范围。第一期不实现完整群体 runtime。

#### `161/162`：实体分级 × LOD × AI 层级的三维体系

**原始方向**：把实体复杂度、表现精度和 AI 驱动层作为三个正交维度。

**判断**：适合长期框架设计，不应在第一期变成全面运行时矩阵。

**处理**：`RESERVE`。

#### `163/164`：与大型 MMO 性能优化架构比较

**原始方向**：认为当前理念先进，但在 OOP/ECS、缓存、多线程、AI LOD、网络 interest 和生态成熟度上落后顶级商业 MMO。

**判断**：差距判断比单纯宣称“可直接支持 MMO”可靠，但仍需要实际 benchmark。

**处理**：`CONSTRAIN`。

#### `165/166`：智能体驱动游戏是否适合 DOD

**原始方向**：近处复杂 Agent 适合 OOP，中距离简化 Agent 可混合，远处群体和碎片适合 DOD。

**判断**：按实体数量 × 逻辑复杂度分层是有效原则。

**处理**：`ADOPT` 作为未来执行策略，不进入第一期全盘迁移。

#### `167/168`：LLM 驱动群体模拟是否适合 DOD

**原始方向**：LLM 负责“大脑”生成意图，DOD 负责批量执行身体。

**判断**：认知频率和执行频率分离是正确的，但 LLM 不能进入固定 physics tick。

**处理**：`ADOPT + CONSTRAIN`。

**解决方案**：LLM/Agent 输出低频 proposal；群体数据系统批量处理位置、趋势和简化状态；两者通过版本化 snapshot、队列和回填事件连接。

#### `169/170`：OOP 和 DOD 是否可以共存

**原始方向**：玩家、Boss、重要 NPC 用 OOP，普通 NPC、群体和碎片用 DOD。

**判断**：混合架构可行，但必须统一实体 ID、事件、权威 revision 和迁移协议。

**处理**：`ADOPT + RESERVE`。

#### `171/172`：三层实体、LOD 与 OOP/DOD 如何结合

**原始方向**：实体 tier、LOD 和 AI 层是逻辑概念，不应绑定某一种实现方式。

**判断**：这是对前面把一级实体绑定 OOP 的重要修正。

**处理**：`ADOPT`。

#### `173/174`：对架构设计水平的评价

**原始方向**：评价用户处于高级到专家级，并回顾用户对过度设计、通用系统和 DOD 的质疑。

**判断**：这是对话反馈，不是技术证据。

**处理**：只保留其中关于“持续质疑边界和代价”的过程复盘，不把评价等级写入工程判断。

#### `175/176`：为什么三人团队不建议 DOD

**原始方向**：DOD 前期搭建、调试、维护和学习成本高，通常不适合小团队游戏。

**判断**：对单一游戏团队有参考价值，对可复用框架研发不构成绝对结论。

**处理**：`CONSTRAIN`。

**解决方案**：先用 OOP/节点实现角色主链，同时为批处理保留数据边界；只有 profiling 证明收益时才引入 DOD backend。

#### `177/178`：框架与游戏的成本不同

**原始方向**：框架可以承受较高研发复杂度，成本在多个游戏项目间摊销。

**判断**：方向成立，但框架必须有模块裁剪、文档、测试和使用者验证。

**处理**：`ADOPT + CONSTRAIN`。

#### `179/180`：一套混合架构是否适配所有游戏

**原始方向**：需要足够团队、人力、多个游戏验证和接受更高维护成本。

**判断**：可作为框架愿景，不能承诺“所有游戏”。

**处理**：`RESERVE`。

#### `181/182`：框架复杂度可以接受，但运行时不能超预算

**原始方向**：提出“只为使用的东西付费”，通过模块按需加载、lazy init、null implementation、性能预算和硬件适配降低运行时负担。

**判断**：原则正确；GDScript 的抽象开关不等于零成本。

**处理**：`ADOPT + CONSTRAIN`。

**解决方案**：模块化加载、睡眠/降频、专用 backend、批量处理和 profiling；不直接采用未经测量的 0.5ms/1ms/2ms 等预算。

### E. 2D/2.5D、类型适配与世界表示（183-206）

#### `183/184`：2D 和 2.5D 是否需要这套系统

**原始方向**：2D/2.5D 可复用状态机、意图、协调器、资源占有和实体分级，但不需要 3D 骨骼、root motion、IK、3D 物理和 3D LOD。

**判断**：协议机制可复用，执行器必须按维度裁剪。

**处理**：`ADOPT`。

#### `185/186`：云顶之弈是什么类型

**原始方向**：回合制策略、自动战斗、经济运营、阵容构筑和随机性结合的混合类型。

**判断**：类型分析不是角色动作契约，但说明“间接控制 -> 自动执行”的执行模式也可共享语义层。

**处理**：`RESERVE`。

#### `187/188`：云顶之弈是否 2.5D

**原始方向**：更准确地说是 3D 表现、网格化/回合制逻辑和固定视角策略。

**判断**：再次说明表现层和逻辑层可以分离，但不能直接等同于 2.5D 动作游戏。

**处理**：`ADOPT` 作为表示层参考。

#### `189/190`：合金弹头和 Minecraft 的启示

**原始方向**：合金弹头需要极简 2D 动作系统；Minecraft 体现数据驱动、区块、资源复用和按需加载。

**判断**：底座必须可裁剪；“完整系统”不是所有游戏都应加载的 runtime。

**处理**：`ADOPT`。

#### `191/192`：体素世界还是预设美术资源

**原始方向**：沙盒、可破坏、多人和长期迭代适合数据驱动/体素；线性手工设计适合预设资源；最佳方案是逻辑数据化、表现可替换。

**判断**：逻辑/表现分离可吸收，体素不是当前角色动作底座的必要前置条件。

**处理**：`ADOPT + DEFER`。

#### `193/194`：原子级美术资源与数据驱动组合

**原始方向**：以模块化美术原子替代体素最小单元，通过 socket 和数据组合生成大结构。

**判断**：适合未来资源管线，但每个原子仍需碰撞、socket、材质、LOD、authority ID 和版本。

**处理**：`RESERVE`。

#### `195/196`：原子美术是否可以由体素构成

**原始方向**：体素可以作为原子模型、全局网格数据或制作工具。

**判断**：三种方式的渲染、碰撞、存档和网络成本不同，不能视为同一实现。

**处理**：`RESERVE`。

#### `197/198`：体素审美与 Gaussian Splatting

**原始方向**：体素可以形成风格化美术；Gaussian Splatting 是另一种表示技术。

**判断**：与动作底座直接关系很弱。Gaussian Splatting 不是骨骼动作、碰撞或 authority 的替代品。

**处理**：`DEFER`。

#### `199/200`：美术方案和“美术即碰撞体”

**原始方向**：从可破坏性、碰撞来源、组合性、性能、网络和存档比较体素、网格和原子美术；强调体素美术天然可作为碰撞体。

**判断**：表示方式确实会改变逻辑和资源成本，但“美术即碰撞体”不能自动成为权威物理模型。

**处理**：`CONSTRAIN`。

#### `201/202`：体素的原生优势

**原始方向**：数据即世界、统一空间表示、程序化、存档、网络和批处理。

**判断**：这些优势依赖体素世界的具体数据结构和 chunk 更新策略，也伴随内存、碰撞重建和细粒度成本。

**处理**：`CONSTRAIN + DEFER`。

#### `203/204`：近景网格、远景体素

**原始方向**：体素作为世界数据真相，近景用网格表现，远景用体素或简化表示。

**判断**：可作为未来 world representation，但不能改变角色 semantic action、claims、Motor 和 authority contract。

**处理**：`RESERVE`。

#### `205/206`：体素替换非近场角色建模

**原始方向**：近景使用骨骼网格，远景和群体使用体素角色，按距离切换表示。

**判断**：可作为 presentation/AI LOD，但远景体素角色不应被当成可执行完整武器动作的角色。

**处理**：`RESERVE + CONSTRAIN`。

## 6. 吸收后的统一动作底座

### 6.1 多动作并发

移动是持续控制 lease；攻击、瞄准、换弹、装备、交互和受击是 `ActionInstance`。同一 tick 可有多个动作，但必须通过统一 claims 和物理 profile：

```text
movement + left_leg_chain + right_leg_chain + support_contact
right-arm melee + weapon_slot:sword + weapon_hit_volume:sword
```

如果 claims 和 root/pelvis/support 不冲突，移动和上半身动作可以并发。全身攻击、冲刺、倒地或需要腿部协调的动作必须显式声明 `drive_locomotion`、`replace_locomotion` 或 `suspend`，不能靠动画看起来“不冲突”来推断。

### 6.2 外部全身动画

外部 clip 进入运行时前必须经过：

```text
GLB
  -> canonical skeleton mapping
  -> rest pose / unit / slot validation
  -> track impact / root / pelvis / lower-body analysis
  -> marker / cancel / claims / physics profile validation
  -> native_upper_body | derived_upper_body | full_body_exclusive | drive_locomotion | additive
  -> qualification report
  -> registry admission
```

full-body clip 默认不是 upper-body concurrent。没有合格的 derived/native profile 时，只能独占、排队、拒绝或 presentation-only。

### 6.3 第一阶段武器切片

第一期不做完整 Weapon runtime，只证明接口和权威边界：

```text
EquipmentBinding
  -> WeaponActionProfile
  -> canonical claims
  -> ActorActionArbiter
  -> RolePresentationAdapter / Motor
  -> PhysicsContactEvidence
  -> ActionAttempt
  -> ESM / Gameplay AuthorityResult
```

第一期要求：

1. 一个合格握持槽和手部锚点。
2. 一个带 phase marker 的标准 melee action。
3. 一个从 marker 到 `ActionAttempt` 再到 authority recovery 的闭环。
4. 一个 `hitscan` semantic request/authority validation fixture。
5. 不包含弹药、弹匣、膛室、弹道、双持、拼刀、格挡和任意道具自动武器化。

### 6.4 物理和权威

本地碰撞和传感器只能产生：

```text
PhysicsContactEvidence(local_only=true)
```

只有 ESM/Gameplay 才能产生：

```text
committed damage / object mutation / resource mutation / status result
```

本地 root motion、击中 marker、ray query、武器 hit volume 和碎片物理不能绕过 `ActionAttempt`。

### 6.5 Agent、INF 和 Siming

合法方向：

```text
INF facts / goals / evidence / constraints
  -> CharacterAgent proposal
  -> IntentProposal
  -> Arbiter
  -> CharacterIntentFrame
  -> Motor / Presentation
  -> ActionAttempt
  -> ESM / Gameplay result
```

禁止 Agent、INF 或 Siming 直接写 Transform、AnimationTree、damage、death、inventory、equipment 或 authoritative status。Siming 仍然只能产生 catalyst/context/presentation hint。

### 6.6 Mode B 联网

第一期联网同步的是：

- semantic control intent；
- action instance/request；
- `ActionAttempt`；
- idempotency key 和 expected revisions；
- `AuthorityResult`；
- Gameplay projection。

第一期不做：

- raw bone pose；
- 每帧动画同步；
- netfox rollback；
- server-authoritative `RigidBody3D`；
- 跨机逐位 Godot 物理确定性。

## 7. 项目级问题与解决方案矩阵

| 问题 | 当前风险 | 解决方案 | 阶段 |
| --- | --- | --- | --- |
| `CharacterReplica` 仍直接移动 | 第二条 locomotion truth | 收敛到 `CharacterMotor`，静态审计禁止直接 writer | P0 |
| 没有统一并发仲裁 | 互相覆盖、取消和优先级漂移 | `ActionInstance` + lease + claims + `ActorActionArbiter` | P0 |
| 外部 full-body clip 被误当并发动作 | 穿脚、漂移、root 冲突 | build-time qualification 和显式 fallback | P0 |
| 武器只有骑士专用 modifier | 无法扩展枪械和其他角色 | `EquipmentBinding` + `WeaponActionProfile` | P0 |
| marker/collider 被当成命中真相 | 本地作弊和错误世界状态 | `PhysicsContactEvidence` -> `ActionAttempt` -> authority | P0 |
| Agent/INF 直接污染表现或身体 | 认知层和具身层耦合 | 统一 `IntentProposal` ingress | P0 |
| Gameplay mirror 被误当物理同步 | 网络边界虚假完成 | Mode B 与未来 body stream 分离 | P0 |
| 没有可见的 claims/Motor/authority 调试 | 无法验证并发和性能 | debug overlay、test panel、animation debugger、performance monitor | P0 |
| 远处角色仍运行完整 Agent | 高并发时预算不可控 | entity tier × presentation LOD × AI level，先预留再实现 | P1/P2 |
| 全盘 DOD 过早引入 | 框架复杂度转嫁到当前游戏 | OOP 主路径 + 可替换批处理 backend | P2 |
| 任意道具自动武器化 | 物理、IK、权威和网络不可控 | affordance/profile/custody/qualification gate | P2 |
| 体素被当成当前角色真相 | 表示层侵入动作和 authority | 体素只作为未来 world/presentation representation | P3 |

## 8. 第一阶段执行顺序

唯一实施顺序仍然是：

```text
baseline
  -> shared tags / proposal / frame
  -> leases / claims / parallel arbitration
  -> MotionContribution / PhysicsMotionCommand / Motor
  -> contact evidence / root recovery
  -> external asset qualification
  -> two package staging
  -> presentation adapter
  -> minimum weapon binding/profile
  -> CharacterAgent / INF bridge
  -> ESM / Gameplay ActionAttempt
  -> Mode B transport
  -> debug / replay / two-character runtime proof
```

第一阶段完成标准：

1. 两个外部角色包通过 canonical mapping 和 qualification report。
2. Player、NPC 和 Agent 使用同一 Actor/Motor 路径。
3. 移动与合格上半身动作可以并发；全身动作明确独占或 fallback。
4. 至少一个 held-item slot/hand anchor 和一个 melee action 完成 authority 闭环。
5. hitscan semantic fixture 通过 schema、route、idempotency 和拒绝非法客户端结果的测试。
6. Agent/INF 能产生语义 proposal 并得到可见本地结果。
7. 本地 contact 在没有 committed settlement 时不改变世界。
8. debug、replay、Mode B 和真实 Godot/backend 证据齐全。

## 9. 后续路线

### P1：从动作底座到可玩基础战斗

- ammo、magazine、chamber 和 fire cadence；
- ADS、spread、recoil、weapon IK；
- reload/switch/interruption/recovery；
- 标准 projectile authority；
- 更完整的上半身 qualification 和 attachment profile。

### P2：可组合战斗和实体互动

- dual wield；
- block/parry/clash；
- 标准化 improvised tool profile；
- 物体 durability、破坏和 authority object revision；
- 个体 Agent 与群体模拟迁移；
- 少量高价值对象的实体 tier/LOD 动态切换。

### P3：框架和表示层扩展

- atomic action registry 和并行组；
- motion matching；
- ragdoll authority；
- networked physical authority；
- OOP/DOD specialized backend；
- 原子美术资源、体素 world data、近景 mesh/远景 proxy；
- 远景体素角色或 impostor representation。

## 10. 明确拒绝或不应提前承诺的内容

以下内容不应因为 DeepSeek 的表述而进入当前主 spec 或被报告为已实现：

- 任意 `RigidBody3D` 自动成为武器；
- 仅通过 `PinJoint3D` 把道具绑定到手骨骼；
- runtime 任意删除动画轨道；
- 每帧 AI 重新生成完整骨骼姿态；
- “44 个原子动作”或任何未经测量的组合数量；
- “CPU 下降 90%”“支持 1000 玩家”等未经 benchmark 的数字；
- 通用抽象天然比专用代码更快；
- Gameplay mirror 等于物理 authority；
- 体素天然提供跨机器物理确定性；
- 近景/远景 representation 自动等于可执行动作能力；
- 当前项目已经具备完整剑战、枪战或任意道具战斗。

## 11. 相关文档索引

### 设计真相

- `docs/superpowers/specs/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`
- `docs/superpowers/specs/2026-09-14-character-physics-motion-and-contact-subspec.md`
- `docs/superpowers/specs/2026-09-14-character-animation-asset-qualification-and-concurrent-realization-subspec.md`
- `docs/superpowers/specs/2026-09-14-character-esm-action-attempt-settlement-subspec.md`
- `docs/superpowers/specs/2026-09-14-character-connected-action-and-physical-replication-subspec.md`

### 唯一实施顺序

- `docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`

### 专题任务细化

- `docs/superpowers/plans/2026-09-14-character-shared-contracts-arbitration-and-tools-implementation-plan.md`
- `docs/superpowers/plans/2026-09-14-character-animation-asset-qualification-and-concurrent-realization-implementation-plan.md`
- `docs/superpowers/plans/2026-09-14-character-physics-motion-and-contact-implementation-plan.md`
- `docs/superpowers/plans/2026-09-14-character-esm-action-attempt-settlement-implementation-plan.md`
- `docs/superpowers/plans/2026-09-14-character-connected-action-and-physical-replication-implementation-plan.md`

### 当前事实与操作

- `docs/character/character-action-foundation-current-state.md`
- `docs/character/character-runtime-design-drift-audit.md`
- `docs/character/character-action-foundation-operator-guide-and-index.md`
- `docs/character/character-action-asset-interface.md`

## 12. 最终决策

DeepSeek 对话最重要的贡献不是证明“应该做一个万能实体系统”，而是帮助明确了动作底座的真正价值：

```text
统一语义入口
+ claims-based 并发
+ 唯一物理执行者
+ 可资格化外部资产
+ 证据与权威结算分离
+ 慢速认知与快速执行分离
+ 一套 contract、多个专用 backend
```

第一期应把这些机制做实，并通过两个外部角色、一个近战 authority 闭环和一个 hitscan semantic fixture 验证。通用实体、动态 LOD、群体 DOD、体素世界和任意道具武器化都应建立在这条稳定主链之上，而不是反过来重写角色动作底座。

## 附录 A：完整目录前半段（轮次 1-43）的详细分析

### A.1 证据边界

完整目录把对话分成 90 个轮次，但目前只有轮次 `1-43` 的标题目录，没有对应的问答正文。因此本附录回答的是“这些轮次明确把哪些问题带入架构，以及这些问题现在应如何落位”，而不是声称复原了当时的助手原话。

此前第 5 节的 `113/114` 至 `205/206` 逐组分析对应目录轮次 `44-89`，其证据等级较高；本附录的所有结论都使用 `目录级推断` 语言。目录中的主题归类存在交叉，例如轮次 `26` 同时属于动作底座和模块化，轮次 `59` 同时属于原子动作和 LOD。这是交叉索引，不是重复实现的理由。

### A.2 轮次级决策矩阵（目录级）

| 轮次 | 目录议题 | 目录暴露的设计问题 | 吸收结论 | 对第一期的影响 |
| --- | --- | --- | --- | --- |
| 1-2 | Godot 战斗插件盘点、插件能否编辑 | 依赖插件是否能成为项目核心，许可证和扩展边界是否可控 | `CONSTRAIN`：插件只能作为能力提供者或参考，不能取得动作、Motor 或 authority 所有权 | 建立插件评估表；不因调研直接增加依赖 |
| 3-4 | 3D 实时战斗框架、通用战斗底座选型 | 通用战斗框架是否覆盖实时动作、组合和后端结算 | `ADOPT + CONSTRAIN`：吸收能力分层，不复制外部框架的平行 FSM 或网络模型 | 继续使用统一 proposal/claims/attempt 契约 |
| 5-7 | Unity Combat System Framework 设计、开源框架比较与用法 | 外部框架的分层、资源、连招和编辑器经验如何转化 | `ADOPT` 作为架构参考；`REJECT` 直接照搬节点树、命名和运行时 ownership | 将参考项目转化为验收场景和接口，而不是源码依赖 |
| 8-9 | 复刻《永劫无间》的 Godot 能力与单机可行性 | 高密度动作、网络、镜头和战斗内容的边界 | `CONSTRAIN`：单机可做局部体验，多人级确定性、内容量和网络权威不能由插件自动提供 | 第一阶段只做本地 kinematic + Mode B 语义联网 |
| 10 | 工业化动作系统与可视化连招编辑 | 动作资源如何被组合、调试、取消和复用 | `ADOPT + DEFER`：保留 action profile、timing、claims、cancel；可视化连招编辑延期 | 资产 manifest 和 timing sheet 属于 P0，完整 editor 属于后续 |
| 11 | 动作底座支持 FPS | 近战动作模型是否能承接瞄准、枪械、视角和射击 | `ADOPT + CONSTRAIN`：FPS 通过武器 profile、瞄准 proposal、hitscan route 接入，不新增 FPS 专用身体 truth | 第一阶段仅保留 hitscan semantic fixture |
| 12 | 参考项目、插件、技术架构完整方案 | 调研结论如何变成可执行架构 | `ADOPT`：采用 source adapter、arbiter、executor、presentation、authority 分层 | 与主 spec 的 ownership 结构一致 |
| 13-14 | 动作底座与外骨骼/骨骼动画、根动画与骨骼动画并存 | 外部全身 clip 如何与局部并发、root motion 和 Motor 共存 | `ADOPT + CONSTRAIN`：所有 clip 先资格化；root motion 只是候选贡献，full-body 默认独占 | P0 资产资格化、root policy、full-body fallback 必须完成 |
| 15-16 | Unity 开源骨骼动画复用、视频提取动画 | 外部动作来源是否能直接进入 Godot | `CONSTRAIN`：资源可以借鉴或导入，但必须满足授权、骨架、单位、rest pose、marker 和 claims 契约；视频提取不能跳过资格化 | P0 只接受外部制作的 runtime-ready 资产，不承诺自动视频转动作 |
| 17-18 | Godot 3D 动作游戏步骤、现在不做战斗但为未来准备 | 如何先交付可动角色，又不锁死未来战斗 | `ADOPT`：先做统一身体、移动、外部动画和证据链，再叠加武器/战斗 | 当前第一期路线正是 asset-driven action foundation |
| 19 | Agent 驱动行为树和动画树 | 认知层是否直接控制行为树、AnimationTree 或 clip | `ADOPT + CONSTRAIN`：Agent 只产出 goal/intent/constraint/proposal；本地 arbiter 决定动作和表现 | P0 必须有 Agent/INF ingress，禁止 direct pose/body writer |
| 20 | 感知决策完成后是否先做通用动作底座 | 语义上游已存在时，具身层是否能独立收敛 | `ADOPT`：动作底座作为 CharacterAgent 的执行边界优先实现 | P0 先固定 `CharacterControllerPort` 和 frame |
| 21 | 为永劫 + FPS 级别战斗打基础 | 一个动作底座如何容纳近战、枪械、移动和受击 | `CONSTRAIN`：基础设施现在做 claims、timing、authority；具体战斗内容分阶段 | P0 一个 melee + 一个 hitscan fixture；完整战斗 P1/P2 |
| 22 | 日常/战斗模式切换 | 模式切换是否会产生两套 FSM 和互相抢写 | `ADOPT + CONSTRAIN`：模式是 control/presentation profile 和 proposal policy，不是第二套身体运行时 | 将 mode 作为 proposal metadata/profile 输入；需要切换测试 |
| 23-25 | 3D 沙盒底座、模块化热插拔、模块化利弊 | 功能组合与运行时成本如何平衡 | `ADOPT + CONSTRAIN`：核心身体契约默认存在，内容能力可配置启用；不做任意运行时 hot-unplug | P0 保持固定核心；模块裁剪和动态加载延期 |
| 26-28 | 引入模块后是否改底座、底座不热插拔、根节点挂载内容 | 根节点 ownership 和默认加载策略是否清楚 | `ADOPT`：Motor、arbiter、runtime snapshot、presentation port 属于稳定核心；模块通过 adapter 注册 | P0 审计根节点 writer；禁止插件或模块新增第二 Motor |
| 29-30 | 模拟经营/剧本杀影响、修正为 3D 世界中的基础动作 | 叙事、经营、社交玩法是否侵入动作底座 | `ADOPT + CONSTRAIN`：玩法只产生语义 intent/affordance/authority request，不改身体层 | P0 保留 interaction/affordance route；复杂玩法留在上游 domain |
| 31-32 | Agent 控制 UI、动作库和复杂连招；底座是否配合 Agent | Agent 是否应该编排 UI、连招和原子动作 | `CONSTRAIN`：Agent 可提出高层复合意图，不能直接选择未经资格化 clip 或绕过 claims；UI 只复用状态/优先级思想 | P0 用 proposal/action profile；原子展开、UI runtime 延期 |
| 33-35 | 原子动作库、原子动作设计、覆盖互动需求 | 如何让 AI 组合拿取、踢击、书信等复合行为 | `RESERVE`：保留 `atomic_sequence` 和未来 registry；第一期必须为空，复合行为先用外部 clip + semantic action | 资产 descriptor 保留字段，禁止 atom expansion |
| 36-37 | Actor 物理性质永久保持、力量升级 | 质量、力量、速度和成长应归动作层还是 Gameplay | `ADOPT + CONSTRAIN`：有效属性由 Gameplay/ESM projection 提供，Motor 只消费受限 physics profile；成长不能直接篡改动画或速度上限 | P0 固定 profile/ref 边界；成长和资源结算后续接入 |
| 38-39 | 新动作底座完整方案、初版不做原子动作 | 设计是否需要在第一期一次完成全部能力 | `ADOPT`：采用“基础契约先行、原子扩展预留”的分期策略 | 与当前 master spec 和唯一 plan 一致 |
| 40-41 | 参考项目/插件完整方案、全对话回顾 | 调研材料如何收敛成一个版本，避免多个漂移方案 | `ADOPT`：建立权威层级、单一实施计划和 current-state ledger | 新分析文档只做决策记录，不成为第二套 spec/plan |
| 42-43 | 统一角色身体重构评估、预期动作体验 | 重构是否真的能产生目标体验，还是只完成抽象 | `ADOPT + CONSTRAIN`：体验必须由两个真实外部角色、移动/上半身并发、近战 authority 和失败恢复证明 | P0 完成标准使用可观察运行证据，而非“架构存在” |

### A.3 前半段讨论对当前方案的新增价值

#### 1. 插件不是架构决策的替代品

轮次 `1-7`、`12`、`15` 和 `40` 反复围绕插件和参考框架展开。它们共同说明：插件调研回答的是“已有能力能否减少实现量”，并不回答“谁拥有身体位移、动作占有、物理证据和世界后果”。

因此需要把插件放进五项评估矩阵，而不是写成“推荐安装”列表：

| 评估项 | 必须回答的问题 | 当前决策 |
| --- | --- | --- |
| 许可证与来源 | 能否修改、分发、商用，是否依赖不可控二进制 | 未通过审查前不能成为生产依赖 |
| 运行时 ownership | 是否会接管 `CharacterBody3D`、AnimationTree、网络或伤害 | 不能取得 Motor、authority 或 claims owner |
| 数据/资源边界 | 是否支持 canonical mapping、外部 clip、timing、mask 和 fallback | 只能通过现有 descriptor/qualification adapter 接入 |
| 扩展与替换 | 能否替换执行器、transport、settlement 和 presentation | 只接受可包裹、可禁用、可测试的能力 |
| 性能和证据 | 是否有 profiling、多人/高并发数据和 Godot 版本兼容证据 | 没有 benchmark 就不能承诺性能收益 |

这也解释了为什么当前方案没有把 `WeaponLayer`、插件控制器或外部 GAS 直接升格为第二套运行时。插件可以被使用，但必须服从项目 contract。

#### 2. 模式切换应是 profile，不是平行控制器

轮次 `11`、`18`、`21`、`22`、`30-32` 暗示了多种控制语境：日常移动、战斗、FPS 瞄准、交互、社交/经营和 Agent 自动执行。正确抽象不是为每种语境各建一套 FSM，而是：

```text
control_mode / capability / affordance / status
  -> source proposal
  -> same claims arbiter
  -> same CharacterIntentFrame
  -> mode-specific presentation profile
```

模式只能改变允许的 proposal、动作 profile、镜头和表现权重；不能改变唯一 Motor、ActionAttempt 和 authority owner。当前主 spec 已有 `control_mode`、`allowed_control_modes` 和同一 arbiter 边界，但第一期仍需用“日常移动 -> 战斗动作 -> 退出/拒绝”的固定测试证明没有第二条 body writer。

#### 3. 外部动画资源是第一期的真实瓶颈

轮次 `13-18` 把问题从“有没有动作系统”转成“外部 full-body 资源能否稳定进入系统”。这比再增加一个战斗插件更关键。第一期资源门槛应保持：

```text
外部 GLB/动画
  -> canonical skeleton/rest pose/unit 校验
  -> 实际轨道影响分析
  -> full-body / upper-body / locomotion 资格判定
  -> marker、cancel、claims、physics profile
  -> qualification report
  -> registry admission
```

从视频或其他框架获取的动作可以作为生产输入，但不能跳过来源许可、骨架适配、时序标注、root-motion 策略和权威证据契约。没有资格报告的动作只能是 preview/presentation-only，不能参与并发或产生 `ActionAttempt`。

#### 4. Agent 的价值在“提出什么”，不在“怎么写骨头”

轮次 `19-20`、`25`、`31-35` 共同指向同一个边界：智能体可以理解上下文、选择目标、提出连贯行为，不能直接驱动 `AnimationTree`、Transform、伤害或原子动作执行。原子动作未来也必须先展开为普通 `ActionInstance`，再经过 claims、timing、cancel、physics 和 authority。

这保证了 CharacterAgent/INF 的推理频率可以低于 physics tick，同时保留可回放、可审计和可拒绝的执行路径。

#### 5. 物理属性和成长必须走 Gameplay projection

轮次 `36-37` 提出了动作体验中常见但容易越权的需求：角色力量、重量和耐久会长期保持并随成长变化。正确链路是：

```text
Gameplay/ESM effective stats
  -> capability/status/physics-profile projection
  -> bounded MotionContribution / ActionAttempt
  -> Motor 或 authority settlement
```

力量不能直接让 Agent 写入速度，重量不能直接让本地动画判定伤害，成长也不能绕过 revision、资源和权限校验。这样既支持属性驱动的动作差异，也不会让角色身体层变成第二个 Gameplay 数据库。

### A.4 完整目录揭示的主要矛盾及解决方式

| 矛盾 | 不解决的后果 | 当前解决方式 |
| --- | --- | --- |
| 采用插件 vs 保持项目控制权 | 插件接管 Motor、动画或伤害，形成平行 truth | 插件只做 adapter、工具或参考；核心 contract 自有 |
| 模块化热插拔 vs 动作底座稳定 | 运行中删除核心节点导致 lease、claims、Motor 丢失 | 核心默认加载；能力模块可配置启用，runtime hot-unplug 延期 |
| 通用实体 vs 角色 first | 过早抽象造成 EntityBase 万能化和验收失焦 | 机制层可扩展，第一期执行层仍是角色专用 |
| 原子动作 AI 组合 vs 外部全身 clip | 未资格化轨道被拆解后穿插、穿脚和 root 冲突 | `atomic_sequence=[]`；先用 qualified semantic action |
| 动画表现 vs 物理/世界真相 | marker/collider 直接造成伤害或破坏 | `PhysicsContactEvidence -> ActionAttempt -> authority` |
| LLM/Agent 低频推理 vs physics 高频执行 | 固定 tick 被网络/模型调用阻塞，结果不可重放 | proposal/snapshot 异步，fixed tick 只消费已版本化输入 |
| OOP 框架愿景 vs DOD 性能想象 | 未测量就引入 ECS/DOD，开发成本和调试复杂度先上升 | 角色 OOP 主路径；只有 profiling 证明收益才加入批处理 backend |
| 高保真多人愿景 vs Mode B 现实 | 把 mirror 或语义消息误报成物理同步 | 当前只承诺语义动作和 authority projection，raw pose/rollback 延期 |
| 美术即碰撞体 vs 物理安全 | 网格/体素表示被误当作权威碰撞和可破坏状态 | 表示、碰撞证据、authority 状态分层；体素属未来表示方向 |

### A.5 对第一期的最终影响清单

目录前半段没有推翻当前主 spec，但使以下事项从“可选理念”升级为“必须明确的实施约束”：

1. **插件政策必须写死**：不引入插件拥有的 CharacterBody3D、动作 FSM、伤害或网络 authority；所有插件采用都要有许可证、版本、ownership、扩展点和 profiling 记录。
2. **模式 profile 必须可观测**：至少测试日常移动、战斗动作、瞄准语义和 Agent proposal 在同一 arbiter 下切换，确认没有第二 Motor 或第二动作真相。
3. **动作编辑器不属于第一期闭环**：第一期交付 manifest、timing sheet、qualification report 和调试器；可视化连招编辑器、原子动作展开和 motion matching 属于后续工具链。
4. **属性/成长要保留 projection 入口**：`physics_profile_ref`、capability/status 和 authority result 要能表达力量、重量、耐久等变化，但不把成长逻辑塞进 Motor。
5. **第一期验收必须是体验证据**：两个外部角色包、移动与合格上半身并发、全身动作 fallback、一个 melee authority 闭环、一个 hitscan semantic fixture、Agent/INF proposal、拒绝和恢复路径。

### A.6 不应从目录标题推断的内容

仅凭完整目录，不能断言以下事项已经在 DeepSeek 原文中得到技术证明，也不能把它们写入当前项目事实：

- 某个 Godot 插件已经满足本项目的全部 claims、Motor、ESM 和 Mode B 要求；
- Unity 框架的骨骼动画可以无条件复用或自动 retarget；
- 视频提取动画已经具有合法授权、稳定 marker 或可用 root motion；
- 原子动作数量、组合数量、CPU/FPS/玩家规模和 DOD 收益；
- 单机可行性自动推出多人联网、回滚或跨机物理确定性；
- 统一框架自动适用于所有游戏类型、UI、摄像机、体素对象和任意道具；
- 当前仓库已经完成剑战、枪战、复杂连招、动态实体 LOD 或群体模拟。

本附录不会改变第 1 节列出的权威层级。若后续获得轮次 `1-43` 的原文，应逐条替换目录级推断，并只在有实现或 benchmark 证据时更新主 spec/plan 的事实状态。
