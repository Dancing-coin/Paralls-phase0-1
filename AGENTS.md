# Paralls Runtime Guidance

This repository implements the `world-character-Siming-authority` mainline runtime. The preserved Phase 0 demo is a smoke-compatibility slice, not the architectural target. Start with `docs/INDEX.md`, `docs/harness.md`, and `docs/ai-engineering-workflow.md`; for design decisions, follow `docs/superpowers/specs/world-character-siming-authority-mainline/README.md` and then its master design.

验证入口与证据契约见 `docs/harness.md`。处理清理、陈旧报告或失败诊断时，先读 `docs/harness-playbook.md` 的对应案例；Design、Superpowers、显式 Goal 与 native subagents 的协作边界见 `docs/ai-engineering-workflow.md`。

## Runtime Boundaries

- Godot owns local embodiment, player input, and visible/audio presentation. It is not world-truth authority or the character cognition host.
- The Python backend owns structured protocols, session routing, character service, ESM authority, Siming catalyst, and event traces.
- Cross-boundary input is structured intent. Backend result objects drive object and environment changes; do not fake local success.
- Siming emits high-level catalysts only. Keep animation local and do not introduce remote raw-pose driving.

## Scope And Editing

- Preserve the root Godot project. Keep scenes under `scenes/phase0/`, scripts in `scripts/`, and backend changes in `backend/`.
- Do not expand into full role cognition, full Siming, multi-scene story flow, or Phase 1 architecture cleanup unless explicitly requested.
- Prefer small, targeted edits and existing patterns. Do not copy design documents into code comments.

## Verification

- Backend: run `python -m pytest -v`.
- Broad changes: run `python scripts/verification/harness.py --profile all`.
- For multi-step work, use the Goal ledger and Superpowers workflow described in `docs/ai-engineering-workflow.md`; retain the resulting acceptance evidence under `.harness/verification/`.
- Use native subagents only for independent, bounded lanes; the lead agent remains responsible for integrating their work and verifying the result.
- Godot changes need editor or runtime evidence. Integration claims need a running backend, a real boundary message, and a visible scene result.
- Use Godot MCP when it is available for scene, autoload, and runtime checks. Otherwise report Godot work as static-only or editor-unverified.

### Harness Retention

- 运行产物由 `run_scope` 放入本轮系统临时目录；顶层消费者完成后清理。本轮进程与临时副本也必须回收。
- 必要诊断在清理前通过 `--export-evidence` 显式导出到仓库外；保留期限由调用方管理。
- `.harness/` 只保留可审查的 profiles、rules、模板、夹具、references、evolution 配置、CI 与静态元数据。
- 提交前检查 `git status --short -- .harness` 和目录实际内容；清理仅限本轮拥有的文件、目录和进程，保留用户已有数据。

## Reporting

Separate completed and verified work from static-only work, blockers, and next steps. Do not claim a runtime milestone without its corresponding verification evidence.

## Architecture Documentation Contract

Every new or substantially revised architecture documentation area must include, at the same level or through explicitly linked companion files:

- an architecture diagram showing ownership and module boundaries;
- a sequence diagram showing the principal interaction order;
- a data-flow diagram showing inputs, transformations, outputs, and authority boundaries.

Use Mermaid in Markdown unless a repository-specific diagram format is required. The diagrams must distinguish current implementation, planned work, and deferred work. A design document without all three diagrams is incomplete. Each architecture folder must contain its own `AGENTS.md` when it adds stricter naming, diagram, or implementation-mapping rules; folder rules supplement this file and do not weaken it.

Character additions must preserve existing scene actors and append an independently identified actor by default. Asset package, skeleton profile and motion-library registration are separate from scene actor creation and backend identity binding. Replacement requires an explicit replacement request and named target; asset registration or active-control selection must not implicitly replace an actor. Document implemented admission and discovery behavior separately from planned capabilities.

## Gameplay Tag Guidance

For gameplay and character design, tags are registered, versioned semantic carriers. A tag may describe an object, component, relation, state, event or capability and may participate in a registered effect binding, but it must not directly write resources, effects, inventory, status lifecycle or world truth. Meta-tags describe tag governance such as attachability, lifecycle, visibility, edit policy, merge/conflict policy and authority requirements; they do not create an unbounded second rule engine. Creator editing and in-world character/Siming changes must produce proposals or authority events through the owning domain.

Use `docs/10月分析/战斗系统与角色技能，状态和资源/08-对象标签、编辑与版本治理设计.md` for the proposed object/meta-tag design and its INF references. Reuse the semantic registry, resource/ability runtimes, status lifecycle and effective stats. Keep lifecycle, semantic category, effect binding and activation as separate axes; meta-tag fields never grant new owners or bypass capability/privacy gates. Analysis documents are not implementation authorization.
