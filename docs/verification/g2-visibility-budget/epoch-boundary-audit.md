# G2 authority epoch boundary audit

Status: investigation only. No authority epoch fencing is implemented here.

The architecture specification keys an authority generation and canonical
writer by `(stream, scope)`. The handoff sequence requires freezing the old
writer, draining work, retaining confirmed events and unresolved commands,
obligations and cursors, resolving or preserving unknown outcomes, then
advancing the generation and recovering the new writer. A method that accepts
only a new writer and increments a counter would not prove that sequence.

The two storage implementations have different concurrency boundaries:

- `GameplayEventStore.append_batch` holds its in-process `RLock` through
  preparation and installation.
- `DurableGameplayEventStore.append_batch` performs preparation and writes
  inside SQLite's `BEGIN IMMEDIATE` transaction. Separate instances can open
  the same database, so a per-instance in-memory epoch map cannot fence them.
- `_prepare_append` handles an existing idempotency record before revision
  checks. A previously committed exact retry must recover its original receipt
  after handoff without creating a new event; a new write under the old epoch
  must fail. Reusing the key with a changed digest must still fail.
- Snapshots serialize complete batches and verify ledger events, transaction
  results and idempotency records against one another. The SQLite snapshot
  export and JSON-to-SQLite migration also reconstruct these records.

On Python 3.12.2 with the G0 environment, the real `_batch()` fixture from
`test_gameplay_event_store_contract.py` was validated as `AtomicEventBatch`.
A temporary Pydantic subclass with an optional `authority_epoch` defaulting to
`None` added that key to `model_dump(mode="json")`, changing the SHA-256 of
`json.dumps(..., sort_keys=True)` from
`6092c9cd87721f57a524e31bc4227c1de3368dac8284a7f632634f4c4a0aac4f` to
`aaca180814d524a7492d9e785d19f6057490544c30baa6dade764fa48c148c05`.
This is an illustrative serialization check, not a historical frozen hash or
proof that every domain hashes this exact object. It shows why an additive
model field still needs an explicit compatibility and snapshot migration plan.

Implementation acceptance must exercise the actual authorized handoff and
commit boundary, not a test-only registry:

1. Reject missing or mismatched `(stream, scope, epoch, writer)` for protected
   writes, including a multi-stream batch and a different writer at the same
   epoch; preserve revision and principal checks.
2. Serialize handoff and append across two durable store instances, then
   reopen and restore/export snapshots. A stale writer must never commit after
   handoff, including when a process loses its response or restarts.
3. Preserve exact receipt lookup and replay after handoff; reject changed
   payload under the same key and never create a second event or side effect.
4. Demonstrate the authoritative freeze/drain/recovery evidence rather than
   letting callers self-assert handoff completion. Preserve unresolved results.
5. Verify legacy snapshots, stored event hashes and pre-existing replay paths
   without rewriting historical frozen hashes or silently assigning epochs.

The visibility benchmark remains synthetic; its inconsistent tail results do
not validate this separate commit path or close D6. No decision D2-D10 is
closed by this investigation.

## Existing durable serialization regression

`test_independent_durable_writers_serialize_revision_and_preserve_retry`
starts two distinct durable stores against one SQLite file and races batches
with the same expected stream revision. One commits and one gets a revision
conflict. After both stores close, a reopened store returns the original
receipt for an exact retry, rejects a changed digest and has one event,
transaction and outbox entry. This validates the existing revision and
idempotency substrate, not authority epoch enforcement or handoff.

On Windows 11 with the G0 Python 3.12.2 environment, the following command
reported 47 passed and 2 deprecation warnings:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_gameplay_event_store_persistence.py backend/tests/test_gameplay_event_store_contract.py backend/tests/test_gameplay_event_store_connection.py -q
```

## Migration Constraints

The existing `DriverArbitrator` grants in-process, window-scoped advancement
claims and explicitly grants no settlement rights. It is not a persisted
writer registry and cannot authorize EventStore commits. The connection and
runtime-process generations likewise do not identify a canonical writer for
each `(stream, scope)`.

The EventStore currently accepts snapshot schemas 1 and 2, and SQLite schema
3. A protected archive needs a new schema version that older readers reject:
adding optional keys to schema 2 risks an old reader silently discarding the
fence. SQLite migration also has to account for an old process that opened the
database before the schema version changed. Checking the version only at
startup cannot stop that process from appending afterwards. A rollout must
either establish and verify an exclusive quiescence boundary before enabling
protection, or enforce the fence in a database boundary that old connections
cannot bypass. Merely upgrading the open-time schema check is insufficient.

An implementation unit must include all of these observable cases:

| Boundary | Required observation |
|---|---|
| First protection | Existing history and receipt digests stay unchanged; protected streams cannot accept a write without the registered writer and epoch. |
| Atomic multi-stream batch | A missing or stale grant for any protected stream rejects the entire batch, including outbox and revision changes. |
| Retry after transition | The original exact retry resolves its existing receipt; a changed digest rejects; neither publishes again. |
| Concurrent instances | Handoff and append serialize on the same SQLite transaction boundary; after handoff an old writer cannot append through another already-open instance. |
| Interrupted handoff | Freeze, outstanding commands and unknown outcomes survive restart; no caller-provided boolean substitutes for drain or receipt evidence. |
| Restore and rollback | New snapshots preserve fence state and are rejected by old readers; legacy snapshots load without silently acquiring protection. Rollback requires a verified compatible migration or a pre-protection archive. |
| Authority identity | The registered writer is bound to a trusted runtime authority, not merely the idempotency record's caller-supplied principal string. |

The exact trusted authority and freeze/drain owner for a first real stream
remain to be traced before enabling it. This matrix is a design constraint,
not an implementation or evidence of G2 acceptance.
