# Paralls Runtime Guidance

This repository implements the `world-character-Siming-authority` mainline runtime. The preserved Phase 0 demo is a smoke-compatibility slice, not the architectural target. Start with `docs/INDEX.md`; for design decisions, follow `docs/superpowers/specs/world-character-siming-authority-mainline/README.md` and then its master design.

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
- Godot changes need editor or runtime evidence. Integration claims need a running backend, a real boundary message, and a visible scene result.
- Use Godot MCP when it is available for scene, autoload, and runtime checks. Otherwise report Godot work as static-only or editor-unverified.

### Harness Retention

- 运行产物由 `run_scope` 放入本轮系统临时目录；顶层消费者完成后清理。本轮进程与临时副本也必须回收。
- 必要诊断在清理前通过 `--export-evidence` 显式导出到仓库外；保留期限由调用方管理。
- `.harness/` 只保留可审查的 profiles、rules、模板、夹具、references、evolution 配置、CI 与静态元数据。
- 提交前检查 `git status --short -- .harness` 和目录实际内容；清理仅限本轮拥有的文件、目录和进程，保留用户已有数据。

## Reporting

Separate completed and verified work from static-only work, blockers, and next steps. Do not claim a runtime milestone without its corresponding verification evidence.
