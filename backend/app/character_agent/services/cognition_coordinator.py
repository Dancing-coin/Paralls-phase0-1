"""Character owner 的原计划阶段提交；模型调度仍使用后续同槽驱动。"""
import math
import json


class CharacterCognitionCoordinator:
    def __init__(self, *, runtime, admissions):
        if runtime._session_store is not admissions.store:
            raise ValueError('cognition_session_store_mismatch')
        self.runtime, self.admissions = runtime, admissions

    def _entry(self, key, activation, now):
        self.admissions._owner()
        entry = self.admissions.read(key)
        if entry is None:
            raise ValueError('cognition_admission_missing')
        if (activation is None or activation.actor_id != entry.actor_id
                or not self.runtime.activation_is_current(activation.lock_ref, activation.token)):
            raise ValueError('cognition_activation_invalid')
        if not math.isfinite(now) or now >= entry.expires_at:
            raise ValueError('cognition_admission_expired')
        self.admissions._validate_source(entry)
        if entry.source_kind not in {'ingest_siming_output', 'run_background_cognition_tick'}:
            raise ValueError('cognition_entry_source_not_supported')
        return entry

    def begin_entry(self, key, *, activation, now):
        entry = self._entry(key, activation, now)
        previous = self.admissions.read_progress(key)
        if previous is not None:
            return previous
        background = entry.source_kind == 'run_background_cognition_tick'
        planned = self.runtime._plan_background_entry(entry.actor_id, entry.producer_ts) if background else self.runtime._plan_siming_entry(entry.payload)
        if not planned['supported']:
            raise ValueError('cognition_entry_actor_not_supported')
        frame = dict(actor_id=entry.actor_id, stage='entry', source_kind=entry.source_kind,
            producer_ts=entry.producer_ts, source_pins=entry.source_pins,
            social_ticks=self.runtime._cognition_social_ticks(entry.actor_id),
            last_background=self.runtime._last_background_tick_ms.get(entry.actor_id),
            actor_pin=[list(pair) for pair in self.runtime._capture_cognition_pin(entry.actor_id)])
        after = dict(frame, entry_after=planned['after'], normalized_payload=planned['normalized_payload'],
            cadence=dict(deferred=planned['result'] is not None, last_tick=self.runtime._last_cognition_tick_ms.get(entry.actor_id)) if background else self.runtime._plan_cognition_cadence(entry.actor_id, entry.producer_ts,
                wake_up=self.runtime._is_wake_up_input(planned['normalized_payload'])))
        if background and planned['result'] is not None:
            after.update(background_result=planned['result'], commands=[])
        plan = dict(expected_revision=self.admissions.store.event_count(entry.actor_id),
            events=planned['events'], before=frame, after=after)
        plan['self_write_pin'] = self.runtime._cognition_entry_self_write_pin(entry.actor_id, plan) if planned['after'] is not None else {}
        return self.admissions.advance_progress(key=key, expected_revision=0, stage='entry',
            status='commit_started', frame=frame, plan=plan, now=now)

    def resume_entry(self, key, *, activation, now):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if progress is None or progress.stage != 'entry':
            raise ValueError('cognition_entry_progress_required')
        if progress.status in {'stage_ready', 'completed'}:
            return progress
        if progress.status != 'commit_started':
            raise ValueError('cognition_entry_progress_invalid')
        plan = progress.plan
        existing = self.admissions.store.read_receipt(entry.actor_id, kind='cognition_stage', key=f'{key}/entry')
        if existing is None:
            self._validate_entry_pin(entry.actor_id, plan, self_write=False)
        self.admissions.store.commit_cognition_stage(actor_id=entry.actor_id,
            key=f'{key}/entry', expected_revision=plan['expected_revision'],
            events=plan['events'], before=plan['before'], after=plan['after'])
        if self.admissions.store.event_count(entry.actor_id) != plan["expected_revision"] + len(plan["events"]):
            raise ValueError("cognition_stage_head_changed")
        if existing is not None:
            # 完整原 receipt/key 已核对，只有精确原计划的自写值可以与 before 不同。
            self._validate_entry_pin(entry.actor_id, plan, self_write=True)
        # 原 session receipt 先提交；投影和局部 after 安装失败仍保留 commit_started 可恢复。
        self.runtime._finish_session_projections(entry.actor_id)
        self.runtime._install_cognition_entry_after(entry.actor_id, plan)
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision,
            stage='entry', status='completed' if plan['after']['cadence']['deferred'] else 'stage_ready', frame=plan['after'], now=now)

    def _validate_entry_pin(self, actor_id, plan, *, self_write):
        before = dict(plan['before']['actor_pin'])
        current = dict(self.runtime._capture_cognition_pin(actor_id, policy_id=plan['before'].get('policy_id', '')))
        allowed = plan['self_write_pin'] if self_write else {}
        if set(before) != set(current) or any(value != before[field] and value != allowed.get(field)
                for field, value in current.items()):
            raise ValueError('cognition_entry_stale_pin')

    def prepare_l2(self, key, *, activation, now):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if progress.stage == 'l2' and progress.status == 'provider_pending':
            self._validate_provider_pin(entry.actor_id, progress.frame)
            self.runtime._finish_session_projections(entry.actor_id)
            return progress
        if progress.stage != 'entry' or progress.status != 'stage_ready':
            raise ValueError('cognition_l2_entry_not_ready')
        self._validate_entry_pin(entry.actor_id, progress.plan, self_write=True)
        request, context = self.runtime._freeze_siming_l2_request(entry.actor_id, progress.frame)
        revision = self.admissions.store.event_count(entry.actor_id)
        pins = dict(self.runtime._capture_cognition_pin(entry.actor_id))
        pins['timeline'] = self.runtime._cognition_digest(revision + 1)
        frame = dict(progress.frame, stage='l2', context=context, actor_pin=[list(pair) for pair in sorted(pins.items())],
            l2_profile=self.runtime._l2._profile_cache[entry.actor_id])
        text = request.decode('utf-8')
        with self.admissions.store.transaction():
            self.admissions.store.commit_cognition_stage(actor_id=entry.actor_id, key=f'{key}/l2/request',
                expected_revision=revision, events=[dict(event_type='l2_reasoning_request', producer_ts=entry.producer_ts,
                    payload=json.loads(text))], before=progress.frame, after=frame)
            result = self.admissions.advance_progress(key=key, expected_revision=progress.revision,
                stage='l2', status='provider_pending', frame=frame, request_json=text, now=now)
        self.runtime._finish_session_projections(entry.actor_id)
        return result

    def _validate_provider_pin(self, actor_id, frame):
        if dict(self.runtime._capture_cognition_pin(actor_id, policy_id=frame.get('policy_id', ''))) != dict(frame['actor_pin']):
            raise ValueError('cognition_provider_stale_pin')

    def accept_l2(self, key, *, activation, now, output):
        return self._accept_provider(key, activation=activation, now=now, output=output, stage='l2')

    def accept_l3(self, key, *, activation, now, output):
        return self._accept_provider(key, activation=activation, now=now, output=output, stage='l3')

    def accept_suggestion(self, key, *, activation, now, output):
        return self._accept_provider(key, activation=activation, now=now, output=output, stage='suggestion')

    def accept_provider_error(self, key, *, activation, now, stage, error):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if stage not in {'l2', 'l3'} or not isinstance(error, Exception):
            raise ValueError('cognition_provider_error_invalid')
        failure = dict(type=type(error).__name__, message=str(error))
        if progress.stage == stage and progress.status == 'result_ready':
            if progress.completion.get('error') != failure:
                raise ValueError('cognition_progress_completion_conflict')
            return progress
        if progress.stage != stage or progress.status != 'provider_pending':
            raise ValueError(f'cognition_{stage}_provider_not_pending')
        self._validate_provider_pin(entry.actor_id, progress.frame)
        # 原异常仍在 owner 边界时冻结原 fallback；重开不重建异常类或再次规划。
        fallback = self.runtime._plan_provider_failure(progress.frame, stage, error)
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision,
            stage=stage, status='result_ready', frame=progress.frame,
            completion=dict(error=failure, fallback=fallback), now=now)

    def _accept_provider(self, key, *, activation, now, output, stage):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        completion = dict(output=output)
        if progress.stage == stage and progress.status == 'result_ready':
            if progress.completion != completion:
                raise ValueError('cognition_progress_completion_conflict')
            return progress
        if progress.stage != stage or progress.status != 'provider_pending':
            raise ValueError(f'cognition_{stage}_provider_not_pending')
        self._validate_provider_pin(entry.actor_id, progress.frame)
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision,
            stage=stage, status='result_ready', frame=progress.frame, completion=completion, now=now)

    def freeze_l2(self, key, *, activation, now):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if progress.stage == 'l2' and progress.status == 'commit_started':
            return progress
        if progress.stage != 'l2' or progress.status != 'result_ready':
            raise ValueError('cognition_l2_result_not_ready')
        self._validate_provider_pin(entry.actor_id, progress.frame)
        events, interpretation = self.runtime._plan_l2_effects(progress.frame, progress.completion.get('output'),
            fallback=progress.completion.get('fallback'))
        revision = self.admissions.store.event_count(entry.actor_id)
        pins = dict(progress.frame['actor_pin'])
        own = dict(timeline=self.runtime._cognition_digest(revision + len(events)))
        for event in events:
            if event['event_type'] == 'dynamic_state_event':
                own['dynamic'] = self.runtime._cognition_digest(event['payload'])
        pins.update(own)
        after = dict(progress.frame, interpretation=interpretation, actor_pin=[list(pair) for pair in sorted(pins.items())])
        plan = dict(expected_revision=revision, before=progress.frame, after=after, events=events, self_write_pin=own)
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision, stage='l2',
            status='commit_started', frame=progress.frame, plan=plan, now=now)

    def resume_l2(self, key, *, activation, now):
        return self._resume_effects(key, activation=activation, now=now, stage='l2')

    def resume_l3(self, key, *, activation, now):
        return self._resume_effects(key, activation=activation, now=now, stage='l3')

    def resume_suggestion(self, key, *, activation, now):
        return self._resume_effects(key, activation=activation, now=now, stage='suggestion')

    def _resume_effects(self, key, *, activation, now, stage):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if progress.stage == stage and progress.status in {'stage_ready', 'completed'}:
            return progress
        if progress.stage != stage or progress.status != 'commit_started':
            raise ValueError(f'cognition_{stage}_commit_not_started')
        plan = progress.plan
        existing = self.admissions.store.read_receipt(entry.actor_id, kind='cognition_stage', key=f'{key}/{stage}/effects')
        if existing is None:
            self._validate_entry_pin(entry.actor_id, plan, self_write=False)
        with self.admissions.store.transaction():
            self.admissions.store.commit_cognition_stage(actor_id=entry.actor_id, key=f'{key}/{stage}/effects',
                expected_revision=plan['expected_revision'], events=plan['events'], before=plan['before'], after=plan['after'])
            if stage == 'execution' and existing is None and not plan['after']['execution']['deferred']:
                self.admissions.store.save_runtime_state(entry.actor_id,
                    expected_head=plan['expected_revision']+len(plan['events']),
                    snapshot={'continuity_state': plan['after']['execution']['continuity']})
        if self.admissions.store.event_count(entry.actor_id) != plan['expected_revision'] + len(plan['events']):
            raise ValueError('cognition_stage_head_changed')
        if existing is not None:
            self._validate_entry_pin(entry.actor_id, plan, self_write=True)
        self.runtime._finish_session_projections(entry.actor_id)
        self.runtime._install_recovery_state(entry.actor_id)
        if stage == 'execution':
            self.runtime._install_execution_request_state(entry.actor_id, plan['after']['execution'])
            if not plan['after']['execution']['deferred']:
                self.runtime._persist_graph_continuity(actor_id=entry.actor_id, producer_ts=entry.producer_ts)
        if stage == 'l3':
            self.runtime._record_shadow_skill_affordance_summary(actor_id=entry.actor_id, producer_ts=entry.producer_ts)
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision, stage=stage,
            status='completed' if stage in {'suggestion', 'execution'} or plan['after'].get('background_result') else 'stage_ready', frame=plan['after'], now=now)

    def prepare_l3(self, key, *, activation, now):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if progress.stage == 'l3' and progress.status == 'provider_pending':
            self._validate_provider_pin(entry.actor_id, progress.frame)
            return progress
        if progress.stage != 'l2' or progress.status != 'stage_ready':
            raise ValueError('cognition_l3_l2_not_ready')
        self._validate_provider_pin(entry.actor_id, progress.frame)
        prepared = self.runtime._freeze_siming_l3_request(entry.actor_id, progress.frame)
        policy_id = str(prepared.behavior_policy.get('candidate_id', '') or '')
        frame = dict(progress.frame, stage='l3', l3_prepared=prepared.to_json_value(),
            policy_id=policy_id,
            actor_pin=[list(pair) for pair in self.runtime._capture_cognition_pin(entry.actor_id, policy_id=policy_id)])
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision,
            stage='l3', status='provider_pending', frame=frame,
            request_json=prepared.request_json.decode('utf-8'), now=now)

    def freeze_l3(self, key, *, activation, now):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if progress.stage == 'l3' and progress.status == 'commit_started':
            return progress
        if progress.stage != 'l3' or progress.status != 'result_ready':
            raise ValueError('cognition_l3_result_not_ready')
        self._validate_provider_pin(entry.actor_id, progress.frame)
        events, decision, own = self.runtime._plan_l3_effects(progress.frame, progress.completion.get('output'),
            fallback=progress.completion.get('fallback'))
        background_result = None
        if entry.source_kind == 'run_background_cognition_tick':
            event, background_result, agenda = self.runtime._plan_background_completion(progress.frame, decision)
            events.append(event)
            own.update(agenda=self.runtime._cognition_digest(agenda), last_background=self.runtime._cognition_digest(entry.producer_ts))
        revision = self.admissions.store.event_count(entry.actor_id)
        own['timeline'] = self.runtime._cognition_digest(revision + len(events))
        pins = dict(progress.frame['actor_pin'])
        pins.update(own)
        consumed = 'error' not in progress.completion
        after = dict(progress.frame, decision=decision, policy_consumed=consumed,
            consumed_policy_ids=sorted(set(progress.frame.get('consumed_policy_ids', [])) | ({progress.frame['policy_id']} if consumed and progress.frame.get('policy_id') else set())),
            actor_pin=[list(pair) for pair in sorted(pins.items())])
        if background_result is not None:
            after.update(background_result=background_result, commands=[], last_background=entry.producer_ts)
        plan = dict(expected_revision=revision, before=progress.frame, after=after, events=events, self_write_pin=own)
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision, stage='l3',
            status='commit_started', frame=progress.frame, plan=plan, now=now)

    def prepare_suggestion(self, key, *, activation, now):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if progress.stage == 'suggestion' and progress.status == 'provider_pending':
            self._validate_provider_pin(entry.actor_id, progress.frame)
            return progress
        if progress.stage != 'l3' or progress.status != 'stage_ready':
            raise ValueError('cognition_suggestion_l3_not_ready')
        self._validate_provider_pin(entry.actor_id, progress.frame)
        if self.runtime.get_control_mode(entry.actor_id) != 'player_priority_assisted':
            raise ValueError('cognition_suggestion_control_mode_invalid')
        if progress.frame['decision']['planning_status'] == 'continuity_floor':
            from app.models.character_agent_runtime import CharacterInterpretation, CharacterIntentDecision
            packet = self.runtime._build_continuity_floor_suggestion(actor_id=entry.actor_id,
                producer_ts=entry.producer_ts,
                interpretation=CharacterInterpretation.model_validate(progress.frame['interpretation']),
                decision=CharacterIntentDecision.model_validate(progress.frame['decision'])).model_dump(mode='json', exclude_none=True)
            frame = dict(progress.frame, stage='suggestion')
            revision = self.admissions.store.event_count(entry.actor_id)
            own = dict(timeline=self.runtime._cognition_digest(revision+1))
            pins = dict(frame['actor_pin'])
            pins.update(own)
            after = dict(frame, suggestion=packet, commands=[], actor_pin=[list(pair) for pair in sorted(pins.items())])
            plan = dict(expected_revision=revision, before=frame, after=after, self_write_pin=own,
                events=[dict(event_type='character_agent_suggestion_packet', producer_ts=entry.producer_ts, payload=packet)])
            return self.admissions.advance_progress(key=key, expected_revision=progress.revision,
                stage='suggestion', status='commit_started', frame=frame, plan=plan, now=now)
        prepared, context = self.runtime._freeze_suggestion_request(entry.actor_id, progress.frame)
        policy_id = str(prepared.behavior_policy.get('candidate_id', '') or '')
        frame = dict(progress.frame, stage='suggestion', l3_prepared=prepared.to_json_value(),
            suggestion_context=context, policy_id=policy_id, policy_consumed=False,
            actor_pin=[list(pair) for pair in self.runtime._capture_cognition_pin(entry.actor_id, policy_id=policy_id)])
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision,
            stage='suggestion', status='provider_pending', frame=frame,
            request_json=prepared.request_json.decode('utf-8'), now=now)

    def freeze_suggestion(self, key, *, activation, now):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if progress.stage == 'suggestion' and progress.status == 'commit_started':
            return progress
        if progress.stage != 'suggestion' or progress.status != 'result_ready':
            raise ValueError('cognition_suggestion_result_not_ready')
        self._validate_provider_pin(entry.actor_id, progress.frame)
        packet = self.runtime._plan_suggestion_effects(progress.frame, progress.completion['output'])
        revision = self.admissions.store.event_count(entry.actor_id)
        own = dict(timeline=self.runtime._cognition_digest(revision+1),
            policy_consumed=self.runtime._cognition_digest(bool(progress.frame.get('policy_id'))))
        pins = dict(progress.frame['actor_pin'])
        pins.update(own)
        after = dict(progress.frame, suggestion=packet, commands=[], policy_consumed=True,
            consumed_policy_ids=sorted(set(progress.frame.get('consumed_policy_ids', [])) | ({progress.frame['policy_id']} if progress.frame.get('policy_id') else set())),
            actor_pin=[list(pair) for pair in sorted(pins.items())])
        plan = dict(expected_revision=revision, before=progress.frame, after=after, self_write_pin=own,
            events=[dict(event_type='character_agent_suggestion_packet', producer_ts=entry.producer_ts, payload=packet)])
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision, stage='suggestion',
            status='commit_started', frame=progress.frame, plan=plan, now=now)

    def freeze_execution(self, key, *, activation, now):
        entry = self._entry(key, activation, now)
        progress = self.admissions.read_progress(key)
        if progress.stage == 'execution' and progress.status == 'commit_started':
            return progress
        if progress.stage != 'l3' or progress.status != 'stage_ready':
            raise ValueError('cognition_execution_l3_not_ready')
        self._validate_provider_pin(entry.actor_id, progress.frame)
        if self.runtime.get_control_mode(entry.actor_id) == 'player_priority_assisted':
            raise ValueError('cognition_execution_control_mode_invalid')
        effects = self.runtime._plan_execution_effects(progress.frame)
        revision = self.admissions.store.event_count(entry.actor_id)
        own = dict(timeline=self.runtime._cognition_digest(revision+len(effects['events'])),
            continuity=self.runtime._cognition_digest(effects['continuity']),
            social_ticks=self.runtime._cognition_digest(effects['social_ticks']))
        pins = dict(progress.frame['actor_pin'])
        pins.update(own)
        after = dict(progress.frame, stage='execution', execution=effects, commands=effects['commands'],
            social_ticks=effects['social_ticks'],
            actor_pin=[list(pair) for pair in sorted(pins.items())])
        plan = dict(expected_revision=revision, before=progress.frame, after=after,
            events=effects['events'], self_write_pin=own)
        return self.admissions.advance_progress(key=key, expected_revision=progress.revision, stage='execution',
            status='commit_started', frame=dict(progress.frame, stage='execution'), plan=plan, now=now)

    def resume_execution(self, key, *, activation, now):
        return self._resume_effects(key, activation=activation, now=now, stage='execution')
