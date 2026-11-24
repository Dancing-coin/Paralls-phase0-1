# 守城三条域路径证据

最新状态见本文末尾的 2026-11-24 验证。以下 2026-11-23 记录保留当时的基线和状态。

- 基线：`810a46c1249918c09b42fa1fe0c12d7d784579d2`，标签 `integration-2026-11-23`。
- 当前 B 分支：`thread-b/reference-data-20261123`。Information 代码修复提交为 `6741ab6115d5c280390aaba162fa1e109f6064e3`；后续文档提交移动了远端分支 tip。A 应 fetch 时使用该分支最新 tip。定向测试与 U11 在该代码提交前以相同源码内容复验。
- 扫描命令：`git status --short`；`rg -n "morale|passability|breach|Information" backend/app backend/tests docs/v2-coordination`；pytest 收集命令见下文。
- 验证时间：2026-11-23 Asia/Shanghai。
- 结论等级：Information 域写入通过所列定向测试、P-3 与选择集门禁；Morale、Presence 阻塞，未实现其域写入。三条守城生产路径和 Architecture v2 单元均未验收。

## 三条路径状态

| 路径 | 当前 B 侧结果 | 状态 |
|---|---|---|
| casualty → Morale | 已验证 LifeState 的真实死亡提交与 outbox；没有守军编制权威事实，也没有已裁定的 D8 重算规则。`relationship_private_estimate.py` 的 morale 只是角色私有估计。 | 阻塞，未实现 Morale writer。见 `handoff.md` H-B-003 与 `design.md`。 |
| facility breach → Presence | 当前源码未发现已提交的设施完整度破口事件或生产 writer。Construction Production 的维修把 condition 提高，不能作为 breach 输入。 | 阻塞，未实现 Presence 通行性 writer。需 Facility Owner 的源事件、FactType、payload 与 revision 合同。 |
| report delivery → Information | 真实 SocialDelivery v2 receipt 经 recipient、可见性、撤销和 source revision 校验后，提交 recipient 私有的 `gameplay.information.knowledge_updated@1`。 | B 域 writer 和列出的 P-3 / 回归门禁已验证；生产 Gateway/L5 接线待 A。 |

## U1–U11：Information

| 项 | 状态 | 证据及缺项 |
|---|---|---|
| U1 Owner 声明与分类 | 部分 | `backend/app/gameplay/fact_type_registry.py:27` 登记规范短名 `Information`。本单元没有完整 Owner 声明、writes/denies、不变式和 Resolver 清单。 |
| U2 FactType 声明 | 未做，偏离已记录 | 没有提交 `packs/information/` 规则包或 FactType。A 需按 recipient 可见性确定输出 `fact:information:<scope>:report` 的精确 scope 与声明。 |
| U3 事件 schema 与 P-3 | 已验证，范围有限 | `backend/app/gameplay/information_event_schema.py:12-23` 声明 `gameplay.information.knowledge_updated@1`。`backend/tests/test_siege_information_runtime.py:121-143` 将已提交事件经真实 outbox dispatcher 发布到 `HeavenlyAuthorityEventProjector`，断言图节点 domain=`information`。该测试也断言事件在 `FACT_TYPE_REGISTRY.event_types()`，见同文件 `104`。这证明域 schema discovery、FactType 成员和测试中的 projector 路径，不证明生产 EventSchema factory 或 Gateway 接线。 |
| U4 共享 Owner 机制 | 部分 | `backend/app/gameplay/information_runtime.py:111-147` 用 atomic event batch、source/delivery stream read revisions、recipient visibility 和 outbox；未接 A 的统一 Gateway / OwnerCommitBuilder。 |
| U5 R1/R2/R3 | 部分 | R1 精确重试测试 `test_siege_information_runtime.py:110-118`。R2 同文件 `84-108` 校验提交事件、visibility、CAS read revisions。Source revocation 零写测试在 `159-177`。Information 独立 durable reopen 与 checkpoint-tail 测试未做。 |
| U6 读取方与专项测试 | 静态清单及定向测试 | B writer 的生产读取者是 `backend/app/gameplay/p5/social_delivery.py` 中的 `SocialDeliveryAuthority`，实例化见 `information_runtime.py:6,29`；A 的 Gateway/L5 尚未导入本 writer。测试直接构造调用方见 `test_siege_information_runtime.py:69-82`。未核实动态反射消费者。 |
| U7 可见性与读取边界 | 部分 | 写入事件和 outbox audience 限定 `actor:<recipient>`，见 `information_runtime.py:128-145`；面向主体读取策略与生产 `read_as` 未接通。 |
| U8 规则包与 Resolver | 未做，偏离已记录 | 当前实现通过 Python `InformationAuthority.update_knowledge` 处理，未由规则包 Resolver 驱动。 |
| U9 探针与基线比较 | 部分 | 真实 SocialDelivery → Information 写入和 outbox → projector 测试通过。零代码规则包探针未做。五组冻结选择集与三个已登记选择集比较结果见“验证”。 |
| U10 文件清单及验证等级 | 完成记录 | 代码、测试、选择集、board/handoff 与本证据均列于变更摘要。 |
| U11 单元选择集 | 已登记并比较 | `docs/verification/selection/siege_information.json` 登记 10 个唯一节点；包含参数化 P-3 测试的三个真实 node IDs。比较结果见“验证”。 |

