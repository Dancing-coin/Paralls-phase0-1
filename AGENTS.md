# Paralls Runtime Guidance

This repository implements the `world-character-Siming-authority` mainline runtime. The preserved Phase 0 demo is a smoke-compatibility slice, not the architectural target. Start with `docs/INDEX.md`; for design decisions, follow `docs/superpowers/specs/world-character-siming-authority-mainline/README.md` and then its master design.

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

- Harness verification output is temporary evidence. Delete `.harness/verification/` after the verification run; do not commit its reports, logs, traces, databases, screenshots, or caches.
- Delete temporary `.harness/` run directories after each run. This includes random-ID directories, snapshots, archives, copied worktrees, generated assets, `__pycache__`, SQLite files, logs, and other runtime state.
- Keep only reviewable static harness inputs: profiles, rules, templates, fixtures, references, evolution configuration, CI configuration, and checked-in harness metadata.
- Before committing, inspect `git status --short -- .harness` and confirm no generated verification output or run directory remains.

## Reporting

Separate completed and verified work from static-only work, blockers, and next steps. Do not claim a runtime milestone without its corresponding verification evidence.
