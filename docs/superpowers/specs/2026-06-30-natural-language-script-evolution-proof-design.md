# Natural Language Script Evolution Proof Design

## Purpose

Design a backend-only proof that verifies whether a natural-language player event can legally evolve a world from a natural-language script baseline.

The proof is not a frontend or Godot presentation test. It must show, in console-readable Chinese/English output, that:

- A natural-language script can be normalized into a baseline world model.
- A natural-language player input can be normalized into an external event candidate.
- The event candidate is checked against the baseline and allowed deviations.
- Backend authority and ESM produce the world evolution artifact.
- Locked facts remain preserved.
- The final branch is either `PROVED_EVOLVABLE` or rejected with a specific reason.

## Confirmed Decisions

- The script input is natural language. It may be Markdown or plain text.
- The script is the mainline baseline, not an event source.
- The player event input is also natural language.
- DeepSeek must be called for real in live proof mode.
- DeepSeek is a normalizer, not the world-truth authority.
- Backend authority chain and ESM decide whether evolution is legal.
- The first proof fixture should be a minimal "lamp letter" scenario.
- The proof is backend-only by default and does not depend on frontend or Godot runtime.

## Architecture

The proof has four stages:

```text
Natural-language script
  -> DeepSeek script_normalize
  -> baseline_model

Natural-language player event
  -> DeepSeek event_normalize
  -> candidate_event

baseline_model + candidate_event
  -> baseline validation
  -> backend authority chain / ESM
  -> world_result / authority events

world_result + baseline_model
  -> divergence check
  -> locked fact check
  -> final verdict
```

DeepSeek has two explicit responsibilities:

- `script_normalize`: convert natural-language script text into a minimal baseline model.
- `event_normalize`: convert natural-language player text into a candidate external event.

DeepSeek must not directly declare that the world has changed. It may say "this text looks like `inspect(obj_letter)`"; the backend must decide whether that event is legal and what state changes are produced.

## Script Input

The script input should remain readable prose. It may use Markdown headings for readability, but no YAML or JSON is required from the user.

Example:

```markdown
# 灯下信件

深夜，书房里只有一盏台灯亮着。桌上放着一封旧信，信封泛黄，半压在一本黑色笔记本下。

角色 A 站在书桌旁，已经注意到桌上有一封信，但还没有打开。角色 B 在门外，并不知道信里的内容。

当前主线中，角色 A 只是看见了旧信，尚未检查、打开或带走它。
```

## Baseline Model

`script_normalize` produces the minimum model needed for proof:

```json
{
  "script_id": "lamp_letter",
  "mainline_summary": "深夜书房中，角色 A 注意到桌上的旧信，但尚未打开或检查。",
  "actors": [
    {
      "actor_id": "char_a",
      "summary": "站在书桌旁，知道旧信存在。"
    },
    {
      "actor_id": "char_b",
      "summary": "在门外，不知道信件内容。"
    }
  ],
  "objects": [
    {
      "object_id": "obj_letter",
      "summary": "桌上的旧信，半压在黑色笔记本下。",
      "state": {
        "location": "desk",
        "visibility_state": "partially_visible",
        "interaction_state": "unopened"
      }
    }
  ],
  "locked_facts": [
    {
      "fact_id": "fact_letter_exists",
      "summary": "桌上存在一封旧信。"
    },
    {
      "fact_id": "fact_char_b_does_not_know_letter_content",
      "summary": "角色 B 尚不知道信件内容。"
    }
  ],
  "allowed_deviations": [
    {
      "deviation_id": "player_inspects_letter",
      "trigger_family": "player_interaction",
      "target_object_id": "obj_letter",
      "interaction_type": "inspect",
      "may_change": [
        {
          "path": "objects.obj_letter.visibility_state",
          "from": "partially_visible",
          "to": "visible"
        },
        {
          "path": "objects.obj_letter.interaction_state",
          "from": "unopened",
          "to": "inspected"
        }
      ],
      "must_preserve_locked_facts": [
        "fact_letter_exists",
        "fact_char_b_does_not_know_letter_content"
      ]
    }
  ]
}
```

