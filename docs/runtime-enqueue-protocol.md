# WebSocket 有界命令接纳

`/ws` 在原会话绑定成功后支持 `runtime_enqueue`。当前只接纳 `character_actor_status` 和 `raw_fact_event`；不支持嵌套入队、绑定或续期命令。旧消息格式及旧业务 `ack` 行为保持。

```json
{"message_type":"runtime_enqueue","payload":{"request_id":"client:17","command":{"message_type":"character_actor_status","payload":{"actor_id":"char_a"}}}}
```

`request_id` 是 1–128 字符的字符串。同一连接的未完成请求不能重复；它不是持久化幂等键。命令结构和原业务模型仍须合法，角色权限在实际 owner 执行时校验。

```json
{"message_type":"runtime_admission","payload":{"request_id":"client:17","accepted":true}}
```

`accepted=true` 只证明原命令已经进入有界 owner 队列，不证明授权、业务成功或持久化完成。每连接至多 128 个未完成请求，原 owner 队列上限仍为 128。容量不足、重复未完成编号或 runtime 不可用时返回 `accepted=false` 和 `reason`，不执行该命令。

```json
{"message_type":"runtime_completion","payload":{"request_id":"client:17","status":"owner_finished","messages":[{"message_type":"ack","payload":{"accepted":true,"source_type":"character_actor_status","route":"character_actor_runtime_status"}}]}}
```

完成回包按同一连接的入队顺序发送。`messages` 保留原业务消息；应检查其中原业务 ACK 或权威结果，不把 `owner_finished` 视为业务成功。原后台认知输出仍走各自原连接路由，不是此完成回包的成功条件。

绑定、续期及旧入口在该连接此前已接纳命令完成后执行。撤销或断连可以拒收文本和取消尚未开始的队列命令，不撤回已经提交的事实。进程终止或断连可能令已接纳命令没有完成回包；不得根据缺少文本就自动重放事实，应按原业务事实身份查询或重试。

服务隔离探针分别保存 `accepted_ms`（精确对应 runtime_admission）与 `business_ms`（原业务 ACK），事实落定另存 `fact_ms`；原阈值和定速发送时刻不变。
