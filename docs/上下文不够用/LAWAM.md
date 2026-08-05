这篇推文介绍了清华大学与正行创新（Striding AI）联合提出的LaWAM（Latent World Action Model，隐世界动作模型），以下是核心内容总结：

🎯 研究动机

传统像素空间世界动作模型（WAM）先生成未来视频再决策，存在高延迟且含大量对控制无用的纹理/光照信息。LaWAM 提出在视觉隐空间中预测动作相关的未来子目标（latent visual subgoal），保留物体运动趋势、交互区域等关键结构信息，省去逐像素重建，适配实时机器人控制回路。

🔧 方法框架（两阶段）

• 第一阶段——学 LaWM（隐世界模型）：通过隐动作模型（LAM）从当前/未来视觉状态对推断抽象隐动作（latent action，表达"画面间发生了什么变化"而非关节指令），再用前向解码器（LaWM）根据当前视觉特征+隐动作预测未来隐空间视觉特征。训练目标含特征预测误差、KL 正则及末端执行器状态辅助损失。

- 第二阶段——策略使用：策略先验预测隐动作 → 冻结 LaWM 解码出隐空间视觉子目标 → 动作专家基于此生成动作块。通过隐动作蒸馏让策略学会驱动 LaWM，知识隔离防止 LaWM 被动作专家梯度破坏。

✅ 核心优势与实验结果

维度 表现

推理延迟 2.3B 参数 LaWAM 单动作块推理 187ms，相比像素空间 WAM（LingBot-VA 4482ms）降低最高约 24 倍

LIBERO 基准 平均成功率 98.6%，超越或匹配现有 VLA / 隐动作 / 传统 WAM 基线

RoboTwin 2.0 双臂 Clean 92.64% / Random 89.80%，平均 91.22%

真机任务 抓取放置、开抽屉、折毛巾（可变形物体长时程双臂协作）均验证隐空间子目标能及时响应动态变化

泛化性 同一隐动作轨迹可在不同场景/机器人本体上由 LaWM 展开为因地制宜的隐空间预测

⚠️ 局限与展望

• 当前在相机视角相对固定的任务表现最佳；剧烈相机运动或极细微可变形体动态需进一步增强。

• 未来方向：引入更大规模多样化真实交互数据，增强对移动相机和微小接触状态的处理能力。

📎 资源链接

• 论文：https://arxiv.org/abs/2606.15768

• 项目主页：https://rlinf.github.io/LaWAM/

• 代码：https://github.com/RLinf/LaWAM

- Hugging Face 模型：https://huggingface.co/collections/jialei02/lawam-checkpoints

简而言之，LaWAM 把"想象未来"从生成像素视频改为生成隐空间可行动子目标，在大幅降低延迟的同时保持高任务成功率，并从人类/机器人视频中学习可跨本体迁移的动作—状态变化规律，更贴近真实机器人部署需求。

如需我帮你整理 LaWAM 与常规 VLA/WAM 的对比表格或技术公式解读，可以随时说！


下面是文章中出现的公式与数学建模部分的完整整理，我按出现顺序做了统一标注、补全符号含义，并把文字描述对应起来，方便你对照原文理解。

一、传统 VLA 与 WAM 的概率建模基础

1. 常规 VLA（Vision-Language-Action）模型

常规 VLA 直接学习从「当前观测 + 语言指令」到「动作块」的映射，其联合概率形式为：

\[
p(a_t \mid o_t, l)
\]

其中：
• a_t：当前时刻要执行的动作块（action chunk）

• o_t：当前时刻的观测（通常是高维像素观测）

• l：语言指令（language instruction）

👉 本质：无显式未来预测的端到端映射

2. 像素空间 WAM（World-Action Model）

WAM 在 VLA 基础上引入未来状态/未来视频作为条件，其联合概率分解为：

\[
p(a_t, o_{t+1:t+H} \mid o_t, l) = p(o_{t+1:t+H} \mid o_t, l) \cdot p(a_t \mid o_t, l, o_{t+1:t+H})
\]

其中：
• o_{t+1:t+H}：未来 H 步的高维像素观测（即未来视频帧）

• 第一项 \(p(o_{t+1:t+H} \mid o_t, l)\)：未来视频生成（世界模型）

• 第二项 \(p(a_t \mid \cdot)\)：基于当前观测 + 语言 + 未来视频生成动作