`allowed_deviations` is not a list of events extracted from the script. It is the interaction space inferred from the baseline. For example, if the letter is visible and unopened, inspecting the letter is a valid possible deviation. Making character B suddenly know the contents violates a locked fact unless another legal event first exposes that information.

## Player Event Input

The player event input is natural language.

Example:

```text
玩家靠近书桌，发现灯下那封旧信，于是伸手拿起来仔细看。
```

`event_normalize` produces a candidate event:

```json
{
  "event_type": "player_interaction",
  "source_text": "玩家靠近书桌，发现灯下那封旧信，于是伸手拿起来仔细看。",
  "actor_ref": "char_a",
  "intent_type": "interact_intent",
  "target_ref": "obj_letter",
  "interaction_type": "inspect",
  "confidence": 0.91,
  "evidence": [
    "玩家发现旧信",
    "拿起来仔细看"
  ],
  "normalization_notes": "该输入表达的是对旧信的检查行为，不是打开或带走。"
}
```

The backend accepts this candidate event only as an input to validation. The event candidate does not itself mutate state.

## Backend Validation

The backend proof validates the candidate event in three layers:

- `baseline match`: the referenced actor and target object exist in the baseline model.
- `deviation match`: the event matches one allowed deviation from the baseline.
- `authority execution`: backend authority chain and ESM produce a concrete world result.

The authority execution should reuse existing backend concepts where possible:

- Authority event publication for the incoming player interaction.
- ESM interaction resolution or object/environment state result.
- Authority event publication for the resulting world change.
- Audit/read-model evidence when available.

The exact internal event type names should follow existing backend conventions during implementation. The design requirement is evidence of a real backend path, not a synthetic report-only state change.

## Verdicts

The successful verdict is:

```text
PROVED_EVOLVABLE
```

This means:

- DeepSeek script normalization succeeded.
- DeepSeek event normalization succeeded.
- Candidate event matched the baseline model.
- Candidate event matched an allowed deviation.
- Backend authority chain accepted and processed it.
- A world result or state change was produced.
- Baseline and branch differ in an allowed way.
- Locked facts remain preserved.

Rejected verdicts should be explicit:

- `DEEPSEEK_UNAVAILABLE`
- `SCRIPT_NORMALIZE_FAILED`
- `EVENT_NORMALIZE_FAILED`
- `BASELINE_VALIDATION_FAILED`
- `AUTHORITY_CHAIN_FAILED`
- `LOCKED_FACT_VIOLATED`
- `NO_WORLD_DIVERGENCE`

## Console Report

The console output should be bilingual or Chinese-first, and readable without opening the JSON report.

Successful example:

```text
[0] Script input accepted / 剧本输入已接收

[1] DeepSeek script_normalize PASS
baseline_model:
- actors: 2
- objects: 1
- locked_facts: 2
- allowed_deviations: 1

[2] Player event input accepted / 玩家事件输入已接收
玩家靠近书桌，发现灯下那封旧信，于是伸手拿起来仔细看。

[3] DeepSeek event_normalize PASS
candidate_event:
- actor: char_a
- target: obj_letter
- interaction: inspect

[4] Baseline validation PASS
target exists: obj_letter
actor exists: char_a
allowed deviation: player_inspects_letter

[5] Backend authority chain PASS
authority_event published: player.interaction.requested
esm_result produced: object_state_result
authority_event published: world.object_state.changed

[6] World divergence PASS
obj_letter.visibility_state:
  baseline: partially_visible
  branch: visible

obj_letter.interaction_state:
  baseline: unopened
  branch: inspected

[7] Locked facts preserved PASS
fact_letter_exists: preserved
fact_char_b_does_not_know_letter_content: preserved

[RESULT] PROVED_EVOLVABLE
该玩家行为可以从主线基线分叉出一个合法世界状态，后续可继续演化。
```

