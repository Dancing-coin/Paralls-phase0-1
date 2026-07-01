# Paralls Phase 0 Demo Workspace

This document now describes a preserved smoke-compatibility runtime surface for Phase 0.
It is not the top-level architectural mission for the repository.

Current mainline truth lives under:
- `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`

This workspace still contains the runnable validation demo for Phase 0.

Directories:
- `godot/`: local client runtime and presentation shell
- `backend/`: Python coordination backend
- `docs/`: demo script and scene setup notes

Current implementation status:
- backend contracts and services: active
- Godot runtime skeleton: scene-load and autotest verified locally

Verification entrypoints:
- `python scripts/verification/verify_phase0.py`
- `python scripts/verification/verify_phase1_slice.py`

Verification artifacts:
- Reports are written to `.harness/verification/`
- `verify_phase0.py` produces both JSON and Markdown audit reports and returns non-zero when strict `Phase 0` goals are not fully proven
- `verify_phase1_slice.py` audits the current `Phase1-shaped` runtime slice around visual facts, authority routing, runtime projection, and Siming consumption
