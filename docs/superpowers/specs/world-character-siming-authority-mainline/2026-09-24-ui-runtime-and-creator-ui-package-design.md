# UI Runtime 与创作者 UI Package 设计

Status: `design-only; implementation not authorized`

Date: `2026-09-24`

## 摘要 / Summary

本设计为 `world-character-Siming-authority` 主线定义跨玩法的 UI Runtime。它以
**功能稳定、体验可变**为原则：每个游戏必须内置一套完整、可玩、无需模型即可运行的
UI；玩法包可带来受治理的 UI 功能扩展；司命只在已准入的能力、布局和内容槽位内组装
体验并请求多模态内容增量。

This design defines a cross-game UI Runtime. A game remains fully playable from
its built-in UI without a model. Gameplay packages add governed UI extensions;
Siming can only compose approved capabilities and request approved-slot content.

本设计不授权实现，也不把 UI Runtime 变成 world-truth owner、通用客户端代码执行器，
或第二套 gameplay/package authority。

## 目标与非目标 / Goals and Non-goals

### Goals

1. 使 Godot `Control` 成为第一个 renderer，同时保持 UI plan 不含 Godot 节点路径、
   GDScript 或引擎私有类型，以允许未来 Web/移动端实现同一协议。
2. 将 UI 功能、交互语义、状态、可访问性与美术/多模态表现分离。
3. 使司命能够在 scope-filtered runtime 信号下选择已审核的 UI 体验方案，并以可审计、
   可回放、可降级的方式请求槽位内容。
4. 使创作者能用相同的组装与生成能力制作 UI 草案，但只有经验证、审核和冻结的包才能
   进入玩家运行时。
5. 以 UI-first 的历史治理游戏为第一个验证案例，而不把它硬编码为底座唯一玩法。

### Non-goals

- 不允许运行时模型生成或执行 GDScript、任意节点树、任意网络请求或新的点击行为。
- 不允许司命改写 `UICapability` 的功能、structured intent、权限、字段、确认流程、
  权威事实标签或数据 scope。
- 不允许 UI、本地 renderer、UI profile 或模型绕过 ESM、Gameplay authority、
  `GameplayEventStore`、System L6 或既有 backend result 链写世界真相。
- 不在本设计中完成完整历史宏观模拟、通用 UI DSL、全平台 renderer、创作者市场结算或
  production identity。

## 所有权与固定边界 / Ownership and Hard Boundaries

| Concern | Owner | UI Runtime boundary |
| --- | --- | --- |
| 世界/玩法事实、结算、回放 | 既有 domain authority / GameplayEventStore / ESM | UI 只读受过滤 view 与 committed result |
| 跨层事件与前端投影 | System L6 / projector | UI Runtime 消费 eligible projection，不取代 canonical event log |
| 本地输入与可见表现 | Godot renderer / local presentation | renderer 不确认玩法事实 |
| 全局态势与高层体验建议 | Siming | 只输出受限 UI proposal，不直写 renderer |
| UI 功能语义与交互契约 | `UICapabilityRegistry` | 不能由 profile、参考资产或生成结果改写 |
| UI 包、扩展、profile、媒体资产的治理 | creator control plane / package admission | activation 以 immutable revision/digest 为准 |

`Siming -> UI` 的“控制”是体验决策权，不是任意客户端执行权。所有 proposal 都须经
UI Policy Gate 重新验证；renderer 只执行已经批准的 `UIExperiencePlan`。

## 三层发布模型 / Three-tier Publication Model

```text
Base Game UI Package
  +-- complete playable capabilities, states, accessibility, fallbacks
  |
  +-- Gameplay UI Extension Package(s)
  |     +-- governed domain panels, selectors, experience modes
  |
  +-- runtime UIExperiencePlan increments
        +-- approved package/layout selection, emphasis, approved-slot content
```

### 1. Base Game UI Package

每个游戏 revision 必须声明一个 immutable `BaseGameUIPackage`。它在无模型、离线媒体、
生成失败或司命禁用时仍保证完整可玩，至少保留：关键 capability、输入、状态、后端回执、
错误恢复、键鼠/手柄路径、无障碍语义和内置 fallback。

它是功能下限；体验增量不得删除关键能力、改变关键操作的语义或把未提交状态伪装为已生效。

### 2. Gameplay UI Extension Package

玩法包可以声明 versioned `GameplayUIExtensionPackage`，但只能扩展其已准入玩法能力、
数据 view 和体验模式。它不能以 package/profile 形式偷渡新的 canonical owner、任意
数据 selector 或客户端行为。

### 3. Runtime Experience Increment

司命可在 session/event safe boundary 上选择已经激活的 package 和 layout variant，调整
允许的面板展开、阅读优先级、信息密度、提示强度和叙事节拍，并为已注册 slot 请求内容。
它是短寿命表现计划，不能替代 package activation，也不能让游戏等待模型完成才可操作。