## 已验证环境

```text
3.12.2 (tags/v3.12.2:6abddd9, Feb  6 2024, 21:26:36) [MSC v.1937 64 bit (AMD64)]
F:\\codex-temp\\paralls-v2-thread-b-reference-data-20261123\\backend\\app\\__init__.py
```

本次选择集比较使用 `docs/verification/absorb-main-3bf3418e/compare_selection.py`。原始分批日志和结果位于 `F:\\paralls-verification\\thread-b\\siege-three-paths-20261123\\`。

```text
ownership: selected=24 problems=0 improvements=0
modifier: selected=12 problems=0 improvements=0
equipment: selected=87 problems=0 improvements=0
inventory: selected=56 problems=0 improvements=0
shared-replay: selected=990 problems=0 improvements=0
life_state: selected=12 problems=0 improvements=0
reference_data: selected=15 problems=0 improvements=0
siege_information: selected=10 problems=0 improvements=0
```

定向 pytest 在本次显式 `TEMP`、`TMP`、`TMPDIR` 均指向 F 盘的运行结果：

```powershell
$env:TEMP = 'F:\\paralls-verification\\thread-b\\siege-three-paths-20261123\\runtime-temp'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$env:PYTHONPATH = '<current worktree>\\backend'
& 'D:\\Temp\\paralls-g0-py312\\Scripts\\python.exe' -m pytest -q `
  backend/tests/test_siege_information_runtime.py `
  backend/tests/test_p5_social_delivery.py `
  backend/tests/test_infra_reference_data_license_admission.py
