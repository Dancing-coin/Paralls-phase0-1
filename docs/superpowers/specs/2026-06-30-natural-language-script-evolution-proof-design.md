# Natural Language Script Choice Evolution Proof Design

## Purpose

Design a backend-only proof that verifies whether a natural-language script mainline can legally evolve when a group of natural-language player choices is simulated.

The intended user-facing effect is:

```text
输入一份自然语言剧本作为主线
+ 输入一组玩家操作/选择
-> 模拟每个选择会触发什么事件
-> 生成每个选择对世界的影响
-> 证明哪些选择可以推动主线演化
-> 验证司命是否观察到演化，并在增强验收中证明司命是否提出干预/催化
```

The proof is not a frontend or Godot presentation test. It must show, in console-readable Chinese/English output, that:

- A natural-language script can be normalized into a baseline world model.
- A group of natural-language player choices can be normalized into candidate events.
- Each choice is evaluated as an independent branch from the same baseline.
- Backend authority and ESM produce world impact evidence for each valid branch.
- Siming observes/audits the branch evolution as the first Siming acceptance level.
- Siming may additionally propose an intervention/catalyst/dispatch as an enhanced acceptance level.
- The final report classifies each choice and summarizes whether the mainline is evolvable.

## Confirmed Decisions

- The script input is natural language. It may be Markdown or plain text.
- The script is the mainline baseline, not an event source.
- The player input is a group of natural-language choices, not a single event.
- Each choice is independently evaluated from the same baseline state.
- DeepSeek must be called for real in live proof mode.
- DeepSeek is a normalizer, not the world-truth authority.
- Backend authority chain and ESM decide whether world impact is legal.
- Siming is not the primary judge of legality; it observes, audits, and may assist with intervention/catalyst suggestions.
- The first proof fixture should be a minimal "lamp letter" scenario.
- The proof is backend-only by default and does not depend on frontend or Godot runtime.

## Architecture

The proof has five stages:

```text
Natural-language script
  -> DeepSeek script_normalize
  -> baseline_model

Natural-language choice group
  -> DeepSeek choices_normalize
  -> candidate_events[]

For each candidate_event, independently from baseline_model:
  -> baseline validation
  -> backend authority chain / ESM
  -> world_result / authority events / branch diff

Each branch result
  -> Siming observe/audit path
  -> optional Siming intervention-like output

All branch results
  -> choice classification
  -> mainline evolution summary
```

DeepSeek has two explicit responsibilities:

- `script_normalize`: convert natural-language script text into a minimal baseline model.
- `choices_normalize`: convert a natural-language choice group into ordered candidate events, using the same baseline context for consistent references.

DeepSeek must not directly declare that the world has changed. It may say "choice A looks like `inspect(obj_letter)`"; the backend must decide whether that event is legal, what state changes are produced, and whether Siming observed or intervened.

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
        "interaction_state": "unopened",
        "possession": "desk"
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
    },
    {
      "deviation_id": "player_takes_letter",
      "trigger_family": "player_interaction",
      "target_object_id": "obj_letter",
      "interaction_type": "take",
      "may_change": [
        {
          "path": "objects.obj_letter.possession",
          "from": "desk",
          "to": "char_a"
        }
      ],
      "must_preserve_locked_facts": [
        "fact_letter_exists",
        "fact_char_b_does_not_know_letter_content"
      ]
    }
  ],
  "prior_event_requirements": [
    {
      "requirement_id": "letter_must_be_held_before_handing_to_b",
      "summary": "角色 A 必须先拿起旧信，才能把旧信交给角色 B。",
      "required_state": {
        "objects.obj_letter.possession": "char_a"
      }
    }
  ]
}
```

`allowed_deviations` is not a list of events extracted from the script. It is the interaction space inferred from the baseline. `prior_event_requirements` captures choices that might become legal after another branch state, but are not legal from the current baseline.

## Choice Group Input

The player input is a group of choices. It remains natural language and can be written as plain lines, bullets, or labels.

Example:

```text
A. 玩家拿起旧信仔细查看。
B. 玩家直接离开书房。
C. 玩家把信交给门外的角色 B。
```

`choices_normalize` receives the script text, the baseline model, and the choice group. It produces ordered candidate events:

```json
{
  "choices": [
    {
      "choice_id": "A",
      "source_text": "玩家拿起旧信仔细查看。",
      "event_type": "player_interaction",
      "actor_ref": "char_a",
      "intent_type": "interact_intent",
      "target_ref": "obj_letter",
      "interaction_type": "inspect",
      "confidence": 0.91,
      "evidence": [
        "旧信",
        "仔细查看"
      ],
      "normalization_notes": "该选择表达的是检查旧信。"
    },
    {
      "choice_id": "B",
      "source_text": "玩家直接离开书房。",
      "event_type": "player_navigation",
      "actor_ref": "char_a",
      "intent_type": "move_intent",
      "target_ref": "room_exit",
      "interaction_type": "leave",
      "confidence": 0.86,
      "evidence": [
        "离开书房"
      ],
      "normalization_notes": "该选择可能合法，但不一定影响当前主线关键对象。"
    },
    {
      "choice_id": "C",
      "source_text": "玩家把信交给门外的角色 B。",
      "event_type": "player_interaction",
      "actor_ref": "char_a",
      "intent_type": "interact_intent",
      "target_ref": "obj_letter",
      "secondary_target_ref": "char_b",
      "interaction_type": "handoff",
      "confidence": 0.88,
      "evidence": [
        "把信交给角色 B"
      ],
      "normalization_notes": "该选择需要先满足旧信由角色 A 持有的前置状态。"
    }
  ]
}
```

The backend accepts candidate events only as validation inputs. Candidate events do not mutate state by themselves.

## Independent Branch Semantics

Each choice is evaluated from the same `baseline_model`.

Choice A does not change the input state for choice B or C. This is required because the proof compares possible player choices at the same mainline decision point.

Sequential player operation proofs are a different mode and are out of scope for the first version.

## Backend Validation

For each candidate event, the backend proof validates four layers:

- `normalization schema`: the candidate has stable ids, actor refs, target refs, interaction type, confidence, and evidence.
- `baseline match`: the referenced actor and target object exist in the baseline model.
- `deviation or prior requirement match`: the event either matches one allowed deviation, has no meaningful mainline impact, violates locked facts, or needs a prior state.
- `authority execution`: backend authority chain and ESM produce a concrete world result for valid impact branches.

The authority execution should reuse existing backend concepts where possible:

- Authority event publication for the incoming player interaction.
- ESM interaction resolution or object/environment state result.
- Authority event publication for the resulting world change.
- Audit/read-model evidence when available.

The exact internal event type names should follow existing backend conventions during implementation. The design requirement is evidence of a real backend path, not a synthetic report-only state change.

## Siming Verification

Siming verification is a first-class part of this proof.

The first acceptance level is observation/audit:

```text
SIMING_OBSERVED_EVOLUTION =
  branch has allowed world divergence
  +
  SimingRuntime or SimingEventPipeline consumed the resulting authority event
  +
  Siming produced audit/read-model/debug projection evidence for that branch
