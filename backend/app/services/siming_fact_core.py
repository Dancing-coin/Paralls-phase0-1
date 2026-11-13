from dataclasses import dataclass, field
import hashlib
import json

from app.models.authority_event import AuthorityEvent
from app.models.siming_fact_core import FactPhase, SimingFactCoreState, SimingFactSource, SimingLockedFact
from app.models.siming_runtime_state import ObservedSimingEvent


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class SimingFactCoreResult:
    accepted: bool
    known_fact_ids: list[str]
    veto_reason: str | None = None
    phase: FactPhase = 'T0'
    conflict_refs: list[str] = field(default_factory=list)
    states: list[SimingFactCoreState] = field(default_factory=list)


class SimingFactCore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], SimingFactCoreState] = {}

    def snapshot_for(self, event: AuthorityEvent) -> SimingFactCoreState | None:
        state = self._states.get((event.room_id, event.scene_id))
        return state.model_copy(deep=True) if state is not None else None

    def snapshots_for_room(self, room_id: str) -> list[SimingFactCoreState]:
        return [state.model_copy(deep=True) for (room, _), state in sorted(self._states.items()) if room == room_id]

    def install_snapshot(self, state: SimingFactCoreState) -> None:
        self._states[(state.room_id, state.scene_id)] = state.model_copy(deep=True)

    def evaluate(self, observed_events: list[ObservedSimingEvent]) -> SimingFactCoreResult:
        result = self.plan_evaluate(observed_events)
        if result.accepted:
            for state in result.states:
                self.install_snapshot(state)
        return result

    def plan_evaluate(self, observed_events: list[ObservedSimingEvent]) -> SimingFactCoreResult:
        states: dict[tuple[str, str], SimingFactCoreState] = {}
        known: list[str] = []
        phase: FactPhase = 'T0'
        for event in observed_events:
            payload = event.payload
            scope = (event.room_id, event.scene_id)
            state = states.get(scope) or self.snapshot_for(event.authority_event)
            phase = state.phase if state is not None else 'T0'
            if payload.get('locked_fact_conflict') is True:
                return SimingFactCoreResult(False, [], 'locked_fact_conflict', phase)
            fact_id = payload.get('fact_id') or payload.get('established_fact_id')
            operation = payload.get('fact_operation')
            if operation is None and ('fact_value' in payload or (fact_id and 'state_value' in payload)):
                operation = 'write'
            if operation is None:
                legacy_id = payload.get('established_fact_id')
                if legacy_id is not None and str(legacy_id).strip():
                    known.append(str(legacy_id).strip())
                    if event.authority_event.source.layer == 'L1':
                        state = state or SimingFactCoreState(room_id=event.room_id, scene_id=event.scene_id)
                        fingerprint = hashlib.sha256(_canonical(event.authority_event.model_dump(mode='json')).encode()).hexdigest()
                        prior = state.sources.get(event.source_event_id)
                        if prior is not None and prior.digest != fingerprint:
                            return SimingFactCoreResult(False, [], 'fact_source_identity_conflict', phase, [event.source_event_id])
                        state.sources[event.source_event_id] = SimingFactSource(producer_ts=event.producer_ts, digest=fingerprint)
                        state.evidence_sources.setdefault(str(legacy_id).strip(), event.source_event_id)
                        states[scope] = state
                continue
            state = state or SimingFactCoreState(room_id=event.room_id, scene_id=event.scene_id)
            try:
                reason, refs = self._apply(event, state, operation, fact_id)
            except (ValueError, TypeError):
                reason, refs = 'invalid_fact_payload', [event.source_event_id]
            if reason:
                return SimingFactCoreResult(False, [], reason, state.phase, refs)
            states[scope] = state
            phase = state.phase
            if operation in {'write', 'reveal'} and fact_id:
                known.append(str(fact_id))
            elif operation == 'deduce':
                known.extend(payload.get('evidence_refs', []))
        return SimingFactCoreResult(True, list(dict.fromkeys(known)), phase=phase, states=list(states.values()))

    def _apply(self, event, state, operation, fact_id):
        payload = event.payload
        source = event.authority_event.source
        if (event.event_type != 'world_fact_event' or not (
                source.layer == 'L1' or (source.layer == 'L2' and (source.system == 'siming' or source.system.startswith('siming.'))))):
            return 'invalid_fact_source', [event.source_event_id]
        fingerprint = hashlib.sha256(_canonical(event.authority_event.model_dump(mode='json')).encode()).hexdigest()
        prior_source = state.sources.get(event.source_event_id)
        if prior_source is not None:
            return (None, []) if prior_source.digest == fingerprint else ('fact_source_identity_conflict', [event.source_event_id])
        if operation not in {'advance_phase', 'write', 'reveal', 'deduce'}:
            return 'invalid_fact_operation', [event.source_event_id]
        if state.last_ts is not None and event.producer_ts < state.last_ts:
            return 'fact_time_reversal', [event.source_event_id]
        evidence = payload.get('evidence_refs', [])
        sources = payload.get('source_event_refs', [])
        for refs in (evidence, sources):
            if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
                return 'invalid_fact_references', [event.source_event_id]
        if fact_id in evidence or event.source_event_id in sources:
            return 'self_fact_reference', [event.source_event_id]
        for ref in evidence:
            record = state.facts.get(ref) or state.sources.get(state.evidence_sources.get(ref, ref))
            if record is None:
                return 'unknown_evidence_reference', [ref]
            if record.producer_ts > event.producer_ts:
                return 'fact_time_reversal', [ref]
        for ref in sources:
            record = state.sources.get(ref)
            if record is None:
                return 'broken_fact_source_chain', [ref]
            if record.producer_ts > event.producer_ts:
                return 'fact_time_reversal', [ref]
        if operation == 'advance_phase':
            phases = ('T0', 'T1', 'T2', 'T3')
            target = payload.get('fact_phase')
            if target not in phases or phases.index(target) not in {phases.index(state.phase), phases.index(state.phase) + 1}:
                return 'invalid_fact_phase_transition', [event.source_event_id]
            state.phase = target
        elif operation == 'write':
            if not isinstance(fact_id, str) or not fact_id.strip() or not ('fact_value' in payload or 'state_value' in payload):
                return 'invalid_fact_payload', [event.source_event_id]
            fact = SimingLockedFact(
                fact_id=fact_id, value=payload.get('fact_value', payload.get('state_value')),
                world_anchor_id=payload.get('world_anchor_id', ''), state_key=payload.get('state_key', ''),
                category=payload.get('fact_category', 'session'), producer_ts=event.producer_ts,
                source_event_id=event.source_event_id, evidence_refs=evidence, source_event_refs=sources,
            )
            old = state.facts.get(fact_id)
            if old is not None and _canonical(old.value) != _canonical(fact.value):
                return 'fact_value_conflict', [fact_id, old.source_event_id]
            if old is not None and (
                old.world_anchor_id, old.state_key, old.category, old.evidence_refs, old.source_event_refs
            ) != (fact.world_anchor_id, fact.state_key, fact.category, fact.evidence_refs, fact.source_event_refs):
                return 'fact_metadata_conflict', [fact_id, old.source_event_id]
            if old is not None and state.phase == 'T3':
                return 'fact_frozen', [fact_id]
            if fact.world_anchor_id:
                for other in state.facts.values():
                    if (other.world_anchor_id, other.state_key) == (fact.world_anchor_id, fact.state_key) and _canonical(other.value) != _canonical(fact.value):
                        return 'world_anchor_conflict', [other.fact_id, fact_id]
            if old is None:
                if state.phase in {'T2', 'T3'}:
                    return 'fact_set_locked', [fact_id]
                if fact.category == 'foundation' and state.phase != 'T0':
                    return 'fact_category_locked', [fact_id]
                state.facts[fact_id] = fact
        else:
            if operation == 'deduce' and not evidence:
                return 'deduction_requires_evidence', [event.source_event_id]
            if operation == 'reveal' and fact_id not in state.facts:
                return 'unknown_fact_reference', [str(fact_id)]
            if 'fact_value' in payload or 'state_value' in payload:
                return 'revelation_cannot_write_fact', [str(fact_id)]
        state.last_ts = event.producer_ts
        state.sources[event.source_event_id] = SimingFactSource(producer_ts=event.producer_ts, digest=fingerprint)
        return None, []
