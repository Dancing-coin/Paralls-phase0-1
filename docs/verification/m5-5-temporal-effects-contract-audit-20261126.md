# M5-5 Temporal Effects Contract Audit

## Sources checked

The read-only formal Architecture v2 documents were checked in the external documentation repository:

- `docs/architecture-v2/03-事实类型/04-FactType完整schema.md`
- `docs/architecture-v2/02-原语/02-六原语规格.md`
- `docs/architecture-v2/05-规则包/04-规则包文件格式.md`
- `docs/architecture-v2/10-待决/01-待决清单.md`

## What is specified

The FactType schema defines `temporal_effect` as a `process` subtype with:

```text
primitive: process
process_kind: temporal
```

The six-primitive specification adds the temporal-process fields `tick_policy`, `next_tick`, and `exit_condition`. It states that a tick may only request settlement from a Pool Owner and that the idempotency key is `process_id + scheduled_world_tick`.

## What is missing

The rule-pack format only lists the `temporal_effects/` directory and example manifest entries `bleeding` and `burning`. It does not define:

- the YAML entry fields and their types;
- the reference namespace for tick policy, exit condition, target Pool, or model;
- validity and cross-field rules;
- temporal-effect-specific rejection codes;
- the production consumer that schedules or settles the entries;
- package-version and persistence boundaries for effect instances.

The code and pack search at the A tip found no temporal-effect entries, loader section, runtime consumer, or tests. Existing status/economy/ecology temporal consumers implement other owner contracts and do not establish this package category's schema.

## Decision

M5-5 `temporal_effects` remains **blocked on a formal input contract**. Implementing it now would invent persisted package semantics and a consumer boundary. No code, Owner, FactType, event schema, or package content was added for this category.

## Verification level

Static-only audit. No runtime or pytest command was required because the missing contract is the blocking fact.