```

原始结果：

```text
50 passed, 2 warnings in 0.89s
exit_code=0
```

修复提交 `6741ab6115d5c280390aaba162fa1e109f6064e3` 后再次运行同一组定向测试，原始日志 `F:\\paralls-verification\\thread-b\\siege-three-paths-20261123\\information-targeted-abba3c3c-fixed.log`：

```text
50 passed, 2 warnings in 1.02s
exit_code=0
```

F 盘 TMPDIR 的冻结选择集重跑只完成部分：ownership 24、modifier 12、equipment 87、inventory 56 均 `problems=0`。shared-replay 两个节点因 `127.0.0.1:8000` 被外部 UnrealEditor 进程占用而失败，因此完整 G5 未通过。

在继续授权后，单独重跑本域 U11 选择集，TEMP/TMP/TMPDIR 均指向 F 盘：

```text
selected=10 problems=0 improvements=0
exit_code=0
```

输出位于 `F:\\paralls-verification\\thread-b\\siege-three-paths-20261123\\siege-information-selection-final\\`。冻结五组中的 shared-replay 仍有两个失败，不能以本域 U11 通过替代 G5 全部选择集门禁。

最终源码复验的 U11 输出位于 `F:\\paralls-verification\\thread-b\\siege-three-paths-20261123\\siege-information-selection-abba3c3c-fixed\\`：

```text
selected=10 problems=0 improvements=0
exit_code=0
```

此前默认 `TMPDIR=D:\\codex-temp\\user-temp` 的全量分批诊断结果为 `10,448 collected`、`10,420 passed`、`24 failed`、`4 skipped`。24 个失败是已记录的 22 个冻结失败节点，以及在 2026-11-23 LifeState integration 基线复跑中也复现的 `test_cold_ready`（KeyError）与 `test_recovery_owner_probe_measures_original_startup_before_full_oracle`（AssertionError）。该结果不作为本单元的有效门禁证据，因为测试临时目录未按 F 盘要求设置。单次 G0 runner 未生成 `results.json`。四个 skipped 对应既往摘要中的 2 skipped 与 2 xfailed，本次 runner 将其统一记作 skipped。

P-1 仓库 tracked secret scan 原始输出：

```text
tracked_model_secret_offender_count=0
harness_cleanup=passed run_id=2fc9a9f3d4e84ad19ae59ae2415a2124
```

随后在检查监听 8000 端口的外部进程时，发现 UnrealEditor 命令行含认证凭据。值未记录；具体凭据公开状态未核实。依 `AUTONOMY.md` §二停止条件，停止进一步扫描、提交与推送。该外部进程未被终止或修改。

F 盘定向测试日志、F 盘 TMPDIR 的部分选择集日志，以及此前诊断输出均位于 `F:\\paralls-verification\\thread-b\\siege-three-paths-20261123\\`。未运行 Godot、生产 Gateway/L5 M6 探针或生产 Demo。当前 G5 阻塞，提交和推送未执行。

## 对 A 的交接

- A 可使用 `register_information_event_schemas` 接入生产 EventSchema factory；域声明在 `backend/app/gameplay/information_event_schema.py:19`。共享注册表归 A，B 不改。
- Gateway/L5 输入候选为已提交 `gameplay.social.delivery_recorded@2`，命令候选为 `information.update_knowledge`；参数至少绑定 `delivery_event_id`、`recipient_ref`、`known_at_world_tick` 与目标 stream revision。具体目录按 A 的命令/Owner 映射落实。
- 输出 FactType 候选为 `fact:information:<report-scope>:report`。该事实表达“该收件人已收到报告”，不表示报告内容为真或其内在信念。精确 scope、可见性和 resolver binding 由 A 按规范接线。
- Morale 仍需守军成员权威事实及 D8 规则；Presence 仍需 Facility 已提交 breach 源事件与 revision。不可用候选 roster 或维修事件代替这些输入。
- 本证据不覆盖 M6 Gateway/L5 生产接线、Workflow 持久义务、外部生产 Demo 或端到端 M6-5 验收。


## 2026-11-24 守城 Information 接线交付

B 开工基线为 `8b37e3ce49ff241625102bea857cc82215216503`，代码提交为 `63f41c8b47e7fa14c607c554d473dae2193c5d7c`。A 的远端验证基线为 `8227e94c609247eaba1a663ee52d5ae69b1db90b`。A 的恢复提交 `102e4380f2bbc3e85700e4332bfeae1ea01d69f3` 在本机可读取，补验时尚未出现在 A 的远端分支。Python 3.12.2，运行前断言 `app.__file__` 位于对应目录的 `backend` 内，TEMP、TMP、TMPDIR 全部设在 F 盘。原始日志根目录为 `F:/paralls-verification/thread-b/siege-handoff-20261124-mwu47q4f`。

| 验证对象 | 原始结果 | 日志 |
|---|---|---|
| A `8227e94c` 的守城 runtime、签名输入、Morale、Presence、Facility、L5 | `32 passed, 6 warnings in 3.41s` | `a-pytest.log` |
| B Information、SocialDelivery 和 ReferenceData 许可 | `51 passed, 2 warnings in 1.02s` | `b-pytest.log` |
| A `8227e94c` 加 B Information 两个模块、域测试、规则包和探针 | `39 passed, 6 warnings in 7.49s` | `combined-pytest-02.log` |
| A `102e4380`（签名输入恢复）加相同 B 文件 | `41 passed, 6 warnings in 7.25s` | `combined-recovery-pytest.log` |
| B 父提交的两个端口相关节点 | `2 failed, 6 warnings in 8.82s` | `b-parent-port-8000.log` |

定向命令使用 `python -B -m pytest -q -p no:cacheprovider --basetemp <F 盘独立目录>`。A 的测试文件为 `test_m6_5_siege_runtime.py`、`test_siege_physical_input_runtime.py`、`test_morale_refold_runtime.py`、`test_place_passability_runtime.py`、`test_facility_integrity_runtime.py`、`test_l5_dispatch_runtime.py`。B 的文件为 `test_siege_information_runtime.py`、`test_p5_social_delivery.py`、`test_infra_reference_data_license_admission.py`。测试文件均在 `backend/tests/`。

重现组合的步骤如下。

1. 用 `git archive <A SHA> backend packs assets/characters/profiles` 提取到 F 盘独立目录。第一次只提取了 backend 和 packs，收集时缺少启动所需的角色 profiles。补入相同 A SHA 的 profiles 后复跑。首次日志为 `combined-pytest.log`。
2. 从 B 代码提交复制 `backend/app/gameplay/information_runtime.py`、`backend/app/gameplay/information_event_schema.py`、`backend/tests/test_siege_information_runtime.py` 和 `packs/county_siege_information/`，把 [组合探针](probe_information_gateway.py) 复制为组合目录内的 `backend/tests/test_information_gateway_probe.py`。
3. 从组合目录设置并核验解释器、应用导入路径和临时目录。使用同一 pytest 命令加 `-o pythonpath=backend/tests`，运行 A 的六个文件和 Information 域测试、组合探针。探针以测试报告 ID 模拟生产来源映射，以 fixture tick 驱动真实域处理方。

P-3 断言在 `backend/tests/test_siege_information_runtime.py` 的 `test_committed_delivery_updates_only_its_recipient_knowledge` 和 `test_committed_information_event_reaches_registered_graph_projector`。验证登记、提交后 outbox 到图投影及 information 域标识。本次沿用持久事件的原类型、字段和含义。P-1 `check_tracked_model_secrets.py` 输出 `tracked_model_secret_offender_count=0`，暂存新增行规则扫描输出 `staged_added_line_credential_pattern_matches=0`。

G5 使用 `docs/verification/absorb-main-3bf3418e/compare_selection.py --repo <B worktree> --selection <选择集> --output <F 盘新目录>`，按冻结五组和本分支全部已登记选集执行。

~~~text
ownership          selected=24  problems=0 improvements=0
modifier           selected=12  problems=0 improvements=0
equipment          selected=87  problems=0 improvements=0
inventory          selected=56  problems=0 improvements=0
shared-replay      selected=990 problems=2 improvements=0
life_state         selected=12  problems=0 improvements=0
reference_data     selected=15  problems=0 improvements=0
siege_information  selected=11  problems=0 improvements=0
~~~

`selection-shared-replay.log` 的两个问题为 `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` 与 `[wall-clock]`。`selection-shared-replay/batch-0010.log` 和从 B 父提交独立快照运行同一文件的日志均出现 `RuntimeError: Port 8000 is occupied by an external process without a healthy backend`。G5 存在这两项环境失败。全量、Godot、正式守城实跑和生产 Gate profile 装载本轮未验证。

| 单元项 | 本轮状态 |
|---|---|
| U1 | Information 注册短名沿用，完整 Owner 声明待补。 |
| U2 | B 包声明 `fact:information:siege:report_knowledge`，采用收件人 private machine。送达触发使用独立的 `fact:information:siege:report`。A 加载器通过，生产读取边界待接。 |
| U3 | 既有事件 P-3 断言已复验，生产 factory 待 A 接。 |
| U4 | Owner 域写入使用已有原子提交和 revision。A 的 Gateway 与 L5 经隔离组合验证，生产接入待 A。 |
| U5 | 精确重派返回原回执，过期、撤销、错误收件人和 revision 拒绝有域测试。Information 独立 durable reopen 与 checkpoint-tail 待做。 |
| U6 | SocialDelivery 是 Information 的上游读取依赖。生产调用方拟为 A 的 M6-5 handler，探针以真实 Gateway 模拟该调用。生产读取者接入后仍需专项核查。 |
| U7 | 隔离验证了私有事件和收件人 outbox audience。生产 read_as 待接。 |
| U8 | 规则包声明 FactType、machine、命令目录和 Reaction。写入由 Python Owner 提供，声明式域 Resolver 待做。 |
| U9 | 实际 A 加载器、Gateway、L5 与 B store/outbox 组合探针已运行。生产报告分类、时钟不可用时恢复、守城实跑待验证。 |
| U10 | 代码提交包含 runtime、域测试、选择集、组合探针及本域规则包。接线与文件归属见 H-B-009。 |
| U11 | B 分支 Information 选择集登记 11 个节点，零差异。 |