```

The enhanced acceptance level is intervention/catalyst proposal:

```text
SIMING_INTERVENTION_PROPOSED =
  SIMING_OBSERVED_EVOLUTION
  +
  Siming produced at least one intervention-like output
```

Intervention-like output includes a Siming output that is recognizably a candidate, decision, dispatch, catalyst, or downstream intervention request. The first version does not require that Siming's proposal produce a second ESM world mutation.

Siming is auxiliary for judgment. It may explain, observe, audit, or propose a catalyst, but legality still comes from baseline validation plus backend authority/ESM execution.

## Mainline Impact Definition

Mainline impact must not be a DeepSeek-only explanation.

```text
MAINLINE_IMPACT_DETECTED =
  allowed world divergence exists
  +
  Siming observed or audited that divergence
```

This means a branch with an ESM state change but no Siming evidence is not enough to satisfy the Siming verification goal. It should be reported as a world divergence with missing Siming observation.

## Choice Classifications

Each choice receives one primary classification:

- `SIMING_INTERVENTION_PROPOSED`: the branch has mainline impact and Siming proposed an intervention/catalyst/dispatch.
- `MAINLINE_IMPACT_DETECTED`: the branch has allowed world divergence and Siming observed/audited it.
- `EVOLVABLE_NO_IMPACT`: the choice is legal but produces no meaningful mainline world divergence.
- `REJECTED_BY_BASELINE`: the choice violates locked facts or allowed deviations.
- `NEEDS_PRIOR_EVENT`: the choice could be legal after a prior branch state, but not from the current baseline.
- `NORMALIZATION_FAILED`: DeepSeek output failed schema validation or could not be mapped to the baseline.

The overall proof should pass when at least one choice reaches `MAINLINE_IMPACT_DETECTED` or `SIMING_INTERVENTION_PROPOSED`, and no infrastructure-required step silently falls back to fake data.

## Rejected Verdicts

Infrastructure and proof-level failures should be explicit:

- `DEEPSEEK_UNAVAILABLE`
- `SCRIPT_NORMALIZE_FAILED`
- `CHOICES_NORMALIZE_FAILED`
- `BASELINE_VALIDATION_FAILED`
- `AUTHORITY_CHAIN_FAILED`
- `SIMING_OBSERVATION_MISSING`
- `LOCKED_FACT_VIOLATED`
- `NO_WORLD_DIVERGENCE`

Choice-level rejection should use the classifications above rather than a generic failure.

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
- allowed_deviations: 2
- prior_event_requirements: 1

[2] Choice group input accepted / 玩家选择组已接收
A. 玩家拿起旧信仔细查看。
B. 玩家直接离开书房。
C. 玩家把信交给门外的角色 B。

[3] DeepSeek choices_normalize PASS
choices: 3

[CHOICE A] 玩家拿起旧信仔细查看。
candidate_event:
- actor: char_a
- target: obj_letter
- interaction: inspect

[CHOICE A] Backend authority + ESM PASS
authority_event published: player.interaction.requested
esm_result produced: object_state_result
authority_event published: world.object_state.changed

[CHOICE A] World divergence PASS
obj_letter.visibility_state:
  baseline: partially_visible
  branch: visible
obj_letter.interaction_state:
  baseline: unopened
  branch: inspected

[CHOICE A] Siming observation PASS
siming audit/read-model evidence observed

[CHOICE A] Result: MAINLINE_IMPACT_DETECTED
该选择可以从主线分叉出合法世界影响，且司命已观察/审计该演化。

[CHOICE B] 玩家直接离开书房。
[CHOICE B] Result: EVOLVABLE_NO_IMPACT
该选择合法，但未对当前主线关键世界状态产生足够影响。

[CHOICE C] 玩家把信交给门外的角色 B。
[CHOICE C] Result: NEEDS_PRIOR_EVENT
该选择需要先满足前置状态：obj_letter.possession == char_a。

[SUMMARY]
mainline_evolvable: true
impact_choices: A
siming_observed_choices: A
siming_intervention_choices: none
```

