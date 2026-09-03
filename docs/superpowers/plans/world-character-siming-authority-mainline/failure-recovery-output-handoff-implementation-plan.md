# Failure/Recovery/Output Handoff Implementation Plan

Validate explicit package failure policy and fixed event vectors. RED tests
cover release/loss/rework/terminal, missing policy, cross-owner mutation
attempts, custody provenance, duplicate and replay. Gate: Construction writes
evidence only and Inventory independently accepts custody; rollback is binding
disablement.

The failure adapter also rejects a failure tick earlier than the committed run
start tick, preserving deterministic chronology with zero mutation.

The replay projector applies the same chronology check and fails closed on a
pre-start failure event.

The production-output certification event now has an explicit, idempotent
source-controlled schema registration in the existing registry.

The Inventory production-output custody event now has the matching explicit,
idempotent registration in that same registry.