Rejected example:

```text
[INPUT] 玩家输入
角色 B 忽然知道了信里的秘密。

[LLM] DeepSeek event_normalize PASS
actor=char_b interaction=know_secret target=obj_letter

[CHECK] Locked fact violation / 锁定事实被破坏
fact_char_b_does_not_know_letter_content would be broken.

[RESULT] LOCKED_FACT_VIOLATED
该事件不能作为合法演化继续，因为它破坏了剧本锁定事实。
```

## Files And Execution Shape

The proposed implementation should add a standalone backend-only proof surface:

```text
.harness/profiles/script-evolution-proof.json
.harness/fixtures/script-evolution/demo-script.md
.harness/fixtures/script-evolution/demo-event.txt
scripts/verification/verify_script_evolution.py
scripts/verification/tests/test_script_evolution_verify.py
```

Generated evidence should be written under:

```text
.harness/verification/script-evolution-proof-report.json
.harness/verification/script-evolution-proof-report.md
```

Suggested direct command:

```powershell
python scripts/verification/verify_script_evolution.py `
  --script .harness/fixtures/script-evolution/demo-script.md `
  --event .harness/fixtures/script-evolution/demo-event.txt `
  --live-deepseek
```

Suggested harness command:

```powershell
python scripts/verification/harness.py --profile script-evolution-proof
```

If the harness profile is added, `docs/harness.md` must be updated in the same implementation change so docs freshness checks know about the profile.

## Report Artifacts

The JSON and Markdown reports should include:

- Script input path and content digest.
- Player event input path and content digest.
- DeepSeek live-mode metadata without leaking secrets.
- `script_normalize` request/response summary.
- `event_normalize` request/response summary.
- Baseline model.
- Candidate event.
- Validation checks and results.
- Authority events observed.
- ESM/world result observed.
- Baseline versus branch diff.
- Locked facts preservation result.
- Final verdict.

The report must not include API keys or full sensitive environment values.

## Scope Limits

The first implementation should not attempt a general-purpose interactive fiction engine.

In scope:

- One natural-language script fixture.
- One natural-language player event fixture.
- One live DeepSeek normalization path.
- One backend authority/ESM evolution path.
- One positive proof and at least one deterministic rejection test.

Out of scope:

- Frontend/Godot verification.
- Multi-scene story flow.
- Full Siming brain behavior.
- Automatic story authoring.
- Letting DeepSeek directly decide final world truth.
- Parsing the script as a chronological event log.

## Testing Strategy

Implementation should be test-first:

- Unit-test baseline model validation.
- Unit-test candidate event validation.
- Unit-test locked fact preservation.
- Unit-test report verdict mapping.
- Integration-test the deterministic backend authority path without live DeepSeek.
- Provide a live DeepSeek proof mode for manual or harness-gated execution.

The live DeepSeek path should fail clearly if credentials or network access are unavailable, using `DEEPSEEK_UNAVAILABLE` rather than silently falling back to fake data.

## Chosen Implementation Seam

The first implementation should use the existing backend internal seam directly:

- Instantiate `InMemoryAuthorityEventBus` for local proof capture.
- Convert the normalized event candidate into the existing `InteractIntent` shape.
- Publish an incoming authority event for the player interaction.
- Call `ESMService.resolve_interaction()` with an in-range interaction.
- Call `ESMService.emit_object_state_result()` for each allowed object-state transition produced by the matched deviation.
- Publish resulting authority events for the applied world changes.
- Read back bus events and ESM results into the proof report.

The first version should not require starting the full FastAPI app. A later app-wiring proof can be added if this proof needs to demonstrate entrypoint composition, but the initial goal is backend internal main-chain evidence without frontend or Godot dependencies.
