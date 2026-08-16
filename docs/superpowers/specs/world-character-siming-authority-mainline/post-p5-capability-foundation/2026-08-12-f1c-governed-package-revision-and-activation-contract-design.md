# F1C Governed Package Revision And Activation Contract

Status: `implemented-and-verified; complete profile fresh-green`

## Objective

Define the shared package governance required by P6 creator operations: an
immutable manifest, capability allowlist, revision lifecycle, approval,
activation, rollback, audit, and closed-core boundary.

## Contract shape

Packages are digest-addressed revisions with declared schemas, dependencies,
capabilities, data migrations, rollback policy, and owner. Lifecycle is
`draft -> preview -> staging -> active`, with explicit `rejected`, `withdrawn`,
and `rolled-back` transitions. Activation is a signed proposal evaluated by
the closed core and committed through existing Gameplay authority; UI, CLI and
MCP share one authorization decision contract.

## Work packages

1. manifest, digest, schema and capability fields;
2. reader/editor/admin permission matrix and denial parity;
3. preview/staging/active/rollback state machine;
4. audit event and approval evidence;
5. migration compatibility, rollback and replay fixtures.

## Dependencies

F0 identifies package gaps. F1A supplies semantic dependency/revision rules and
F1B supplies visibility/projection scopes. F1C is the hard prerequisite for
P6C/P6D; P6A/P6B may only prepare adapters before F1C is green.

## Evidence gate

Tests cover signature/digest validation, capability denial, UI/CLI/MCP parity,
stale activation denial, atomic activation/rollback, audit completeness,
full/checkpoint-tail replay, migration failure, and zero writes on every
rejected request. Evidence must name closed-core owner and rollback target.

## Non-goals and stop conditions

No direct database writer, raw event ingress, secret/core algorithm exposure,
arbitrary executable plugin, public marketplace, billing platform, or production
deployment automation. Missing approval/audit/rollback evidence keeps F1C
`planned` or `blocked` and blocks P6C/P6D.