Enhanced example:

```text
[CHOICE A] Siming intervention PASS
siming_output_type: intervention_candidate
selected_path: visual_fact_path
intervention_band: fact_reveal

[CHOICE A] Result: SIMING_INTERVENTION_PROPOSED
该选择不只产生主线影响，司命还提出了可下游消费的干预/催化输出。
```

## Files And Execution Shape

The proposed implementation should add a standalone backend-only proof surface:

```text
.harness/profiles/script-evolution-proof.json
.harness/fixtures/script-evolution/demo-script.md
.harness/fixtures/script-evolution/demo-choices.txt
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
  --choices .harness/fixtures/script-evolution/demo-choices.txt `
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
- Choice input path and content digest.
- DeepSeek live-mode metadata without leaking secrets.
- `script_normalize` request/response summary.
- `choices_normalize` request/response summary.
- Baseline model.
- Ordered candidate events.
- Per-choice validation checks.
- Per-choice authority events observed.
- Per-choice ESM/world result observed.
- Per-choice baseline versus branch diff.
- Per-choice locked facts preservation result.
- Per-choice Siming audit/read-model/debug evidence.
- Per-choice Siming intervention-like output evidence when present.
- Per-choice classification.
- Overall mainline evolution summary.

The report must not include API keys or full sensitive environment values.

## Scope Limits

The first implementation should not attempt a general-purpose interactive fiction engine.

In scope:

- One natural-language script fixture.
- One natural-language choice group fixture.
- One live DeepSeek script normalization path.
- One live DeepSeek choices normalization path.
- Independent branch validation for each choice.
- One backend authority/ESM world impact path.
- Siming observation/audit as required acceptance for mainline impact.
- Siming intervention/catalyst as enhanced acceptance when available.
- At least one impact choice, one no-impact choice, and one needs-prior-event or rejected choice.

Out of scope:

- Frontend/Godot verification.
- Multi-scene story flow.
- Sequential choice execution.
- Full Siming brain behavior.
- Automatic story authoring.
- Letting DeepSeek directly decide final world truth.
- Letting Siming replace baseline/ESM legality checks.
- Parsing the script as a chronological event log.

## Testing Strategy

Implementation should be test-first:

- Unit-test baseline model validation.
- Unit-test choice group schema validation.
- Unit-test candidate event validation.
- Unit-test locked fact preservation.
- Unit-test `NEEDS_PRIOR_EVENT` classification.
- Unit-test no-impact classification.
- Unit-test report verdict mapping.
- Integration-test deterministic backend authority and ESM branch execution without live DeepSeek.
- Integration-test Siming observation/audit evidence over a produced branch event.
- Provide a live DeepSeek proof mode for manual or harness-gated execution.

The live DeepSeek path should fail clearly if credentials or network access are unavailable, using `DEEPSEEK_UNAVAILABLE` rather than silently falling back to fake data.

## Chosen Implementation Seam

The first implementation should use the existing backend internal seam directly:

- Instantiate `InMemoryAuthorityEventBus` for local proof capture.
- Convert each normalized candidate choice into the existing `InteractIntent` shape when it maps to player interaction.
- Publish an incoming authority event for the player interaction.
- Call `ESMService.resolve_interaction()` with an in-range interaction for valid interaction branches.
- Call `ESMService.emit_object_state_result()` for each allowed object-state transition produced by the matched deviation.
- Publish resulting authority events for the applied world changes.
- Feed the resulting authority event into the existing Siming runtime or pipeline path.
- Capture Siming audit/read-model/debug evidence for observation acceptance.
- Capture Siming intervention-like output if produced.
- Read back bus events, ESM results, and Siming evidence into the proof report.

The first version should not require starting the full FastAPI app. A later app-wiring proof can be added if this proof needs to demonstrate entrypoint composition, but the initial goal is backend internal main-chain evidence without frontend or Godot dependencies.
