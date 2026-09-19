"""前景阶段提交后复用原 session 事实唤醒后台；不复制感知或构造 Social 来源。"""
from pydantic import JsonValue, RootModel
from .cognition_admission import _digest


class ScheduledCognitionSource:
    def __init__(self, *, runtime, policy):
        self.runtime, self.policy = runtime, policy
        self.admissions = None

    def validate(self, entry):
        event = entry.source_event
        pins = {'scheduled_session': {'actor_id': event.get('actor_id'), 'event_index': event.get('event_index')},
            'activation_policy_revision': self.policy.policy_revision}
        if (entry.source_kind != 'run_background_cognition_tick' or entry.payload
                or entry.source_pins != pins or event.get('producer_ts') != entry.producer_ts
                or entry.delivery_id != 'scheduled:' + str(event.get('event_id'))
                or self.runtime._session_store.read_event(str(event.get('actor_id')), event_id=str(event.get('event_id'))) != event):
            raise ValueError('scheduled_source_invalid')

    def admit(self, *, source_actor, producer_ts, now, source_event=None):
        rt = self.runtime
        rt._assert_cognition_owner()
        event = source_event if source_event is not None else rt._session_store.last_event(source_actor)
        if event is None or event['producer_ts'] != producer_ts:
            return ()
        prior_batch = rt._session_store.read_receipt(source_actor, kind='scheduled_cognition', key=event['event_id'])
        if prior_batch is not None:
            if prior_batch['source_digest'] != _digest(event):
                raise ValueError('scheduled_source_invalid')
            entries = tuple(self.admissions.read(key) for key in prior_batch['child_keys'])
            if any(entry is None or entry.source_event != event for entry in entries):
                raise ValueError('scheduled_admission_missing')
            return entries
        if not rt.get_background_cognition_enabled():
            return ()
        result = []
        with rt._session_store.transaction():
            for actor in rt.get_schedulable_actor_ids():
                if rt.get_background_mode(actor) not in {'active', 'quiet'}:
                    continue
                delivery = 'scheduled:' + event['event_id']
                result.append(self.admissions.admit(source_event=RootModel[dict[str, JsonValue]](event),
                    actor_id=actor, delivery_id=delivery, source_kind='run_background_cognition_tick', payload={},
                    source_pins={'scheduled_session': {'actor_id': source_actor, 'event_index': event['event_index']},
                        'activation_policy_revision': self.policy.policy_revision},
                    producer_ts=producer_ts, now=now, expires_at=now+30.))
            if result:
                rt._session_store.save_receipt(source_actor, kind='scheduled_cognition', key=event['event_id'],
                    receipt={'source_digest': _digest(event), 'child_keys': [entry.child_key for entry in result]})
        return tuple(result)
