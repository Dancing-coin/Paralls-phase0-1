# Chapter Evolution Full Chain Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-only chapter evolution proof mode that auto-generates player choices with DeepSeek and writes complete Chinese-first chain logs.

**Architecture:** Extend `scripts/verification/verify_script_evolution.py` with an explicit chapter mode instead of changing the existing fixture proof path. Reuse the existing backend choice execution pipeline and add richer reporting artifacts around it.

**Tech Stack:** Python 3.13, pytest, existing harness utilities, live DeepSeek via configured `SIMING_LLM_*`.

## Global Constraints

- DeepSeek is required for chapter mode.
- DeepSeek normalizes and proposes choices; backend authority/ESM/Siming decide proof results.
- DeepSeek projects follow-up mainline only from backend-confirmed evidence and never decides proof status.
- Logs are Chinese-first and keep English machine fields.
- Generated verification artifacts remain under `.harness/verification/`.

---

### Task 1: Chapter Mode Contract And Reports

**Files:**
- Modify: `scripts/verification/verify_script_evolution.py`
- Test: `scripts/verification/tests/test_script_evolution_verify.py`

**Interfaces:**
- Produces: `run_proof(..., chapter_mode: bool, auto_choices: bool, full_chain_log: bool) -> dict[str, object]`
- Produces: `normalize_chapter_with_deepseek(script_text: str) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object], list[dict[str, object]]]`
- Produces: `project_mainline_with_deepseek(script_text: str, baseline: dict[str, object], choices_report: list[dict[str, object]]) -> list[dict[str, object]]`

- [x] **Step 1: Write failing tests**

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_chapter_mode_auto_choices_writes_full_chain_logs -q
```

Expected: FAIL because chapter mode flags and artifacts do not exist yet.

- [x] **Step 2: Implement minimal chapter mode**

Add parser flags, DeepSeek-backed chapter normalization, backend-evidence-driven mainline projection, report names, and JSONL writing.

- [x] **Step 3: Run focused tests**

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_chapter_mode_auto_choices_writes_full_chain_logs -q
```

Expected: PASS.

- [x] **Step 4: Run regression tests**

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py -q
```

Expected: PASS.

### Task 2: Live Chapter Proof

**Files:**
- Modify: `scripts/verification/verify_script_evolution.py`
- External input: `C:/Users/38101/Downloads/test.txt`

**Interfaces:**
- Consumes: `--script`, `--chapter-mode`, `--auto-choices`, `--full-chain-log`
- Produces: `.harness/verification/chapter-evolution-full-chain-report.md`

- [x] **Step 1: Run real DeepSeek proof**

```powershell
python scripts/verification/verify_script_evolution.py --script C:/Users/38101/Downloads/test.txt --chapter-mode --auto-choices --full-chain-log
```

Expected: exit code 0 when at least one generated choice produces a Siming-observed or audited mainline impact.

- [x] **Step 2: Inspect logs**

Open the Markdown report and JSONL event stream. Confirm they show input, normalization, candidate choices, backend classification, authority events, ESM results, branch diff, Siming evidence, projected follow-up mainline nodes, and final per-choice status.
