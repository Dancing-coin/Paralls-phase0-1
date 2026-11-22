# M0-5 Command envelope sample

- Code scan SHA: `0e67fe812280e7e518c84c27653153f5a69f2330`; latest coordination baseline checked was `0ecf65aae1698fabba06f06491f7800abdc1728a` and differs only in coordination docs.
- Sampling method: static source sample, not exhaustive. Sampled `debt_runtime.py`'s command/append spine, `contract_runtime.py`'s generic and typed fulfillment paths, `main.py`'s command-like boundary, and `models.py`/`event_store.py` definitions. No test command or command was executed through the application.
- Scan commands: `rg -n 'expected_revisions|source_kind|handled_by|idempotency_key|command_audit' ...`; source line inspection.
- Scan time: 2026-11-22 Asia/Shanghai.
- Conclusion level: static-only.
- Contract reference: external read-only document `docs/architecture-v2/01-内核/07-Command信封与回执.md`, §§2-4, 8, audit section. Its clauses specify required caller-provided `expected_revisions` (§2, lines 44-71), unique `handled_by` (§3, lines 113-124), common `source_kind` validation (§4, lines 130-152), catalog-declared idempotency shape (§8, lines 239-259), and command audit not being a world event (lines 351-357).

| Check | Static evidence | Sample conclusion |
|---|---|---|
| `expected_revisions` required and caller supplied | `debt_runtime.py:72,107-109,158,188`; `contract_runtime.py:32,61,88,103` and command construction around lines 1406-1420 | Sampled typed requests carry expected revisions into the command/append path. No Gateway auto-fill was found in these domain paths. A complete Gateway path was not located; not a global compliance finding. |
| Unique `handled_by` | `fact_type_registry.py:11` registers only three owner names; no runtime command catalog found by `rg --files backend/app | rg '(gateway|command_catalog)'` | No application `command_catalog` or Gateway registry was found in the sampled backend files. The one-handler invariant is not statically enforceable from this sample. |
| Common `source_kind` validation | `main.py` source_kind matches at lines 543-623 concern cognition ingress, not a shared gameplay command validator; `closed_generic_gameplay_families.py:32` defines a source_kind field | The source-kind samples are heterogeneous. A common validation path for gameplay commands is not established. |
| Idempotency key shape matches catalog | debt command carries an opaque key through `debt_runtime.py:520-565`; Contract constructs canonical keys at `contract_runtime.py:472-473,605-609,760-764,887-892,978-979,1047-1052,1203-1208`; generic transition uses provided key at 1284-1337 | Local Contract paths enforce several purpose-specific key strings. No `command_catalog` declaration exists in backend search, so catalog conformance cannot be checked. |
| Command audit treated as world event | `main.py:211` wires `SimingAuditWriter`; `event_store.py` persists event transactions and `models.py` defines world-event batches | The sampled domain paths write world events for committed outcomes. No command-state audit event was identified in the sample. This does not prove all audit paths are separated. |

The protocol document's P-3 event registry query is independent of this command sample. This document makes no claim that all commands meet the v2 envelope contract.
