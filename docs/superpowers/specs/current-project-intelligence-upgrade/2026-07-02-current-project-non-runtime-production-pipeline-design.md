# 当前项目 Non-Runtime Production Pipeline 子规格

- 日期：`2026-07-02`
- 状态：`planned`
- 上位规格：[2026-06-29-current-project-non-runtime-multimodal-tooling-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-non-runtime-multimodal-tooling-design.md)

## 1. 目标

把非运行时工具链 manifest 补全为真实 production pipeline：场景语义抽取、空间结构烘焙、多模态分类、人工审核和数据集/回放构建。

## 2. 定位

该 pipeline 是离线/半离线生产工具，不是 runtime。

它可以生成：

- scene semantic draft
- spatial structure bake
- object affordance draft
- navigation/occlusion annotations
- review task
- replay/dataset artifact

它不能：

- 在 runtime 直接写 world truth
- 共享角色/司命 runtime context
- 代替 L1 runtime-facing subsystem

## 3. 模块

建议模块：

- `SceneSemanticExtractor`
- `SpatialStructureBaker`
- `MultimodalSemanticClassifier`
- `SceneKnowledgeGenerator`
- `ReviewWorkbench`
- `DatasetAndReplayBuilder`

## 4. 审核与落地

生产结果必须进入 review gate。

只有审核后的 artifact 可以作为：

- L1 scene space model seed
- production scene knowledge seed
- verification replay dataset

## 5. Verification 要求

必须证明：

- pipeline 不读取 runtime private context
- draft/review/approved 状态清晰
- approved artifact 可被 L1 extractor 或 verifier 消费
- rejected draft 不进入 runtime

## 6. 一句话收束

Non-runtime production pipeline 是服务内容生产和验证的工具链，不是 runtime；它产出可审核 artifact，为 L1 和验证提供种子数据。
