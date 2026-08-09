# Phase One Gameplay Implementation Plan Tree

## Backfill Status (2026-08-09)

本次回填基于本轮 focused tests 和 Harness fresh reports，不根据工作树里已有的代码文件
存在与否推断完成。当前状态是“前置 contract/domain gates 已验证，P1D/P1E 仍有明确收口项”，
因此不能把第一阶段整体标成完成。

| Plan | Current status | Evidence / remaining work |
| --- | --- | --- |
| P1A shared contract closure | `implemented-and-verified` | `gameplay-foundation-contract` and `gameplay-foundation-all` fresh reports |
| P1B contract evidence | `implemented-and-verified` | G1-G8 全部通过：`phase1b-contract-verification-report.json` |
| P1C Frost Farm | `implemented-and-verified` | `phase1c-frost-farm-report.json` |
| Econ-1 Construction/Production | `implemented-and-verified` | `econ1-construction-production-report.json`；facility acquisition、maintenance obligation、run/output 与 reservation 断言 fresh-green |
| Econ-1 Survival | `implemented-and-verified` | `econ1-survival-profile-report.json` |
| Econ-1 Economy | `implemented-and-verified` | `econ1-economy-period-settlement-report.json`；固定报价，不是动态市场 |
| Econ-1 Organization/Government | `implemented-and-verified` | `econ1-organization-government-report.json` |
| P1D Bakery | `implemented-and-verified` | 三期经营、facility acquisition、原料/产出/销售 reservation、full/checkpoint-tail replay、profile-backed employee、失败/恢复矩阵与 Godot committed mirror fresh-green |
| P1E Generalization | `implemented-and-verified` | Ownership title + account + DebtAuthority 样板通过 profile-backed CharacterRecord、checkpoint-tail、scope-filtered replay、stale/duplicate/permission/custody/term zero-write evidence |

本轮验证结果：`python -m pytest -q` 为 `2314 passed`；`gameplay-foundation-all`、P1D（含
Godot headless mirror）、P1E 与 `docs` Harness profiles fresh-green。完整
`python scripts/verification/harness.py --profile all`
曾在 604 秒命令上限内未完成，因此不把它作为整体完成证据。

### This Backfill Does Not Authorize

- 不新增第二个 runtime、event store、authority bus 或全局 scheduler；
- 不把聚合顾客需求、供应商 quote 或 competitor profile 物化成 NPC canonical state；
- 不把 `approved` spec 提前改成 `implemented-and-verified`；
- 不把动态市场、Population Simulation 或 Creator Control Plane 纳入第一阶段实现。

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to execute one approved plan task at a time.

**Goal:** 将已批准的第一阶段 Gameplay specs 转换为依赖有序、可验证、不会创建平行 runtime 的实施计划。

**Architecture:** P1A 扩展现有 Gameplay Foundation owner；P1B 先补 Harness/evidence；P1C 用霜冻农田验证 effect/resistance；P1D 再组合 Econ-1 面包店及四个子域；P1E 最后用一个结构不同的 debt/contract/ownership 样板验证泛化。所有写入继续落到现有 authority 与 `GameplayEventStore.append_batch()`。

**Tech Stack:** Python backend, Pydantic strict models, existing Gameplay authorities, pytest, Harness profiles, JSON/MD/NDJSON evidence under `.harness/verification/`。

---

执行入口：[第一阶段 Gameplay 计划执行提示词](2026-08-07-phase-one-gameplay-execution-prompt.md)。

## Plan Order

1. [Gameplay Foundation Shared Contract Closure](2026-08-07-gameplay-foundation-shared-contract-closure-implementation-plan.md) (P1A)
2. [P1B Contract Verification And Evidence](2026-08-07-p1b-contract-verification-and-evidence-implementation-plan.md)
3. [P1C Frost Farm Contract Sample](2026-08-07-p1c-frost-farm-contract-sample-implementation-plan.md)
4. [P1D Econ-1 Bakery Reference Game](2026-08-07-p1d-econ1-bakery-reference-game-implementation-plan.md)
5. [Econ-1 Construction And Production](econ1/2026-08-07-econ1-construction-production-implementation-plan.md)
6. [Econ-1 Survival Profile](econ1/2026-08-07-econ1-survival-profile-implementation-plan.md)
7. [Econ-1 Economy And Business Period Settlement](econ1/2026-08-07-econ1-economy-period-settlement-implementation-plan.md)
8. [Econ-1 Organization And Government](econ1/2026-08-07-econ1-organization-government-implementation-plan.md)
9. [P1E Generalization Gate](2026-08-07-p1e-generalization-gate-implementation-plan.md)

## Execution Gates

- P1A plan tasks may begin after the P1A spec approval recorded on 2026-08-07.
- P1B starts only after P1A focused contract tests are green.
- P1C starts only after P1B evidence profiles are green.
- P1D and its four Econ-1 subplans share the P1B/P1C prerequisites; domain subplans must
  land before the P1D vertical closure profile.
- P1E starts only after three replayable bakery periods and all P1D predecessor profiles pass.

No plan authorizes Population Simulation, dynamic markets, Creator Control Plane product APIs,
arbitrary package code, a second event store, a second scheduler, or direct imports of internal
dossier/authority functions.
