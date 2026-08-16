# INF-1C Closed Guard Composition Design

Status: `implemented and verified for finite proposal-only guard composition; August INF-1 lifecycle closure remains incomplete`

## Scope

This package extends only the existing pure `SemanticRegistry` evaluator. A
`MetaRuleDefinition.guard_expression` may now use a single, non-nested
`all(...)` or `any(...)` group whose terms are existing closed atomic guards:
`tag:`, `status:`, `parameter_gte:`, `parameter_lte:`, `parameter_eq:`, and
the existing boolean constants. Evaluation reads a frozen `SemanticSnapshot`
and returns the existing trace/proposal digest surface.

There is no owner mapping, command envelope, settlement plan, event append,
outbox, replay mutation, or domain projection write in this package. MetaRule
evaluation remains proposal-only.

## Admission and rejection

Nested groups, empty terms, unknown atomic forms, free expressions, imports,
function calls, and script execution reject at model validation with
`semantic_guard_expression_unsupported`. The finite parser does not evaluate
Python, expressions, callbacks, or caller-supplied handlers.

## Evidence

`infra-semantic-closed-guard-composition` runs four independent tests for
successful `all`, false `all`, successful `any`, and malformed/script rejection.
The report is
`.harness/verification/infra-semantic-closed-guard-composition-report.json`.

## Remaining INF-1 work

This does not add a generic effect/state owner. The durable owner rows remain
the two closed Survival mappings, `authority:semantic -> effect:cold_exposure
-> state:cold@1 -> SurvivalAuthority` and `authority:semantic ->
effect:heat_exposure -> state:overheated@1 -> SurvivalAuthority`. Generic
StateDefinition coverage, additional owner rows, and all effect expiry paths
outside those rows remain incomplete.
