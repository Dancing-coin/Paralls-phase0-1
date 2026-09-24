# 千人六项闭环最终执行补充

Status: execution_in_progress; godot_unverified; current_population_ceiling_1000

### 4289bd2d 容量失败的接续修复（2026-09-21）

- 同版 change-lifecycle、correctness（1710项）、真实模型 short、service 两档和 transport 五配对通过；capacity 完整采集并清理，但两个2局样本完整性失败。4局四个样本完整性通过，最大单窗 lag 1.094—1.156，严格性能门槛未过，不能将此前抽查 backlog=0 当最终通过。recovery/soak 未启动。
- 实际失败：2局game-1的L2输出calm=-0.03，被原validator拒绝，B2完成21/22；game-2的L3输出无法解析JSON，另一角色任务stale。game-2受控Siming超时后同一任务因stale_pin安全终止，而当前故障验收只认同一任务completed。不得把后续其他成功任务冒充该任务完成；是否接受“原故障任务安全终止并证明恢复”的验收修正正在等待用户答复，未答复前保持原门槛。
- 修复一：L2提示词直接包含CharacterDynamicStateDelta的schema，明确这些字段是局部替换值而非有符号增量；affect_valence合法范围为[-1,1]，其他字段为[0,1]。原validator仍拒绝calm=-0.03，禁止钳制、伪造默认值或自动成功回退。用各字段实际边界和原失败值验证。
- 修复二：L3请求要求紧凑JSON、保留并存目标，将原1800输出token预算增至4096，保留provider 30秒超时。原请求9次真实重放均成功（988—1598输出token），原错误是否由截断造成尚未确认，不能宣称已复现。依据[DeepSeek Chat Completions合同](https://api-docs.deepseek.com/api/create-chat-completion/)，显式非stop结束必须拒绝，先于JSON解析报告有界结束原因；即使正文恰好是合法JSON也不能当成完整成功。正常stop和既有未提供finish_reason的兼容响应仍按原validator处理。
- 检查顺序：新增失败回归→最小修复→gateway/provider及原delta合同回归→原失败请求使用新提示词的真实诊断→独立审查与完整后端/工具验证→提交推送并重新冻结版本→从新SHA串行完成全部正式门禁。旧4289证据保留为原版本结果，不重贴新身份。
- CI #210的static smoke和population-correctness通过，all在Phase0缺17项对话/交互/观测面板运行证据，cleanup通过。详细日志需登录，不能直接归因于用户暂缓的Godot导入P2。Godot继续外机未验证。总体Goal仍active。
- 本轮证据：新增回归先11 failed／74 passed，修复后gateway/provider/delta/mind模型125 passed；两个原失败请求用新提示词分别真实重放3次均通过，仅作诊断。完整双核Phase0环境后端6961 passed／2 skipped／0 failed（651.91秒），拥有作用域清理通过。独立只读审查确认实际DynamicStateStore逐字段替换、异常仍严格上抛，无已确认阻断缺陷。4局八个超限窗口均在第300/600窗高峰，fixture约783—816ms加cadence约265—321ms，不能删除或归为无证据的随机环境抖动。
- 完整验证工具452 passed（72.86秒），清理通过；git diff --check通过，工作树.harness只有静态资产，无本轮提交产物。根main仍保留用户tmp/。仅提交上述六个实现、回归和文档文件，随后重新冻结同版证据；不把短诊断与单测合并冒充正式六项通过。

承接 `2026-09-16-population-production-runtime-closure-implementation-plan.md` 的六项范围、阈值和 G0—G9；不得以本补充的一项完成代替总目标。设计依据：`../specs/2026-09-19-activation-receipt-evidence-cost-design.md`。起点 `c23d879e0d27d4ad7ef023d3edcc24aae2a9ef8d`。执行工作树为 `D:/MyConfiguration/TCLXUSER/.codex/worktrees/pfc/Paralls-phase0-1`。

## Task 1: 激活证据分离

- 修改 `backend/app/population_continuity/models.py` 的 ActivationReceipt：证据类型区分 none/commit/full_replay；提交证据记录原 AppendBatchResult.global_sequence_range，replay_hash 为空；拒绝不携带提交证据。
- 修改 `activation.py`：删除全局 ReplayResult 缓存，成功回执仅消费已提交结果；新增显式 `audit_receipt`，读取该回执提交序号截面并使用原 full_replay 算法。后续其他 Owner 写入不得改变旧截面的审计结果。失败审计不能包装成成功。
- `test_population_continuity.py` 先更新旧隐式审计测试并新增跨 Owner / 非字典序事件 / 持久化重开 / 重复请求 / 无写入拒绝 / 审计失败测试。运行时禁止 read_events 和 full_replay/continue_replay，显式审计仍核对原 hash、事件和 revision。
- 修改 `verify_phase3a_profile_activation.py` 在审计边界显式取证；运行时其他消费者继续使用 commit 证据。
- 扩展混合负载和恢复 cache 指标及复验器，覆盖 activation receipts 与历史投影缓存；不得将缺失字段当作零。历史投影必须为零，已定义的 receipt 限额仍为32。
- 检查：先观察新增测试失败，再运行激活、continuation、持久化恢复、混合指标和验证器回归；所有失败先定位，不放松现有门槛。

## Task 2: 正确性、审查与源码冻结

- 一次 fresh-context 全分支审查，核对运行时提交与显式审计语义、失败原子性、证据消费兼容及指标真实性；修复重要问题并回归。
- 运行完整 backend、相关工具测试、population-runtime-correctness、change-lifecycle；禁止在本机调用 Godot。mainline/all 需要外机真实证据，继续标记未验证。
- 固定 Python3.12.14 和 ci-constraints，记录运行环境；仅使用本地 .env，禁止输出/提交密钥。
- 冻结实现提交后才进入正式性能采集。任何源码修复都使不匹配的旧证据失效。

## Task 3: 同版后端正式验收

- 串行采集服务隔离：100/1000 人各120秒，真实 WebSocket 时序、10ms心跳、单 writer 和 provider 等待分离。
- 千人长历史：1000/10000个历史窗口、tail8、各5次独立冷恢复；保留真实造档和恢复原始结果。
- 传输：1000人、30窗、5配对、manual_window_cost；核对 WS 原包、逻辑SQLite字节、同 seed/hash/oracle及改善判定。
- mixed short：100/1000人各30窗1×；soak：两档各30分钟、各30窗10×、千人另2小时。1×必须满足既定800ms/积压/lag门槛；10×完整保留性能结论。
- 多局：2/4个独立千人后端，各600秒；容量不足保留实际测量，证据缺失不可当作容量不足而通过。
- 每个采集入口使用新的仓库外证据目录；完成后用同源码对应复验器核对。不可并行运行无关基准、裁短、删除故障窗口或复用旧版本成功结果。

## Task 4: CI、外机交接与总聚合

- 核对可重建 CI 和当前提交远端运行；沿用会话的提交推送授权，按 cherry-pick 合回 main，保护用户 tmp/。
- 整理同版外机命令及 evidence.json；population Godot、InteractionSession runtime JSON、mainline/all、Archive Door批准绑定、VLA真实凭据缺项分别列出。Godot导入提前退出按用户决定暂缓。
- 运行六项聚合器，只接受原始证据复验。更新主计划/交接文档为真实结果和精确阻塞。只有所有必要门禁通过才将 Goal 标为 complete；外部阻塞不能伪造闭环。

## 正式短验收暴露的 L3 提示词缺陷

- `9b74197f` 的100/1000人服务隔离及导出复验通过。真实模型short中千人档通过；100人档性能通过，但L3返回`goal_portfolio.status=pending`，原validator拒绝后Character作业stale，矩阵失败，不能用千人档通过代替整矩阵。
- 根因：提示词只说明goal_portfolio是目标列表，没有提供其状态枚举等嵌套合同。由原`CharacterGoalPortfolioEntry.model_json_schema()`直接生成提示词约束，保持validator严格拒绝pending；不映射状态、不放宽stale门禁、不添加自动成功回退。
- 回归先观察提示词缺合同失败，再核对提示词中各合法状态均能被原validator接受，以及实测非法pending仍被拒绝。模型gateway/provider/L3共131项通过；使用原失败请求及新提示词的真实DeepSeek诊断通过且无fallback。这不是正式矩阵证据。
- 重新冻结此修复后重采service、short及其余性能证据；旧`9b74197f`证据保留诊断，不混入新版本总聚合。远端run35487905677的harness/change-lifecycle及correctness失败尚缺具体日志，本地同版两项通过不替代远端结论。

## 长历史验收暴露的观察面板历史重建

- `de309bb3` 千人造档在5,000窗后明显变慢；15秒/1485样本采样中，约75.9%包含结算后的记忆读取，62.1%包含轻量记忆的完整投影。正式冷恢复尚未开始，停止本轮拥有的生成进程并导出失败现场；不能宣称恢复通过。
- 现有面板契约保留完整摘要，不能通过截断记忆或跳过实际结算让验收加速。轻量角色新增持久化摘要索引：每事件复用原记忆归一化规则，仅点读同一claim的当前记录，保留五类记忆顺序、覆盖、修正及过期claim行为。摘要文本仍完整输出，其读取成本随实际输出长度增长。
- 摘要与session event/current在同一事务内更新；recovery schema 3为旧库一次性构建派生索引，升级失败回滚，普通重启不得重放历史。显式完整记忆接口和重量角色图谱scope/branch/valid-time过滤不变。无持久库的兼容模式保留已有内存时间线读取。
- 回归包括实际结算拒绝全历史折叠、全量oracle逐事件等价、修正、普通重启、旧库迁移、缺表拒绝与写入故障回滚；使用原造档入口测量修复效果，再运行完整backend和正式门禁。任何旧提交的通过证据不混入新版本聚合。
- 修复版本完整backend为6916 passed、2 skipped，工具测试421 passed，独立审查无未解决问题；Godot未验证。原造档入口1000人/256历史窗/tail8诊断完成57.4秒、清理通过，只证明诊断运行完成，不能代替正式1000/10000历史窗与五次冷恢复。后续从冻结提交重新采集全部同版门禁。

## 混合长测暴露的记忆评分与 Siming 冻结重复存储

- `1fc736ac` 已完成 correctness、change-lifecycle、100/1000服务隔离、真实模型short、千人1000/10000历史各5次冷恢复及5配对transport；这些结果只适用于该提交。首个100人30分钟soak在SQLite故障前已有204个窗口lag>1，最大约6.453；停止失败队列，保存原始现场。50秒诊断采样4222条、1次栈读取失败，不将附加采样后的运行当作正式性能证据。
- `CharacterMemoryRecallPolicy.select` 在每个候选评分内重新扫描整池最大时间戳，形成O(N²)时间戳读取。改为每池只计算一次，排序、相关性、强记忆、预算、缺证据和独立副本契约不变。计数回归覆盖128/1024历史，旧1024×2条记录读取2101252次；新路径必须满足线性读取上限，不能用机器时间抖动代替复杂度验证。
- 同一现场的Siming入站最大节点约1.14MB，其中plan_pin的角色完整记忆约1.10MB；每次入站转移重复序列化和持久化。`capture_prepared_pin` 改为对原完整ActorMemoryReadResult计算规范化SHA-256，继续覆盖全部池、顺序、完整性、原因、scope/time及revision vector，不能只信任声明的vector。原权威记忆与模型输入不截断，图读集仍保留原节点/关系用于输出引用校验。
- 先复现pin随历史膨胀的失败，再验证1/256条历史的pin上界、相同vector下正文和元数据变化仍拒绝旧completion、合法completion仍完成、旧版完整pin恢复按stale零写入。该内部pin表示变化不迁移已有事实，也不把旧在途请求重新授权；部署前尽量排空，跨版未排空请求可能stale。
- 独立审查并完成完整backend后重新冻结；先执行short/soak确认此处长测缺陷，再重跑其余同版正式门禁，避免在已知失败前重复耗时造档。原门槛、SQLite耐久性和Godot外机规则不变。新增代码未验收前不得称六项闭环完成。
- correctness正式集合纳入记忆召回回归。远端CI完整日志受登录限制，新增只读摘要入口，从本轮manifest/profile结果及focused JUnit提取失败profile、退出码、结构化错误和测试名，写入GitHub运行摘要；不复制模型请求、配置、完整日志或环境变量，不代替原始artifact，也不改变任何失败退出码。后续从新提交CI摘要继续诊断真实根因。
- 修复后完整backend为6927 passed、2 skipped，工具425 passed；两次拥有作用域清理均通过，独立审查无未解决问题。该结果仅覆盖代码回归；新冻结版本的short/soak、其余同版性能与外机门禁仍待采集，不能继承`1fc736ac`的部分通过结果。

## 其他审查重点

### 94432434 长测新增的 Character 阶段重复内容

- short 两档通过；100 人 soak 的 721—738 窗出现 9 个 lag>1，最大3.109，未进入SQLite故障段，不能接受为通过。原始 Character 进度最大5.62MB，其中frame约1.725MB、before/after计划约3.45MB，重复冻结context及L3准备数据。停止失败采集，原始结果保留于仓库外；不得删除坏窗口后继续验收。
- 复用原 session 不可变 receipt，为context、l3_prepared、suggestion_context各冻结一次完整内容。compact frame记录actor/child/origin stage/field绑定及完整内容digest；l2 context可沿用至后续阶段，suggestion替换L3准备时使用独立来源阶段key。冻结数据和首次引用在同一session事务中写入。
- read_progress核对原progress digest，并验证frame、plan.before、plan.after中的引用；仅校验原JSON字节摘要，不在普通阶段读取时展开整份上下文。实际规划/完成所需正文通过窄reader读取；旧inline frame继续按原义恢复，不截断模型记忆、不改变原request_json和source/activation/CAS合同。
- 回归须覆盖真实coordinator在大context下进度体积有界、完整内容相等、重开不重新规划、同actor跨child及跨actor引用拒绝、缺失/篡改在效应前零写入、冻结事务失败回滚、L3和suggestion替换及旧inline恢复。Character导出/离线复验同时保留和校验冻结receipt，不能让引用掩盖缺证据。
- 远端94432434 CI correctness和change-lifecycle失败，公开页面没有具体日志内容；本地通过不能覆盖远端失败。首次停止长测时矩阵已启动下一case，已停止新增自有后端；自动cleanup因文件占用失败，后续递归清理被自动审批策略阻止，临时根0f3255aecc86480cbf54bf577a251811保留并单列未清理。
- Character 引用存储的定向回归68项通过，覆盖缺失/篡改/错身份零写入、事务回滚、旧inline进入新L3、suggestion替换、重启与原始导出拒假。失败现场真实大进度对照15次中位80.19ms→5.29ms、5.47MB→0.502MB，正文相等；仅为诊断。独立审查核对实际旧上下文产生的L3请求JSON与prompt等价，未发现该实现的未解决缺陷。完整回归和重新冻结后正式门禁另行记录。
- CI过滤摘要增加有限公开warning annotation，保持原退出码和私有内容过滤。审查复现Windows cp1252 stdout不能输出中文测试名，已改ASCII转义并加受限编码回归，6项通过。
- 最终回归：完整backend首次6941 passed／2 failed／2 skipped，两项失败均为执行期间追加CI诊断文件导致的源码身份变化；停止修改后原两项补验2 passed（23.76秒），不能把首次命令记为退出0。工具427 passed，独立审查无未解决项，三个测试作用域均清理通过。证据分别在仓库外pop-cognition-frame-full、pop-cognition-frame-identity-recheck、pop-cognition-frame-tools；后续正式correctness仍须按新冻结提交完整采集。
- 额外诊断：失败混合存档约205,030条普通gameplay outbox待派发；原启动同步drain约8分钟。该混合积压恢复开销尚未解决，应继续验证；不能用无此积压的cadence冷恢复结果掩盖，也不在本轮正文去重修复中暗改派发语义。

### CI 非 editable 构建产物与源码身份

- `deeba751` 新 CI annotation 首次提供具体失败：change-lifecycle 子进程退出0，封存器报 `harness_archive_coverage_or_result_invalid`。本地用原 backend pyproject 在最小 Git 仓库实际构建，退出0后产生未忽略的 `backend/build/lib/app/__init__.py`，Harness 身份从 HEAD 变成 HEAD+dirty；封存器要求原报告revision与HEAD一致，因此这类构建产物会误伤验收。该复现证明本地同类路径，远端修复效果仍必须以新CI为准。
- 仅在 `.gitignore` 增加 `/backend/build/`，不放宽源码摘要、HEAD或脏源校验。回归先证实旧规则会标dirty，再确认构建复制不改变提交身份、真实 `backend/app` 修改仍标dirty。工具套件428项通过；混合选择工具测试时包装器遗留HARNESS环境造成的两项失败已通过工具完整套件重验，不修改测试的顶层作用域契约。
- 为避免已知CI缺陷版本消耗整轮数小时，`deeba751` soak在276个measurement窗口后主动停止：最大lag约0.406、backlog始终0，仅为不完整诊断；该轮拥有进程和临时根7bd0d49b2c3f42bca771ee85fd1c9c6a正常回收。两档short原始通过保留，但不重贴新SHA。
- 最小构建诊断临时Git只读object导致自动清理失败；随后对本轮根9ade0810227245828e9a056f6b927094的递归清理被自动审批以blocked by policy拒绝，未绕过，保留目录并列入未清理清单。诊断证据位于仓库外pop-ci-build-identity-diagnostic。

- 正确性门禁自身串行执行四个producer和一组focused测试，每步原预算1200秒；原外层profile默认900秒会在合法子步骤结束前杀进程。已复现`900 < 5×1200+60`的预算冲突，外层独立配置6100秒，仍受CI job105分钟限制；不调整1×/10×性能、ready或任何业务验收阈值。新增预算层级回归，真实远端CI结果仍须重新核实。

### 冷检出脚本 UID 与 CI 变更定位

- `4224a961` 本地 change-lifecycle、完整 correctness、两档真实模型 short 均通过，导出复验及作用域清理通过。远端 CI 已越过 change-lifecycle，`all` 在首次运行 Godot 的 character-agent-execution 报源码身份变化；这不等于运行时 consumer 失败，也不能声称完整 CI 通过。
- 静态核对发现 PopulationPresentationAdapter、PopulationPresenter、PopulationProbe、CharacterMotorCoordinatesProbe 缺少四个 `.gd.uid`。按 Godot ResourceUID 编码补齐未使用的稳定 ID，原有资源仍按路径引用。新增冷检出回归要求已跟踪 GDScript/shader 同时跟踪 UID；不忽略 UID、不放松源码身份检查、不改导入提前退出 P2。
- Harness 身份失败报告增加相对 HEAD 的当前脏 Git 路径列表（用于定位，不冒充 dirty 起点的逐文件运行差异），CI 只公开有限路径，不复制文件内容或请求。原失败退出码不变。RED 为3 failed／426 passed，分别命中 UID 缺项、报告未含路径、摘要未含路径；修复后完整工具429 passed（55.34秒），作用域清理通过；新 CI 仍须验证。UID 导入效果仍标 Godot 未验证。
- 旧版本 short 完成后在下一阶段入口停止，未启动长测，避免明知需修复仍采集数小时旧源码证据。新提交冻结后从同版门禁重新采集，不重贴旧证据身份。

### CI 慢机器测试预算与双后端失败定位

- `39bd27fd` 的本地 change-lifecycle、完整 correctness、两档真实 short 均通过。100人soak越过旧721—738窗口失败区间仍无积压，前缀最大lag约0.531；为修复CI在约13分钟停止，未完成30分钟，不计正式长测通过。拥有进程及临时根52c84738d1c8406da2ec49236e589359由run_scope正常清理。
- CI #205 的具体新证据为 focused 测试退出124、1200秒超时。#206 已越过首次Godot的源码身份错误，all在Phase0默认900秒外层超时；该外层甚至短于内部完整pytest原1200秒预算。两处均不能通过放宽业务或性能断言解决。
- 分离 focused 2400秒与四个producer各1200秒预算；manifest与离线复验必须精确匹配各自预算，外层population profile为7300秒、CI job为130分钟。Phase0完整pytest默认2400秒、外层4200秒，覆盖两段标记等待、四个120秒命令及回收余量；Godot导入提前退出P2仍不处理。
- #206 correctness在21分49秒结束，失败项为 `test_two_actual_backends_share_interval_and_preserve_independent_sqlite`，不能认定单纯超时。原始失败XML尚不可读取；本地限定两个逻辑CPU的独立诊断1 passed／13.32秒，未复现，也不代表问题已修复。CI摘要追加仅含已知内置异常类型、真实仓库Python行号的JUnit定位，以及超时时最后的数字进度；不公开断言局部值或原始请求。
- 两处预算和诊断各先观察RED，随后定向回归、完整工具回归和独立审查，再冻结重采。若双后端再次失败，必须根据新增定位修复，不能删测试、重贴证据或将未执行项当作通过。

检查非激活 Owner 历史增长、重复回执晚于其他写入时的截面、未提交结果、损坏/截断事件和持久库重开；不得以局部digest冒充full_replay。审查指标是否实际观察缓存及所有复验入口是否拒绝缺字段；不修改Godot导入、耐久性、事务与权限契约。

- 本轮最终回归：后端预算/证据41 passed，完整工具435 passed（57.50秒），作用域清理通过。独立审查发现的JUnit单词元正文及伪路径泄漏已先复现RED，再限制为内置异常类型及真实仓库traceback位置；复核无未解决项。双后端远端失败仍待新CI定位，不计已修复；冻结后重采全部本机门禁。

### CI 异步测试等待边界与子进程失败定位

- `81292848` 的 change-lifecycle、完整 correctness（focused 1704项）和两档真实模型short均通过并复验。100人30分钟混合场景完整采集与离线复验通过：1800窗、cadence p95约119.6ms、非故障max lag约0.735、最终backlog0；SQLite锁释放后约0.96秒恢复。RSS长期增长门禁只适用于2小时场景，本档不能代替该项。为定位新CI失败，在下一千人case入口显式停止，矩阵仍失败/不完整，拥有作用域清理通过。
- CI #207 correctness退出1，新增安全诊断定位到scheduled cognition测试的参数0和None在子进程returncode断言失败；本轮未再报告上一轮双后端失败。Phase0退出1且未产生报告，内部原因仍需诊断，不能归咎于已暂缓的Godot导入P2。
- 本地双核原三参数3 passed；控制模型完成延迟10秒（小于生产默认20秒期限）后，原固定250次轮询确定提前断言transient任务未结束。新增同场景回归先1 failed，再把两处完成等待改成30秒有界条件循环、外层子进程75秒。保留原owner0.5秒响应、线程隔离、来源身份、最终completed与精确stale理由断言；不改生产超时/期限/性能预算。双核四参数4 passed（19.08秒）。这是已证实的测试缺陷，不能声称已唯一解释远端两项失败。
- CI摘要对失败profile的command.log只提取内置异常类型及当前仓库实际Python文件行号；JUnit内嵌python -c只输出数值行号，避免下一轮仍只能看见父进程断言。私有正文、任意函数名、伪造/仓库外路径不输出。诊断RED为2 failed／12 passed；完整工具438 passed（60.80秒），清理通过。独立复核和新CI结果另记，随后仍须新冻结版本同版门禁，旧结果不可改签。

- 最终独立复核无阻断项，确认原正确性/owner响应断言及生产门槛保留，安全诊断未输出正文或仓库外路径；后续以新提交CI和完整矩阵为准。

### CI #208 排空观察、测试握手与端口释放

- `2e5baad2` 的 change-lifecycle、correctness（focused 1705项）、两档真实 short 通过；100人30分钟独立复验通过。为修复新CI失败，在下一千人case入口显式停止，整组soak仍未完成；本轮作用域清理通过。旧版完整单档结果不能代替新冻结版本矩阵。
- CI定位：双后端在 `population_mixed_verification.py` 拒绝 `mixed_process_tail_pending`；scheduled cognition 两参数在子进程第68行的owner 0.5秒等待失败；Phase0在停止自有后端后等待8000端口释放失败。最后一项与暂缓的Godot导入P2不同。以下本地复现只证明对应缺陷，远端是否全部解决以新CI为准。
- 步骤1：排空等待每次采集完整资源记录，用该记录判断所有IPC/发送/运行时/传输pending和执行额度均为零，成功时原样落盘；消除第二次snapshot的竞争，不改离线严格拒绝门槛。回归覆盖首次合格后下一次观察重新忙碌、非零等待及不健康拒绝，再跑真实双后端隔离用例。
- 步骤2：以有界握手证明provider仍阻塞时owner已实际执行。回调核对provider已进入、未放行且未退出，owner确认后才release；保留线程身份、30秒完成等待、精确stale和来源断言。加1秒owner工作负载复现固定0.5秒测试的误判，正式服务隔离性能门槛不变，不把共享CI功能测试当性能基准。
- 步骤3：复现端口探测本身耗尽等待预算的问题，核对自有进程已关闭；以单调时钟和有界本机TCP连接观察替代每次启动PowerShell查进程。只有明确拒绝连接才计作端点释放，连接成功、超时或其他错误均不能通过；连续清空次数仍要求2。用真实非HTTP监听、停止自有监听进程以及超时/重新占用测试检查，绝不按端口杀进程；Godot保持外机验证。
- 步骤4：定向RED/GREEN、完整工具回归、独立审查后合并推送。冻结新SHA后串行采集所有本机门禁，跟踪新CI，外机Godot/mainline/all、批准char_c绑定及VLA凭据仍须实证；Goal不在局部修复后结束。
- 验证：后端新增RED为2 failed，修复后双核定向27 passed（47.76秒），包含真实双后端隔离；端口RED为5 failed／1 passed。首次完整工具444 passed／2 failed揭示Windows关闭端口约2秒后才返回拒绝连接：实测1秒上限为TimeoutError，3秒上限下约2.031秒为ConnectionRefusedError。探测改为使用剩余总预算，默认15秒不变；重验完整工具446 passed（67.05秒）。各作用域清理通过。
- 独立审查发现的测试就绪文件创建/写入竞争已改为同目录临时文件关闭后replace发布；最终复核无阻断项。旧版100人30分钟单档p95约119.34ms、非故障max lag约0.594、最终backlog0，SQLite锁释放后约0.90秒恢复；只保留旧版诊断，不改签、不代替千人2小时或整矩阵。Godot仍未在本机运行。

### CI #209 raw cognition 与新增长测停顿

- `b795b7a4` 的 change-lifecycle、correctness（focused1707 passed）与两档真实short通过、导出复验和清理通过。100人30分钟完整单档离线复验为 integrity通过、performance失败；故障前tick221的fixture约1296.79ms、cadence约109.96ms、lag1.422，tick1003另有lag1.219，均随后追平。下一个千人case显式未启动，整组soak未完成，拥有作用域清理通过。不得删除超限窗口或将其按无证据的“环境抖动”排除。
- 只读追踪：每窗28组schedule/open/close共84个原独立事务，未发现该fixture路径的全历史扫描；SQLite仍为WAL/FULL。墙钟明显高于进程CPU增量，提交同步、checkpoint、锁等待和调度停顿尚需分段诊断。忽略目录内诊断入口将分别计量事务进入、正文、退出的墙钟与线程CPU，保持交易粒度与耐久性，不把local_probe/带仪表结果当正式性能证据。单窗门槛是否调整已向用户提出可选澄清；未明确答复前保持既有门槛。
- 新CI的scheduled与双后端未出现在失败摘要；Phase0已生成报告，越过原端口释放异常，但backend_tests和多项Godot场景仍缺失。correctness精确定位到raw cognition测试断开/不断开两分支的子进程第46行，即另一个固定0.5秒owner等待。不能用本地focused通过覆盖远端失败。
- 修复步骤：为raw两分支加入1秒owner工作回归，非断开增加合法10秒模型延迟；采用provider未释放/未退出时owner实际执行的有界握手，并以30秒条件等待替换固定250次循环。保留线程、无挂起任务、断开后已提交prefix不变等断言；不改变生产性能门槛。Phase0输出本轮命名JUnit，复用原安全过滤器只公开失败测试、内置异常类型及实际仓库行号，避免只能看到backend_tests=missing。
- 完成标准：先观察新增失败回归，再完整双核后端与工具测试、独立审查；事务停顿另外按原门槛定位。Godot表现继续外机验证，导入提前退出P2仍不修改。最后按明确的最终合同冻结新SHA，串行补齐所有同版门禁，Goal保持进行中。

### CI #209 完整后端暴露的 Windows 子进程回收竞争

- raw补强后的双核7项通过，包含真实completed、provider正常返回、断开后的prefix和任务清空；工具447项通过。首次完整双核Phase0环境回归为6947 passed／2 failed／2 skipped（628.82秒），两个失败均为InteractionSession探针清理临时SQLite时的WinError32，不能归因于Godot表现。
- 原拥有Job的活动进程计数已经归零，父进程已经退出，但原子进程句柄仍返回WAIT_TIMEOUT。两次真实backend诊断预先持有三个进程句柄，原stop约2.5ms返回时两个子进程未发退出信号；等待同一Job信号后约9.2ms所有句柄均已确认退出。诊断不运行Godot，不作为引擎证据。
- 最小修复：TerminateJobObject后有界等待Job信号，仍为5秒预算，仅WAIT_OBJECT_0通过，WAIT_TIMEOUT/WAIT_FAILED拒绝；父process.wait和所有权边界保留，不按端口终止进程，不吞文件清理异常。真实持SQLite子进程与两项等待异常回归先3 failed；修复后原InteractionSession双核2 passed／24.29秒，完整工具452 passed／69.53秒。覆盖父子存活、父先退出但子仍持库、父子自然退出三种场景。
- 平台边界：实测Windows NT 10.0.26100.0。[微软TerminateProcess说明](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess)明确异步终止需要等待；[官方Job说明](https://devblogs.microsoft.com/oldnewthing/20130405-00/?p=4743)不承诺一般自然退出必然发Job信号。本实现每次显式TerminateJobObject后等待，当前平台回归通过，仍须新CI实证，不扩大为跨Windows版本保证。独立只读审查无已确认阻断项。
- 本轮初次全量失败遗留的paralls-session-i4ab27nf、paralls-session-smcnwpd7仅有本轮临时存档；拥有进程已退出。自动审批以blocked by policy拒绝清理，未执行、未绕过或重试；与此前两个已记录清理阻塞分别保留。修复后新作用域正常清理。
- 接续：源码保持不变完成完整双核后端复验，串行执行180秒local_probe事务分段诊断；完成审查及提交推送后重新冻结同版正式门禁。严格单窗lag门槛继续保留，六项总闭环尚未完成。
- 最终双核后端复验6949 passed／2 skipped／0 failed（639.90秒），清理通过。180秒local_probe诊断完整采集180窗、15120个事务：fixture p95约144.75ms、max148.73ms；事务进入max0.31ms、正文max1.58ms、退出max14.23ms。WAL/FULL、autocheckpoint1000、busy_timeout5000不变。未复现旧tick221/1003停顿，不能宣称其已修复或归因checkpoint；下一步以覆盖221窗的真实provider诊断区分负载差异，旧性能失败继续保留。原始材料位于仓库外`D:/HarnessEvidence/pop-b795-fixture-transaction-diagnostic`，带仪表及local_probe结果不用于正式聚合。

### fdf6a045 同版正式长测与 SQLite 页缓存

- `fdf6a045` 的 correctness（1742项）、change-lifecycle、100/1000服务隔离、千人1000/10000历史各5次冷恢复、5配对transport及两档真实模型short均通过并完成离线复验。soak中100人/1000人各30分钟1x通过，10x完整性通过但独立性能门槛未过；千人2小时处理性能通过，RSS首60窗中位199716864字节、末60窗中位237352960字节，增长37636096字节，超过33554432字节门槛，因此整组soak失败且capacity未启动。不能把其他同版通过项合并为六项闭环。
- tracemalloc和运行时类型快照确认Python活对象及显式缓存已稳定，AuthorityEvent只增长至事件总线上限；2小时内graph和gameplay SQLite文件分别增长到约3.4GB和5.5GB，四个长驻连接仍使用SQLite默认`cache_size=-2000`。根因修复只为四个长驻运行时连接设置`cache_size=-256`，保留WAL、FULL同步、autocheckpoint、事务粒度、事件保留及恢复语义。
- 回归先观察缺失常量及默认`-2000`失败，再通过真实runtime核对Heavenly Graph、Character Session、Gameplay Event Store、Siming Audit四个连接均应用各自声明的256KiB上限。定向存储/生命周期回归48 passed；完整后端与验证工具合并回归7453 passed、2 skipped、0 failed（859.28秒）。
- 1000人、1x、600秒同构诊断完整采集600窗：cadence p95约148.76ms、最终及最大backlog均为0，RSS首/末60窗中位约137.09/155.28MiB，增长18.20MiB；原`fdf6a045`相同前600窗为147.00/180.82MiB，增长33.82MiB。本结果只证明修复方向和早期余量，不能替代冻结新提交后的千人2小时正式门禁。
- 下一步冻结并推送缓存修复提交，然后在同一干净SHA串行重采correctness、change-lifecycle、service、recovery、transport、真实模型short、完整soak和2/4局capacity，最后生成总聚合。Godot运行时、Archive Door获批准的`char_c` IK绑定、VLA真实凭据及当前SHA的mainline/all仍按外部实证状态报告；缺失时保持未完成。
