# 配置居民名单与导入剧本

群体运行时在后端启动时读取一份居民名单；角色注册与群体调度共用这一份快照。默认文件 `backend/assets/population/default_roster.json` 的 12 名居民只是样例，不是固定人数或上限。自定义名单不会自动补齐默认角色。

## 运行配置

```json
{
  "actor_ids": ["alice", "bob@1"]
}
```

通过 `POPULATION_ROSTER_PATH` 指向该 JSON 文件；相对路径以仓库根目录为基准。修改配置后需要重启后端，停止、恢复群体调度不会重读名单。

```dotenv
POPULATION_ROSTER_PATH=backend/assets/population/my_roster.json
```

名单必须非空且 ID 唯一。ID 以小写英文字母或数字开头，其余允许小写英文字母、数字、下划线、点、连字符和 `@`；不接受大写字母、空白、路径分隔符或 `character:` 引用前缀。为兼容运行时引用的隐私边界，ID 不得包含 `actor_private`，也不得以 `private` 或 `branch` 结尾。`stormnight-guardian@1` 是合法 ID。

新居民仅获得 dormant continuity 身份；这不会生成完整 CharacterProfile、剧情真相、私有知识、长期记忆或 Godot 角色实例。完整角色档案仍需按既有入口单独配置。

已经开始的持久局会记录名单摘要；修改名单后重开同一存档会拒绝恢复（`population_roster_mismatch`）。更换名单开始新局时，应使用新的存档路径，保留原存档；当前没有隐式增删居民迁移。恢复规则、存档位置和规模验收见 [群体优化交接](verification/population-data-oriented-closure.md)。

## 结构化角色表直接导入

工具读取 UTF-8 JSON，支持三种输入：

- 仅含 `actor_ids` 的运行配置。
- 现有 `ScriptedMysteryCaseContent` JSON 中的 `actor_refs` 数组，移除每个引用的 `character:` 前缀，保留 `@1` 等后缀；其他剧情字段不参与名单提取。
- 仅含 `characters` 的角色表，每行必须有 `actor_id`、`name`，`aliases` 可省略。

```json
{
  "characters": [
    {"actor_id": "alice", "name": "爱丽丝", "aliases": ["小爱"]},
    {"actor_id": "bob@1", "name": "鲍勃", "aliases": []}
  ]
}
```

在仓库根目录运行：

```powershell
python -m tools.production.population_roster import characters.json --output backend/assets/population/my_roster.json
```

导出只包含 `actor_ids`，姓名和别名不会写入运行名单。多个角色表字段同时出现、空名单、重复或非法 ID 都会报错；工具不从人物台词、真相字段或提到的群众里凑人数，也不静默去重。

## 自然语言剧本生成待审核名单

`analyze` 使用既有 `app.config.settings` 的 `NON_RUNTIME_MODEL_*` 设置。只支持已配置的 HTTP chat/completions 模型，不使用角色运行时的私有上下文。

```dotenv
NON_RUNTIME_MODEL_MODE=http
NON_RUNTIME_MODEL_ENDPOINT=https://your-provider.example/v1/chat/completions
NON_RUNTIME_MODEL_API_KEY=your-provider-key
NON_RUNTIME_MODEL_MODEL=your-model
NON_RUNTIME_MODEL_TIMEOUT_SECONDS=30
```

端点需要兼容 `response_format={"type":"json_object"}`，返回完整的 `choices[0].message.content` JSON 字符串及 `finish_reason="stop"`。未配置、网络失败、被截断或过滤、格式错误、重复 ID、依据不在原文时直接报错；不会生成伪装成模型结果的本地回退名单。错误信息不输出 provider 的原始错误内容或密钥。

```powershell
python -m tools.production.population_roster analyze script.txt --output roster.draft.json
```

这条命令会把指定剧本原文发送到配置的模型端点。输入必须是 UTF-8 文本，可带 BOM；不会自动截短原文或拆分超长剧本。超出模型上下文时，应先整理适合分析的剧本文件。

草稿含以下字段：

| 字段 | 用途 |
| --- | --- |
| `kind` | 固定为 `population_roster_draft`，与运行配置区分 |
| `source_path` | 分析时源文件的绝对路径，便于人工找到原文 |
| `source_sha256` | 源文件原始字节的 SHA256，检测原文是否变动 |
| `characters` | 每项包含 `actor_id`、`name`、`aliases`、`evidence` |
| `characters[].evidence` | 至少一段逐字原文引用，用于核对人物身份 |

人工审阅时，核对所有应加入名单的角色是否齐全，合并同一人物的姓名与别名，区分同名但不同的人，删去不应成为居民的提及对象，并检查每条原文依据是否足以支持人物身份。可以直接编辑草稿中的角色表和 ID，但必须保留来源字段和有效依据。程序只能验证引用确实存在，不能替代人审判断角色是否完整或身份是否正确。

## 审阅后显式批准导出

确认完成以上审阅后执行：

```powershell
python -m tools.production.population_roster approve roster.draft.json --source script.txt --output backend/assets/population/my_roster.json
```

`approve` 本身就是人工确认已审阅的显式动作。它会重新验证草稿 schema、ID、源文件 SHA256 和逐字引用，然后导出仅含 `actor_ids` 的运行配置。`--source` 必须提供原文；允许源文件移动，只要字节内容未改变。即使只是换行符发生变化，SHA256 也会不同，需要重新分析并审核。

草稿不能直接传给运行时加载，也不能作为普通 `characters` 或 `actor_ids` 表导入来绕过审核。生成配置后设置 `POPULATION_ROSTER_PATH` 并重启后端。

三个命令均禁止输出到源文件或草稿自身，也不覆盖已有输出。需重做时请指定新文件名，输出目录须已存在。CLI 文件路径相对于当前工作目录；运行时 `POPULATION_ROSTER_PATH` 的相对路径始终基于仓库根目录。

## 本地验证

```powershell
$env:PARALLS_HEAVENLY_GRAPH_PATH=':memory:'
python -m pytest -q backend/tests/test_population_roster.py backend/tests/test_population_roster_import.py
```

导入测试覆盖现有 stormnight 四角色与 `@1` 后缀；自然语言测试使用本地传输替身，不访问真实 provider。覆盖完整草稿往返、异常响应、截断、原文证据、源文件变更、草稿拒绝和禁止文件覆盖。本轮证明范围是后端配置和离线 CLI，未验证真实模型质量或 Godot 场景。
