# Paralls Phase 0 Demo Workspace

This workspace contains the runnable validation demo for Phase 0.

Directories:
- `godot/`: local client runtime and presentation shell
- `backend/`: Python coordination backend
- `docs/`: demo script and scene setup notes

Current implementation status:
- backend contracts and services: active
- Godot runtime skeleton: scene-load and autotest verified locally

Startup entrypoints:
- Backend only: `python -m app` from `backend/` or `paralls-phase0-backend`
- Full local slice: `powershell -ExecutionPolicy Bypass -File scripts/start_phase0.ps1`
- Godot main scene: `res://scenes/phase0/MainDemo.tscn`
- The launcher expects `GODOT_EXE` to point at a local Godot 4 executable; `PYTHON_EXE` can override the backend Python interpreter

Verification entrypoints:
- `python scripts/verification/verify_phase0.py`
- `python scripts/verification/verify_phase1_slice.py`

Verification artifacts:
- Reports are written to `.harness/verification/`
- `verify_phase0.py` produces both JSON and Markdown audit reports and returns non-zero when strict `Phase 0` goals are not fully proven
- `verify_phase1_slice.py` audits the current `Phase1-shaped` runtime slice around visual facts, authority routing, runtime projection, and Siming consumption
