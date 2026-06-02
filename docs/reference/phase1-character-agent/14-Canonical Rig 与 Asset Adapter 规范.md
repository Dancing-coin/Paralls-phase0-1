# 14-Canonical Rig 与 Asset Adapter 规范

## 1. 定义

`Canonical Rig` 与 `Asset Adapter` 的作用，不是让所有角色长得一样、绑得一样，而是让所有角色都能被同一套角色智能体“以同一种语义方式驱动”。

## 2. 核心原则

- 上层永远不依赖具体资产命名
- 必须建立统一控制空间
- 每个资产只需要接入统一空间，不反过来污染角色智能体

## 3. Canonical Face Schema

`Phase 1` 以 `FACS` 为主轴，至少支持：

- `AU1`
- `AU2`
- `AU4`
- `AU5`
- `AU6`
- `AU7`
- `AU9`
- `AU10`
- `AU12`
- `AU14`
- `AU15`
- `AU17`
- `AU20`
- `AU23`
- `AU24`
- `AU25`
- `AU26`

## 4. Canonical Body Schema

最小 body channels 至少包括：

- posture_open
- posture_collapsed
- spine_guarded_hunch
- spine_forward_probe
- chest_open_confident
- shoulder_raise_tension
- shoulder_inward_defense
- neck_retract_alert
- center_of_mass_forward/backward
- weight_shift_left/right
- step_back_micro
- step_forward_hesitant
- arm_cross_guard
- hand_self_touch_* 
- hand_cover_mouth_* 
- object_hide_close_* 

## 5. 标准骨骼槽位

最小骨骼槽位：

- root / pelvis / spine_lower / spine_mid / spine_upper
- clavicle_l/r
- upperarm_l/r
- forearm_l/r
- hand_l/r
- neck / head
- thigh_l/r
- calf_l/r
- foot_l/r

## 6. Embodiment Profile

每个角色资产必须带 `Embodiment Profile`：

- `canonical_body_map`
- `canonical_face_map`
- `retarget_profile`
- `face_profile`
- `locomotion_profile`
- `gesture_profile`
- `style_compensation_profile`
- `constraint_profile`

## 7. Adapter 边界

Adapter 负责：

- 骨骼 remap
- 面部 remap
- 范围归一
- 风格补偿
- 约束上限

Adapter 不负责高层表达策略。

## 8. 资产分级

建议资产至少分：

- A 级：完整支持
- B 级：大部分支持，少量近似
- C 级：基础表达支持

## 9. 一句话收束

`Canonical Rig` 和 `Asset Adapter` 的目标，是让上层永远说同一种身体语言，下层资产各自负责把这种语言翻译成自己的 rig 和面部控制器。
