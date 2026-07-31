# 角色声线源资产

本目录只保存声线源资产的 YAML 清单，不保存原始录音、provider 签名 URL、API
key 或生成的对话音频。

原始参考音频由受控资产存储保管，清单用 `secure_asset://` 引用它，并记录：

- 所属 `actor_id` 与资产 ID
- 文件 SHA-256
- 使用授权或演出者同意记录
- 保留与撤销策略

受授权的后台 enrollment 工具才可以为此引用签发临时 HTTPS 读取 URL，并调用
百炼声音复刻。复刻返回的 `voice_id` 初始只能是候选，必须完成人工试听审批后
才可写入 TTS 音色绑定。

`char_a.example.yaml` 仅展示格式，不能直接启用。
