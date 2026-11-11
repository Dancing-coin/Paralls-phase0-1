# G2 身份绑定可行性盘点

- 日期：2026-11-11。
- 源码快照：`5db3b59d2ad6ebb584e9b647065505581ade7dd7`，分支 `codex/g0-b3-ingress-20261109`。
- 性质：只读静态审计；本轮未执行测试、WebSocket 探针、Godot 或全量 harness，不作身份认证、隐私或 G2 验收通过结论。
- 依据：[已批准会话受众契约](boundary-audit.md#session-audience-contract-product-approved)。其 `boundary-audit.md:48–76` 要求主体、字段及获知时间证据，pull 与发送前均复验绑定、租约和权限；未绑定连接、客户端 actor/session ID、演示房间和旱情辖区均不是会话授权证据；拒绝及游标不得泄露受保护会话是否存在。
- 证据入口：[session visibility denial 记录](../g2-session-visibility-denial/README.md) 的 Boundary behavior、Focused verification（含 WebSocket session binding 测试组成，`:80–98`）及 Remaining gates。本文件重新读源码和测试，不把该记录的历史测试结果算成本轮执行。

## 总判：需扩展

现有可信本机凭证绑定、连接 epoch、WebSocket 租约及撤销机制可以作为已有基础；它们没有把“这个连接的后台主体”转换成“该主体此刻有权获知这个 session 的这些字段”。当前 session pull 仍固定拒绝，不能直接复用 B3 对象入口或 mirror 授权即开放正向 session 投影。缺口是会话事实向主体披露的授权边界及其 pull/发送前接线，不是再把客户端 session ID 当成身份。

| 结论档 | 对象及证据范围 |
|---|---|
| 可直接复用 | 在已有可信本机部署前提内，后台签发的一次性凭证、连接本地绑定、epoch/撤销 API；这些仅证明各自现有身份与生命周期契约。 |
| 需扩展 | 正向 session 读取：已认证主体与会话字段、历史感知/身份识别或授权送达、known_time 的权威关联；把当前绑定、租约和该关联的权限状态带到 pull 及实际发送前。若需要远程账户身份，还缺生产部署的身份验证接入。 |
| 不可行 | 直接把 B3 控制器绑定、当前空间样本、request ID、actor scope 或演示辖区当作完整 session 受众授权证据。它们所证明的契约不同；这不是整个方向不可行。 |

## 此连接能否证明为主体 X

### WebSocket 会话身份：有条件能，不能把主体身份等同于会话授权

`backend/app/services/websocket_session_auth_service.py:27–35` 的 enrollment 只接收凭证和协议/能力偏好，不接收主体与 actor scope。后台签发凭证时保存 principal、actor 范围和到期时间（`:119–156`）；本机绑定要求 loopback、凭证存在、未使用且未过期，然后从后台记录生成不可猜的 `session_ref`、principal、actor 范围、connection epoch 和 lease（`:199–224`）。后台启动配置签发范围及子进程交接见 `backend/app/services/trusted_local_gameplay_mirror_launcher.py:47–74`。此证据证明可信本机启动契约内的凭证持有连接被后台指派为 X；不证明任意远端账户或凭证交付过程已完成真实客户端验收。

连接标识由后端 `/ws` 构造（`backend/app/main.py:3555–3559`），绑定结果写入该连接的 context（`:5228–5246`），随后按连接/epoch 注册 mirror（`:4336–4357`）。客户端提交同名主体或已有 session ID 不能替代此链。

服务具备部署身份 resolver 扩展口，身份须由 resolver 返回，再由后端生成绑定（`backend/app/services/websocket_session_auth_service.py:166–198`）。但当前生产装配为无 resolver 的 `WebSocketSessionAuthService()`（`backend/app/main.py:2027`）；不能据接口存在宣称远程账户已认证。测试中的 resolver 是注入样本（`backend/tests/test_websocket_session_auth_service.py:84–108`），不是生产身份提供者证据。

### B3 控制器身份：证明另一份较窄的可信本机契约

`backend/app/services/embodied_controller_auth_service.py:90–132` 核对一次性本机凭证、loopback、到期时间及凭证中的 actor/controller，绑定到后端传入的 `connection_ref`，并产生 `principal:trusted_local:<actor>`。签发主体来自后台启动配置（`backend/app/services/trusted_local_embodied_controller_launcher.py:42–68`）。`resolve_controller_binding` 按连接查当前绑定，再检查撤销状态、controller epoch 和 actor 一致性（`backend/app/services/embodied_controller_auth_service.py:166–177`）。该服务的 `authenticated_session` 分支仍拒绝，配置标记也不能把它变成已实现适配器（`:98–101`）。

控制器 bind 路由只返回控制器绑定，不给连接设置 WebSocket session binding；后者有独立消息和 context 写入（`backend/app/main.py:5200–5246`）。两套 principal/actor 范围没有在这些入口中自动建立等价关系。因此“能操作 actor X”不推出“作为参与者 X 能读取任意 session”。

## B3 对象持久化入口实际证明什么

| 证据 | 当前行为 | 对 session 授权的限制 |
|---|---|---|
| `backend/app/main.py:6119–6142` | `obj_plaque`/`obj_worktable` 入口按当前连接解析 controller binding，匹配后台配置的 actor/room/scene/zone，要求 request ID，并以 binding ID + request ID 派生规范操作身份。 | request ID 关联同一绑定内的请求/精确重试；它不是凭证，不证明参与者、观察者、送达者资格。 |
| `backend/app/main.py:6144–6160` | 先找原结算；新结算读取该连接的授权空间样本，把源流 revision 交给既有 Owner 结算。 | 原收据恢复与新操作空间校验有不同语义；不能把重试结果或当前位置当成历史 session 披露证据。 |
| `backend/app/world_runtime/embodied_spatial_source.py:40–60,109–114,177–185` | 样本 scope 与内部部署定义精确匹配，并核对当前 controller binding、连接和 epoch。 | 证明声明范围内样本获准，不是独立服务器物理证明或会话字段访问许可。 |
| `backend/app/world_runtime/embodied_spatial_source.py:226–236,239–266` | 样本连同 scope digest、binding、connection、进程 epoch 和后台单调时钟持久化；读取重新核对 scope、进程、绑定和新鲜度，返回事件引用及 revision。 | 当前位置来源；没有在该证据中建立历史世界时间感知、身份识别、字段披露或 session known_time。重启后的历史样本不自动恢复有效当前身份。 |

静态测试证据：`backend/tests/test_player_object_ingress.py:21–48` 覆盖原请求重试和变更重试，`:51–103` 是组件 WebSocket 对象交互用例，`:106–118` 拒绝另一绑定借样本，`:152–165` 拒绝未绑定、缺样本/请求 ID、异主体/范围；`backend/tests/test_embodied_spatial_source.py:106–135,212` 覆盖撤销、重连和持久库重开相关情况。以上为已阅读的测试代码，本轮未执行。

## 生命周期、租约及撤销后已有连接

| 对象 | 证据与结论 |
|---|---|
| WebSocket binding | 模型含 active/renewal/revoked/expired/disconnected 状态、epoch 和 lease（`backend/app/services/websocket_session_auth_service.py:38–49`）。`resolve_binding` 只是查表，不主动校验租约（`:226–227`）；必须由读取/发送边界使用实时后台时间复验，不能把查到记录视为有效。 |
| WebSocket renewal | `issue_replacement_enrollment` 撤掉旧 binding 并生成替代凭证；actor scope 可由后台 selector 收窄，新凭证保留原 lease 截止时间（同文件 `:251–274`），不是自动延长租约。重连 epoch 更新和旧 binding 失效的测试位于 `backend/tests/test_websocket_session_renewal_lifecycle.py:34–83`。 |
| WebSocket 撤销与断连 | 服务撤销/断连移除活动记录并保留有界终态诊断（`backend/app/services/websocket_session_auth_service.py:276–306`）。仅调用服务 API 不直接操作 socket。生产 transport hook 另行取消连接任务、关闭 sink、清掉投递/订阅状态并请求关闭（`backend/app/main.py:6650–6691`）；连接收到 typed revocation 后等待确认/超时并以 4403 关闭（`:3653–3667,3771–3787`）。已提交领域事实不由此回退。 |
| 控制器 binding | `ControllerBinding` 没有租约到期字段（`backend/app/models/embodied_interaction.py:301–307`）。凭证到期在建立时检查，execution grant 的到期是另一份执行许可（`:310–328`），不能当作 controller binding 持续租约。重绑定撤销旧 controller epoch，显式 revoke/disconnect 撤销绑定及 grants（`backend/app/services/embodied_controller_auth_service.py:114–121,229–248`）。 |
| 控制器撤销后的连接 | 已建立 socket 不由 controller revoke API 立即关闭；后续 `resolve_controller_binding` 拒绝，空间读取也以 `spatial_source_binding_revoked` 拒绝（`backend/app/world_runtime/embodied_spatial_source.py:253–257`）。生产断连清理同时调用 controller disconnect（`backend/app/main.py:3524–3534`）。这与 WebSocket 会话撤销后的受控关连接不是同一生命周期。 |

静态测试证据：controller revoke/disconnect/rebind 见 `backend/tests/test_embodied_controller_auth_ingress.py:64–109`；空间断连拒绝见 `backend/tests/test_embodied_spatial_ingress.py:83–90`；WebSocket transport 撤销清理、typed close 及组件连接关闭见 `backend/tests/test_websocket_session_renewal_lifecycle.py:148–276`。本轮未执行，不据此扩大为所有路径或部署环境的保证。

## 能否在 pull 与发送前再校验

**能力存在，现有 session 正向读取没有接入。**

现有 mirror 读入口每次解析当前 binding，比较 principal、epoch、状态、租约及双方 actor 范围后才访问投影源（`backend/app/services/gameplay_mirror_session_access_service.py:47–77,94–107`）。静态用例 `backend/tests/test_gameplay_mirror_session_access_service.py:114–153` 检查 revoked/expired/epoch/scope 下源不再被调用。该权限是 mirror actor 范围，不是会话字段受众合同。

mirror 发送前由 Owner 的 `_mirror_send_lease` 重新 resolve 当前 binding，并核对该 session 的连接/sink、绑定、active 状态和实时 lease（`backend/app/main.py:1698–1717`）。投递循环取得 send lock 后复核 fence、从 Owner 取当前 lease，逐帧发送前再次核对 fence/deadline，编码后还核对 deadline（`:3793–3856`）。生产 IPC 外层在实际 send lock 内检查连接 generation、state revision、revoked、binding lease 和传入 deadline，发送等待受 deadline 限制（`backend/app/services/runtime_process.py:350–368`）；child 发送携带同步 binding revision 和 deadline（`:861–870,932–951`）。这说明不局限于“仅建立时校验”，也不证明 session 披露权限已在发送前检查。

相关静态用例：`backend/tests/test_runtime_execution_transport.py:221–222` 的参数包含 popped/sending revoke、expiry、renewal 等；`backend/tests/test_runtime_process_transport.py:496–544,663–679` 检查 binding/revocation 到达父进程 fence、阻塞发送的租约截止和 mirror 精确截止丢帧。本轮未执行这些并发/进程测试。

B3 对象入口在领域处理时检查 controller binding（`backend/app/main.py:6126–6136`），其普通响应经 `send_batch`/`send` 输出；后者只取 send lock 后调用 `send_json`（`:3698–3704,4406`），没有在这个通用函数中重新解析 controller binding。生产 IPC 的 WebSocket binding fence 也不能据此解释成 controller binding 或 session 字段权限的复验。这里仅界定本轮追踪的对象响应链，不推断其他异步完成或认知输出路径没有自己的门。

当前 `_handle_embodied_interaction_session_projection_pull` 没有 connection context 参数，路由也不传 context（`backend/app/main.py:5163–5164,6790–6796`），直接返回 `session_access_unavailable`，在读取前拒绝且不回 session ID/游标。已有 helper 自述未接入授权读取（`:6799–6804`）。因此当前拒绝路径不需要假装有正向授权；后续正向接入缺少的是完整权限边界，而非只补一次 bind 检查。静态拒绝用例 `backend/tests/test_embodied_interaction_session.py:49–123` 比较已知/未知 ID 和游标，并拒绝虽有有效 binding 但无披露证据的请求。

## 尚缺哪类真实信任边界

- **部署身份到连接主体。** 可信本机凭证路径已有窄契约；远程身份 resolver 当前未装配。控制器 actor principal 与 WebSocket principal 的关系不能由客户端 actor 字符串或相同 socket 自动推定。
- **权威 session 事实到主体可获知字段。** 当前控制器身份、actor read scope、实时空间来源和请求去重身份，均没有给出已批准合同所需的参与者字段披露、历史观察/识别或授权送达、principal-specific known_time。此结论仅针对本轮读取的这些来源；不声称审计了所有感知/送达实现或它们均不可复用。
- **授权决定到 pull 和实际发送。** mirror 已有实时绑定/租约、队列 fence 和 IPC 发送门，但 session 路由尚未把其自身权限证据接到这些实际强制边界；不能把发送通道支持复验等同于已验证完整 session 授权。两次检查间的权限变化、过期、撤销、重连与历史读取是否仍满足合同，尚无本轮端到端证据。

缺证据或不匹配应保持明确错误码；不以 `None`、空集或游标变化代表拒绝，也不暴露受保护会话是否存在。本盘点不指定新错误码、不提出实现方案、不开放正向路径，不改变任何现有 fail-closed、幂等或 revision 要求。

## 检查范围与未验证范围

已执行的是 Git 快照读取、`rg` 源码定位及上述源文件/测试的逐段静态阅读；未运行任何测试、网络进程、Godot、性能测量或 runtime harness。历史记录的测试结果和测试函数存在均不等于本轮已验证行为。凭证安全交付、真实部署身份源、完整 session 受众事实来源以及并发撤销到 wire 的运行结果未在本轮验证。

现有空间来源的架构、时序和数据流上下文见 [空间来源设计的 Architecture / Sequence / Data flow](../../superpowers/specs/2026-10-20-embodied-spatial-source-design.md#architecture)。该文区分当前实现、Godot 待验证及延期能力；它是既有背景，不构成本盘点新增设计或验收结论。