⚠️ 问题：
• 若 o_{t+1:t+H} 是高维像素视频，第一项计算成本极高

• 像素中大量纹理/光照信息与控制无关，造成算力浪费

二、LaWAM 的隐空间建模（核心创新）

LaWAM 保留 WAM 的“未来条件生成”结构，但把未来状态从像素空间映射到冻结视觉编码器的特征空间。

定义：
• \(z_t = E(o_t)\)：当前观测经冻结视觉编码器得到的隐空间特征

• \(z_{t+1:t+H} = E(o_{t+1:t+H})\)：未来观测对应的隐空间特征

3. LaWM 第一阶段训练目标（隐世界模型学习）

（1）隐逆动力学模型（Latent Inverse Dynamics Model）

从当前和未来隐特征中推断隐动作：

\[
\hat{a}_t^{\text{latent}} = f_{\text{inv}}(z_t, z_{t+1})
\]

其中：
• \hat{a}_t^{\text{latent}}：抽象隐动作，表达“当前→未来画面发生了什么变化”

• f_{\text{inv}}：隐逆动力学模型

（2）LaWM 前向解码器（Latent World Model）

结合当前隐特征 + 隐动作，预测未来隐特征：

\[
\hat{z}_{t+1} = f_{\text{LaWM}}(z_t, \hat{a}_t^{\text{latent}})
\]

其中：
• \hat{z}_{t+1}：LaWM 预测的未来隐空间视觉子目标

• f_{\text{LaWM}}：前向解码器（即 LaWM 主体）

（3）总训练目标函数

第一阶段训练 LaWM 的目标是最小化以下组合损失：

\[
\mathcal{L}_{\text{LaWM}} =
\underbrace{\\hat{z}_{t+1} - z_{t+1} \
_2^2}_{\text{未来特征预测误差}}
• \beta \cdot \underbrace{D_{\text{KL}}(q(\hat{a}_t^{\text{latent}} \mid z_t, z_{t+1}) \parallel p(\hat{a}_t^{\text{latent}}))}_{\text{KL 正则项}}

• \lambda \cdot \underbrace{\mathcal{L}_{\text{ee}}(\hat{s}_{t+1}^{\text{ee}}, s_{t+1}^{\text{ee}})}_{\text{末端执行器状态辅助损失}}

\]

其中：
• 第一项：未来隐特征的预测精度

• 第二项：KL 散度，约束隐动作分布不过拟合

• 第三项：末端执行器（夹爪/机械臂末端）状态预测损失，让隐动作更偏向具身运动，减少纯外观变化的干扰

• \beta, \lambda：平衡系数

三、第二阶段：策略部署与动作生成

部署阶段真实未来特征 z_{t+1} 尚未发生，流程变为：

1. 策略先验预测隐动作（不再依赖真实未来）：
\[
\tilde{a}_t^{\text{latent}} = \pi_{\text{prior}}(z_t, l)
\]

2. 冻结 LaWM 解码隐空间子目标：
\[
\tilde{z}_{t+1} = f_{\text{LaWM}}(z_t, \tilde{a}_t^{\text{latent}})
\]
（LaWM 参数全程冻结，避免被动作专家梯度破坏）

3. 动作专家生成动作块：
\[
a_t = \pi_{\text{expert}}(z_t, l, \tilde{z}_{t+1})
\]

4. 第二阶段训练技巧

• 隐动作蒸馏：让策略先验预测的 \tilde{a}_t^{\text{latent}} 逼近第一阶段学到的 \hat{a}_t^{\text{latent}}，保证策略能稳定驱动 LaWM

• 知识隔离：冻结 LaWM，仅训练策略部分，保护 LaWM 已学到的场景变化规律不被破坏

四、关键设计对比（公式层面）

方法 未来表示 核心计算量来源 是否适合实时控制

像素 WAM o_{t+1:t+H}（高维像素） 视频生成 ❌

LaWAM z_{t+1}（低维隐特征） 隐空间特征预测 ✅

五、一句话总结公式层面的创新

LaWAM 把 WAM 中昂贵的 \(p(o_{t+1:t+H} \mid o_t, l)\) 替换为轻量的 \(\hat{z}_{t+1} = f_{\text{LaWM}}(z_t, \hat{a}_t^{\text{latent}})\)，在保留“未来条件生成”结构的同时，将未来预测从像素级生成降级为隐空间特征预测，从而实现 24 倍延迟降低 + 90%+ 成功率。

