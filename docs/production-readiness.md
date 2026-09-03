# 生产级完整实现门禁

这份清单定义生产级运行的必要条件。测试兼容模式可以使用 stub 或 legacy fallback，但生产启动必须显式满足以下门禁。

## 在线角色模型

- `CHARACTER_MODEL_PROVIDER_KIND=deepseek`（或已批准的在线兼容 provider）
- `CHARACTER_MODEL_ENDPOINT`、`CHARACTER_MODEL_API_KEY`、`CHARACTER_MODEL_MODEL` 均已配置
- `CHARACTER_MODEL_REQUIRE_ONLINE=1`
- `DIALOGUE_MODE=http`
- `verify_character_model_live.py` 的 dialogue、L2、L3 均为 `passed`，且 `fallback_used=false`

## 真实语音

- `TTS_MODE=openai_compatible` 或 `TTS_MODE=dashscope_http`
- TTS endpoint、API key、model 和已批准 voice binding 均已配置
- `TTS_REQUIRE_REAL=1`
- `verify_tts_provider_live.py --allow-live-call` 返回 `real_provider_verified`
- Godot 播放证据必须引用真实 WAV clip，不接受 `stub://` 或 `provider_fallback`

## 图谱连续性

- `CHARACTER_GRAPH_REQUIRE_CONTINUITY=1`
- 生产 runtime 不创建 `character_agent_session_store.json`
- actor-private graph snapshot 必须包含 working memory、dynamic state、need/tension、supervision、goal state/history、session timeline 和 continuity state
- 重启后 timeline 与五池读取必须来自 Heavenly Graph

## Authority 与 Godot

- Authority 六域 committed events 都能投影 owner、source revision vector、source lineage、replay ref 和 correction lineage
- Godot 必须使用真实 Authority result 驱动场景变化
- reconnect、gap/resync、backpressure 和 controlled-close profiles 全部通过
- 最终 Heavenly live report 的 17 个结果和三张 meaningful captures 全部通过

## 发布规则

任一在线 provider、TTS、连续性或 Godot 生产门禁失败，都只能报告为“生产级未完成”，不能用测试通过数替代。
