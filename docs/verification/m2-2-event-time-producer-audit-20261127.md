# M2-2 event-time producer audit

- Snapshot: A branch `thread-a/ownership-bond-followup-20261121` at `39ca1452b507d835f58e3c9b85a36d6d3f239b57`.
- Verification level: static source and call-path inspection only. No code or tests changed.

## Search evidence

Command:

```text
rg -n event_time backend/app/gameplay backend/app/main.py
```

The only production matches are:

| Source | Evidence | Meaning |
|---|---|---|
| `backend/app/gameplay/models.py:92` | Optional strict nonnegative `GameplayEvent.event_time`; omitted legacy values remain omitted in serialization. | Durable field exists, but does not supply a value to producers. |
| `backend/app/gameplay/information_runtime.py:207` | Information report event writes its validated `world_now`. | Trusted producer for report publication only. |
| `backend/app/gameplay/morale_refold_runtime.py:155` | Morale passes `death.event_time` to Pool adjustment. | Propagates source time when the casualty event already has one. |
| `backend/app/gameplay/pool_runtime.py:373,375-376,406-407,440,610,624` | Pool adjustment validates and persists an optional event time. | Sink support, not an independent clock source. |

## M6-5 source trace

- `backend/app/gameplay/m6_5_siege_runtime.py:197,210-211,385,464,489,535-539` defines and supplies a trusted world-tick provider. Report publication and the Information reaction path consume it.
- The Morale reaction at `backend/app/gameplay/m6_5_siege_runtime.py:452-454` sends the casualty event to `MoraleRefoldAuthority`; the refold uses that event's optional `event_time`.
- The Presence reaction at `backend/app/gameplay/m6_5_siege_runtime.py:455-460` supplies a breach event and current stream revision to `commit_assessment`. It does not supply a world tick.
- `backend/app/gameplay/siege_physical_input_runtime.py:54,247-286,309` shows signed physical receipts are persisted without setting `GameplayEvent.event_time`. V2 impact receipts carry a `physics_tick` used to order impact and assessment receipts, but no inspected code establishes that it shares the session world-tick epoch.
- Facility integrity and Presence events therefore have no demonstrated authoritative world-tick producer. A current tick captured during later processing would represent processing time, which can differ from source-event occurrence time.

## Conclusion

The A-side producer inventory confirms two source paths: Information report publication and Morale propagation from a casualty event. The Morale path produces a known time only when its source event has one. No general producer covers existing Ownership, Credential, Facility, Presence, or other gameplay events. In particular, the signed physics tick cannot be converted to world `event_time` from current evidence.

This audit does not implement `read_as`, principal qualification, selector interpretation, or event-type-to-FactType visibility mapping. M2-2 remains blocked on those contracts and on authoritative source-time producers for migrated domains. It does not use stream revision, global sequence, or later processing time as a substitute.

## Status

| Item | Status |
|---|---|
| Existing event-time writer sites | Static inventory complete for the searched A production tree. |
| Source-to-world-clock mapping for signed physics receipts | Not established. |
| Ownership/Credential/Facility/Presence event-time producers | Not implemented or verified. |
| `read_as` and visibility enforcement | Not implemented. |
| Tests and frozen selections | Not run; no code changed. |
