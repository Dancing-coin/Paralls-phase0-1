# 角色档案关联资产库

本目录是角色档案与表现资产之间的稳定索引入口。它不替代角色运行时，
也不替代 `assets/artpacks/` 的美术资源包；它记录每个 `actor_id` 使用哪些
经过审批的角色模型、服装、道具、动作和声线资产。

## 目录职责

```text
assets/characters/
  profiles/                 角色作者档案真相
  dossiers/                 角色结构化档案
  asset_manifests/          角色表现资产索引与绑定清单
  voice_sources/            受控声线源资产清单，不保存原始录音
  shared/                   当前共享骑士临时资源
```

角色模型、服装模型、手持道具、贴图、材质和动画的可运行文件应归入
`assets/artpacks/<资源包ID>/`；`asset_manifests/` 使用稳定 ID 或资源引用把
它们关联到角色。这样更换美术包不会改变 `actor_id`、角色档案、后端权威或
Godot 的 `CharacterReplica` 运行时壳。

所有 A/B/C 角色仍应通过 shared skeleton and animation preparation path，
`A/B/C` should not diverge into separate asset conventions。

## 资产分类

| 分类 | 存放位置 | 角色清单记录内容 |
| --- | --- | --- |
| 作者档案 | `profiles/`、`dossiers/` | 角色身份、能力、性格和约束 |
| 角色模型与骨架 | `assets/artpacks/<包ID>/characters/` | `role_asset_id`、骨架绑定、兼容级别 |
| 服装与外观 | `assets/artpacks/<包ID>/characters/` | 服装槽位、默认外观、可见规则 |
| 手持道具与装备 | `assets/artpacks/<包ID>/props/` | 装备槽位、锚点、偏移与状态规则 |
| 动作与表情 | `assets/artpacks/<包ID>/animations/` | 动作语义、动画引用、root motion 与修饰器 |
| 声线源资产 | 受控资产存储 | `secure_asset://` 引用、哈希、授权与撤销状态 |
| TTS 音色绑定 | `assets/tts/` 或部署配置 | provider、model、已批准的 `voice_id` |

## 不可突破的边界

- 不要把角色模型根节点替换成运行时 `CharacterReplica`。
- 不要因更换服装、道具或声线而更改 `actor_id` 或角色档案真相。
- 原始参考音频、签名下载 URL、API key 和生成对话音频不得提交到本目录。
- `voice_sources/` 仅保存元数据；复刻后的 `voice_id` 必须先经试听审批，
  再写入 TTS 音色绑定。
- 角色资产清单是资产管理索引，不是新的通用运行时资产库；它必须继续通过
  现有 artpack adapter、binding profile 和运行时壳接入。

具体接入规则见 `docs/art-resource-swap-workflow.md` 与
`docs/character/character-asset-integration.md`。
