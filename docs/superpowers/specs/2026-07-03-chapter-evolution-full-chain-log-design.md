# Chapter Evolution Full Chain Log Design

## Goal

Allow a full natural-language chapter to be used as the script mainline, ask DeepSeek to generate a small set of player-like choices, and produce a backend-only proof log that shows every meaningful chain step from input to final Siming-observed evolution judgment.

## Scope

- Input is a natural-language chapter file such as `C:/Users/38101/Downloads/test.txt`.
- DeepSeek is required in chapter mode. Fixture fallback is not allowed because arbitrary chapters do not share the fixed demo schema.
- DeepSeek may normalize the chapter and generate candidate player choices, but it must not be the final evolution judge.
- DeepSeek may project the next mainline only after backend authority/ESM/Siming evidence exists; that projection is explanatory, not proof authority.
- Backend authority, ESM branch execution, and Siming observation remain the proof boundary.
- Output must be Chinese-first with English machine fields preserved.

## Design

Add a `--chapter-mode --auto-choices --full-chain-log` path to `scripts/verification/verify_script_evolution.py`.

The chapter path will:

1. Read the natural-language chapter.
2. Call DeepSeek to normalize it into the existing backend proof shape: `actors`, `objects`, `locked_facts`, `allowed_deviations`, and `prior_event_requirements`.
3. Call DeepSeek to generate exactly three player-like candidate choices against that baseline.
4. Execute each choice independently through the existing backend branch pipeline.
5. Call DeepSeek again with only confirmed backend evidence (`branch_diff`, authority event types, ESM result types, and Siming evidence) to explain how each impacted choice changes the next mainline.
6. Record a full chain trace in the JSON report and JSONL event stream.
7. Render a Chinese-first Markdown report that separates total proof status, per-choice execution status, and follow-up mainline projection.
8. Print a Chinese-first console proof summary with per-choice Branch Diff and follow-up mainline projection, so manual runs do not require opening the Markdown file first.

Each projected mainline entry must include:

- impacted mainline node
- original mainline direction
- evolved mainline direction
- 3 to 5 follow-up plot nodes
- locked facts that still constrain the branch
- whether the branch remains evolvable

## Artifacts

- `.harness/verification/chapter-evolution-full-chain-report.json`
- `.harness/verification/chapter-evolution-full-chain-report.md`
- `.harness/verification/chapter-evolution-events.jsonl`
- console stdout with Branch Diff and `mainline_projection`

## Non-Goals

- No Godot/frontend execution.
- No production story engine.
- No claim that DeepSeek output is canonical world truth.
- No automatic mutation of the chapter text itself.