## 功能壳、美术 Adapter 与 Binding Profile

UI 的核心对象是 `UICapability`，不是参考资产。它固定声明：

- `capability_id`、用户任务与允许的 `action_id`；
- 经 scope-filtered projection 取得的 data view；
- 输入字段、验证、确认、pending/accepted/refused/blocked 状态；
- focus order、hit target、键鼠/手柄输入、accessibility role/label；
- 最低可见信息和 fallback 行为。

每个 renderer 以稳定的 capability runtime shell 承载交互；美术只通过
`UICapabilityBindingProfile` 接入：

```text
UICapability Runtime Shell
  +-- fixed action/state/accessibility/data contract
  `-- UIArtAdapter
        `-- UICapabilityBindingProfile
              +-- admitted layout variant
              +-- semantic-state -> visual-state mapping
              +-- approved image/font/audio/motion slots
              `-- fallback profile
```

Binding profile 可改变背景、边框、主题、非关键动效、音效、插画、布局许可范围与叙事槽位；
它不得改变点击命中区、焦点顺序、action payload、确认路径或 authority status 语义。
装饰性节点默认不接收输入；输入只能由 capability shell 的稳定节点接收。

## 通用 UI Direction Skill 与玩法 Profile

`UI Direction Skill` 是司命的通用领域技能，而不是自由 prompt。其 versioned knowledge
至少包括：

- capability 的用途、关键操作、不可遮蔽信息和降级约束；
- 通用体验模式与其可组合条件；
- approved UI package、layout variant、reference bundle 和 slot 能力；
- 多模态 provider 的输入规格、预算、时延、审核与 fallback；
- 仅限允许 scope 的会话体验信号，例如重复失败、关键风险未读、输入设备与无障碍偏好。

每个游戏/玩法包提交 `UIDirectorProfile`，由通用技能解释。Profile 至少锁定：

- 玩法的目标、情绪节拍、信息优先级；
- `UICapability` 到体验模式的映射；
- 可引用 package、layout、reference bundle 和 content slot 的 allowlist；
- 司命允许调整的参数范围、频率、有效期与 safe boundary；
- 哪些状态必须始终显著显示；
- fallback 与禁止项。

Profile 不能新增 capability、action、selector、owner 或 renderer 执行代码。需要这些能力时，
必须走新的底座能力 admission，而不能用 profile 绕过审核。

## 体验计划协议 / Experience-plan Protocol

```text
committed event + scope-filtered session view + active package revisions
  -> UI Director Adapter
  -> UIExperienceProposal              (untrusted candidate)
  -> UI Policy Gate + registry checks
  -> UIExperiencePlan                  (approved, renderer-consumable)
  -> renderer + optional slot requests
```

`UIExperienceProposal` 至少包含 `proposal_ref`、world/session refs、触发 committed event refs、
目标 UI scope、candidate package/layout refs、parameter bounds、expected revision vector、
deterministic seed、expiry 和 explanation digest。

获准 `UIExperiencePlan` 必须固定 package/profile/binding digests、filtered-view revision、
slot content refs、seed、expiry 与 fallback ref。它是 presentation trace，不进入 Gameplay
canonical ledger；但应与 world/session revision 关联保存，以重现当时的体验选择，不在回放时
重新请求模型。

UI Policy Gate 对未知、未激活、过期、越 scope、隐私超界、预算超限、不可访问、未审核或
stale proposal 零副作用拒绝，并回退到 Base Game UI Package。

## 参考资产与多模态内容 / References and Multimodal Content

参考资产只服务既定功能，不定义功能。`UIReferenceBinding` 必须有独立身份和 provenance，
而不能退化为裸文件路径。最低信息包括：

- `reference_id`、source scope/ref、snapshot/digest、审核状态与有效范围；
- 语义类型、优先级/权重、适用 package/page/panel/slot；
- `preserve_targets` 与 `suppress_targets`；
- 显式挂载、自动选择或上游继承的 lineage；
- 最终使用、抑制、覆盖、超出 scope 或无效的 resolution status。

UI 参考的硬优先级如下：

1. 功能、交互、事实状态、权限和无障碍契约；
2. 游戏/玩法包的产品身份与已审核 design system；
3. 已注册的信息层级与 layout 许可；
4. 参考资产的表现约束；
5. 新生成内容的表现变体。

低优先级资产不得借美术、文案或动效覆盖高优先级语义。每次运行时决议产出
`UIReferenceResolutionArtifact`，记录最终实际采用、未采用或被抑制的参考及理由；它附属于
UI plan/package，不成为第二个资产真相 owner。

多模态生成只能填充命名 slot，例如 `narrative_copy`、`portrait_media`、
`background_media`、`ambient_audio`、`chart_spec`、`motion_parameters`。生成请求只带
scope-filtered facts 和已 resolution 的参考；输出为 `UIContentDraft`，再经 schema、来源、
可见性、预算、资源大小、可访问性、内容安全和引用完整性自动验证。批准后以带 digest 的
`ContentArtifactRef` 绑定到 plan；失败、超时或预算耗尽只触发 slot fallback，绝不改变交互
结构或阻塞世界推进。

## 创作期与运行时的不同权限

创作期允许 Creator Skill 与创作者使用同一组装/生成工具形成：

```text
UIPackageDraft / BindingProfileDraft / ReferenceResolutionDraft
  -> preview + schema/permission/a11y/interaction regression/budget checks
  -> human review
  -> immutable approved UIPackage and digest
  -> package publication and governed activation
