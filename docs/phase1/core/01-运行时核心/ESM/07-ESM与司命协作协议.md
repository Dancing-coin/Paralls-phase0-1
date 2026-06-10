# 07-ESM与司命协作协议

## 1. 文档目标

本文档冻结 `ESM` 如何接收司命环境请求、如何回写结构化结果，以及两者的最小 replay 闭环。

## 2. 核心定义

司命负责：

- 高层催化判断

`ESM` 负责：

- 物理可行性检查
- 状态结算

## 3. 司命到 `ESM`

司命只允许通过：

- `environment_request`

进入 `ESM`。

## 4. `ESM` 回给司命

`ESM` 回给司命的正式对象固定为：

- `ActionResolutionResult`
- `EnvironmentStateResult`
- `ObjectStateResult`
- `BodyStateResult`
- `ConstraintStateResult`

## 5. 最小执行闭环

```text
InterventionDecision
-> environment_request
-> ActionRequest
-> ActionResolutionResult / ConstraintStateResult
-> EnvironmentStateResult / ObjectStateResult
-> Siming Re-evaluation
```

## 6. 禁令

- `ESM` 不替司命做公平判断
- 司命不替 `ESM` 写物理结果

## 7. 一句话收束

`ESM` 与司命的关系，应该始终保持为“司命请求、`ESM` 结算、司命再解释”的闭环，而不是两边互相越权写结果。