```

创作期生成的草稿不能直接进入玩家 runtime。运行时只可引用 approved package、capability、
binding、reference bundle 和 content slot。审核的对象是完整 UI 契约，而不只是单张媒体：
新 capability、交互动作、新 selector、新信息架构和新 renderer 行为需要离线人工审核；
仅已有 slot 的内容变体可走自动资格审核。

## 可见性、解释与回放

玩家 UI 必须清晰区分：已提交事实、未提交草案、角色意见、模型推测、司命体验调度和生成
媒体。视觉风格不得模糊这些状态。

对于体验/参考，提供两层 provenance：默认摘要回答“当前采用了哪些 package、体验模式、
继承/自动选择/生成内容”；展开层回答“来自哪里、为什么被采用、什么被抑制、使用了哪一
revision/digest、适用范围和 fallback”。这不是 debug-only 日志，而是玩家和创作者都可读的
结果说明面。

## 第一个验证案例：历史治理 UI

历史治理案例用于压力测试底座，不定义底座的唯一类型。其 Base Game UI Package 至少包含：

- 国情和事件阅读；
- 奏报与大臣建议；
- 诏书草拟、审阅、确认和提交；
- 政策接受、拒绝、执行与因果回执；
- 时间推进；
- 已提交历史与分支回看。

其玩法扩展可提供廷议、灾情、边防等领域面板。`UIDirectorProfile` 可在“常规朝会”、
“紧急奏报”、“多方意见对照”和“结算复盘”等已审核体验模式间选择，填充已许可的地图、
人物肖像、插画、旁白和图表 slot；不能改变诏书表单、提交路径或政策事实状态。

首个 vertical proof 应证明同一 committed world-event 序列在禁用模型时完整可玩；启用司命
时只改变获准体验增量；生成失败后仍能稳定操作；且可以在记录的 package/profile/reference/
content revisions 下回放。

## 验收与验证 / Acceptance and Verification

本设计进入实现前，计划必须覆盖至少以下证据：

1. Base Game UI Package 在没有司命、模型或网络媒体时完整可玩。
2. binding profile 不可改变 action、payload、命中区、focus、权限、authority status 或
   accessibility contract。
3. untrusted proposal 的 unknown/stale/expired/private/unapproved/budget-exceeded 路径均为
   zero side effect，并正确 fallback。
4. profile 尝试引入未注册 capability、selector、交互或 renderer code 时被拒绝。
5. reference resolution 能记录 winner/supporting/suppressed/overridden/out-of-scope/invalid，
   并保持 provenance。
6. 多模态产物只能进入批准 slot；失败不会阻塞输入、世界推进或关键操作。
7. renderer 对相同 approved plan 保持语义一致；Godot Control 是第一个 runtime evidence。
8. presentation trace 与固定 revision/digest/seed 可重放，而不重调模型。
9. 历史治理案例通过完整 UI fallback、司命增量、生成失败和 replay 四种场景。

## 依赖与后续顺序 / Dependencies and Sequencing

本设计复用既有 Godot presentation、BackendBridge、LocalPresentationBus、System L6、
creator control plane、immutable package/manifest、projection 和 replay 边界；不另建 UI event
store、scheduler、authoritative data path 或 content writer。

实施顺序应为：

```text
capability + Base Game UI Package contract
-> Godot Control renderer shell + fallback proof
-> extension package / binding profile admission
-> UIExperienceProposal / Policy Gate / trace
-> reference-resolution artifact + slot content pipeline
-> creator draft/review/publish path
-> history-governance vertical proof
```

每一阶段都需单独证明 schema、权限、拒绝零副作用、回放和 renderer evidence，不能因为
创作期 preview 或模型生成成功而宣称 runtime milestone 已完成。

## Risks

- 将 profile 或参考资产扩张为第二套 capability/asset truth owner；
- 因生成等待、媒体失败或网络问题破坏基础交互可用性；
- 用视觉叙事掩盖草案、意见、推测与 committed fact 的差异；
- 给司命未过滤的 private session data 或 renderer 直写权；
- 用 UI 包偷渡新 domain fact、selector 或执行代码；
- 在未完成 first vertical proof 前过早构建通用 UI DSL、市场或多 renderer 平台。

这些风险均以 registry allowlist、immutable revision/digest、scope filtering、Policy Gate、
fallback、审计 trace 和 focused Harness evidence 控制。
