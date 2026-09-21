"""司命 owner 入站与冻结领域计划；provider 和输出交付由后续阶段续接。"""
from app.models.authority_event import AuthorityEvent
from app.models.siming_heavenly_memory import (
    SimingAdmissionProvider, SimingAdmissionCursor, SimingAdmissionEffect, SimingAdmissionEffectReceipt, SimingAdmissionTransition,
)
from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch
from app.services.siming_continuation import SimingProviderCompletion, SimingAcceptedPlan, SimingAdvance, SimingTurnFrame, SimingStageEffects, digest, CANDIDATE_TIMELINE_REQUEUE, candidate_timeline_changed
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_heavenly_runtime_support import SimingHeavenlyRuntimeSupport


class SimingCoordinator:
    def __init__(self, *, runtime, admissions, graph, invalidation_reader, output_pipeline=None, character_admissions=None):
        self.runtime = runtime
        self.admissions = admissions
        self.graph = graph
        self._invalidation_reader = invalidation_reader
        self._cursor = None
        self.output_pipeline = output_pipeline
        self.character_admissions = character_admissions

    def _owner(self):
        self.runtime._assert_siming_owner()

    def admit_event(self, event: AuthorityEvent, *, now, expires_at, policy_version,
                    source_outbox_ref=None, source_transaction_ref=None):
        self._owner()
        if not SimingEventConsumer().handle_event(event):
            raise ValueError("siming_source_not_supported")
        if event.event_type == "population_cadence_event":
            raise ValueError("siming_source_requires_direct_owner_route")
        return self.admissions.admit(scope=SimingHeavenlyRuntimeSupport._scope_for(event), source=event,
            now=now, expires_at=expires_at, policy_version=policy_version,
            source_outbox_ref=source_outbox_ref, source_transaction_ref=source_transaction_ref)

    def take_ready(self, *, now, limit=4):
        self._owner()
        if not 1 <= limit <= 4:
            raise ValueError("siming_ready_limit")
        page = self.admissions.list_pending_all(limit=32, cursor=self._cursor)
        self._cursor = page.next_cursor
        ready = []
        for entry in page.entries:
            head = self.admissions.read_room_head(entry.key.scope)
            if (entry.due_at <= now and head is not None
                    and entry.room_sequence == head.completed_sequence + 1):
                ready.append(entry.key)
                if len(ready) == limit:
                    self._cursor = SimingAdmissionCursor(scope=entry.key.scope, due_at=entry.due_at, entry_id=entry.entry_id)
                    break
        return tuple(ready)

    def prepare_ready(self, key, *, now):
        """调用方已经保留原全局槽；仅 owner 推进账本并返回独立 provider。"""
        self._owner()
        entry, _ = self._entry_and_head(key)
        if entry.state in {"admitted", "due", "requeued"} and (entry.transition is None or entry.transition.reason != CANDIDATE_TIMELINE_REQUEUE):
            entry = self.begin(key, now=now).entry
        if entry.state == "result_ready":
            entry = self.freeze_result(key, now=now).entry
        if entry.state == "commit_started":
            entry = self.resume_committed(key, now=now).entry
            if entry.state != "commit_started" or self.read_plan(key).after.stage not in {"candidate", "adaptive"}:
                return None
        if entry.state not in {"provider_pending", "commit_started", "requeued"}:
            return None
        advance = self.prepare_provider(key, now=now)
        if advance.status != "pending" or advance.replayed:
            return None
        provider = self.runtime._llm_provider if advance.job.stage == "candidate" else self.runtime.heavenly_support._llm_provider
        try:
            revision = self.admissions.read(key).entry.provider_revision
        except BaseException:
            # 请求已经落盘但尚未交付 driver；读取失败也不得遗留活 token。
            self.runtime.cancel_turn(advance.job.turn_id)
            raise
        return advance.job, provider, revision

    def finish_ready(self, key, job, completion, *, provider_revision, now):
        self._owner()
        accepted = self.accept_provider(key, job, completion, now=now, provider_revision=provider_revision)
        if accepted.replayed:
            # 原 completion 已确认；继续当前持久阶段，不把旧 result_ready 当成当前状态重做。
            accepted = self.admissions.read(key)
        if accepted.entry.state == "result_ready":
            accepted = self.freeze_result(key, now=now)
        if accepted.entry.state == "commit_started":
            return self.resume_committed(key, now=now)
        return accepted

    def fail_ready(self, key, job, *, provider_revision, error_kind, now):
        self._owner()
        current = self.admissions.read(key)
        if current is None:
            raise ValueError("siming_admission_missing")
        entry = current.entry
        if entry.state != "provider_pending" or entry.provider_revision != provider_revision:
            return current
        frame = SimingTurnFrame.model_validate_json(entry.transition.provider.frame_json)
        if frame.job != job:
            return current
        entry, head = self._entry_and_head(key)
        self.runtime.cancel_turn(job.turn_id)
        return self.admissions.advance(key, expected_revision=entry.revision, now=now,
            transition=SimingAdmissionTransition(state="failed", reason="provider_failed:" + error_kind,
                room_head=head.model_copy(update={"revision": head.revision + 1,
                    "completed_sequence": entry.room_sequence})))

    def _entry_and_head(self, key):
        receipt = self.admissions.read(key)
        if receipt is None:
            raise ValueError("siming_admission_missing")
        head = self.admissions.read_room_head(key.scope)
        if head is None or receipt.entry.room_sequence != head.completed_sequence + 1:
            raise ValueError("siming_room_busy")
        return receipt.entry, head

    def _source_pin(self, event):
        if self.runtime._source_pin_reader is None or self.runtime._actor_pin_reader is None:
            raise ValueError("siming_pin_reader_required")
        source = self.runtime._source_pin_reader(event.model_copy(deep=True))
        if source is None or source is False:
            raise ValueError("siming_source_not_live")
        return digest({"source": source, "actors": {actor: self.runtime._actor_pin_reader(actor)
            for actor in sorted(set(event.routing.target_ids))}})

    def begin(self, key, *, now):
        self._owner()
        entry, head = self._entry_and_head(key)
        if entry.state == "commit_started":
            return self.admissions.read(key)
        if entry.state not in {"admitted", "due", "requeued"} or (entry.transition is not None and entry.transition.reason == CANDIDATE_TIMELINE_REQUEUE):
            raise ValueError("siming_stage_not_initial")
        if now >= entry.expires_at:
            return self._reconcile_only(entry, head, now=now, reason="wall_ttl_expired")
        if head.after_state:
            self.runtime.install_planned_state(SimingStageEffects.model_validate(head.after_state))
        source = AuthorityEvent.model_validate(entry.source)
        invalidation = self._invalidation(source)
        if invalidation is not None:
            return self._reconcile_only(entry, head, now=now, reason=invalidation)
        pin = self._source_pin(source)
        inputs = SimingEventConsumer().handle_event(source)
        plan = self.runtime.plan_initial(inputs[0])
        if self._source_pin(source) != pin:
            raise ValueError("siming_stale_pin")
        plan_pin = self.runtime.capture_plan_pin(plan)
        if digest(self.runtime.capture_plan_pin(plan)) != digest(plan_pin):
            raise ValueError("siming_stale_plan_pin")
        return self._freeze_plan(entry, plan, now=now, stage="initial", ordinal=0, source_pin=pin, plan_pin=plan_pin)

    def _freeze_plan(self, entry, plan, *, now, stage, ordinal, source_pin, plan_pin):
        key = entry.key
        effects = [SimingAdmissionEffect(effect_key=key.effect_key(stage, ordinal, index),
            kind="graph_batch", payload=batch.model_dump(mode="json"))
            for index, batch in enumerate(plan.effects.batches)]
        effects.append(SimingAdmissionEffect(effect_key=key.effect_key(stage, ordinal, len(effects)),
            kind="runtime_state", payload={"after": plan.after.model_dump(mode="json"),
                "state": plan.effects.model_dump(mode="json", exclude={"batches"}), "source_pin": source_pin, "plan_pin": plan_pin}))
        if plan.after.stage == "completed" and self.output_pipeline is not None:
            for kind, payload in self._plan_outputs(plan):
                effects.append(SimingAdmissionEffect(effect_key=key.effect_key(stage, ordinal, len(effects)), kind=kind, payload=payload))
        return self.admissions.advance(key, expected_revision=entry.revision, now=now,
            transition=SimingAdmissionTransition(state="commit_started", stage=stage, ordinal=ordinal, effects=effects))

    def _plan_outputs(self, plan):
        from app.services.siming_character_dispatch_adapter import SUPPORTED_SIMING_EVENT_TYPES
        pipeline = self.output_pipeline
        source = plan.after.siming_input.source_event
        result = plan.after.result
        events = pipeline._producer.materialize_outputs(result.outputs)
        effects = [("audit_bundle", {"audits": [item.model_dump(mode="json") for item in result.audit_records],
            "checkpoints": [item.model_dump(mode="json") for item in result.checkpoints],
            "read_model": None if result.read_model is None else result.read_model.model_dump(mode="json"),
            "observatory": plan.effects.observatory_messages})]
        confirmed = []
        support = self.runtime.heavenly_support
        for output, event in zip(result.outputs, events):
            if output.output_type != "dispatch_intent" or output.payload.get("siming_graph_owned") is not True:
                continue
            if support is None or not support._is_selected_candidate(source):
                raise ValueError("siming_dispatch_selection_missing")
            args = dict(scope=support._scope_for(source), recorded_at=source.producer_ts,
                correlation_id=source.correlation_id, dispatch_event_id=event.event_id)
            _, before = support._plan_dispatch_state(**args, state="sent_unconfirmed")
            _, after = support._plan_dispatch_state(**args, state="authority_confirmed", prior_batch=before)
            if before is not None:
                effects.append(("dispatch_record", before.model_dump(mode="json")))
            if after is not None:
                confirmed.append(("dispatch_record", after.model_dump(mode="json")))
        effects.extend(("publish_event", {"event": event.model_dump(mode="json")}) for event in events)
        effects.extend(confirmed)
        adapter = pipeline._character_dispatch_adapter
        for event in events:
            if event.correlation_id != source.correlation_id or event.event_type not in SUPPORTED_SIMING_EVENT_TYPES:
                continue
            if adapter is None:
                effects.append(("character_delivery_unavailable", {"event": event.model_dump(mode="json")}))
                continue
            prepared = adapter.prepare_deliveries(event)
            effects.extend(("character_delivery", {"event": event.model_dump(mode="json"), "delivery": item.model_dump(mode="json")})
                for item in prepared.delivery_inputs)
            effects.extend(("character_delivery_audit", {"audit": item.model_dump(mode="json")}) for item in prepared.audit_summaries)
        return effects

    def character_delivery_proof(self, event, delivery_input):
        """点读原冻结交付和此前发布回执，不把进程内 bus 记录当持久授权。"""
        from app.models.siming_heavenly_memory import SimingAdmissionKey
        self._owner()
        key = SimingAdmissionKey(scope=SimingHeavenlyRuntimeSupport._scope_for(event),
            source_event_id=event.causation_id)
        current = self.admissions.read(key)
        if (current is None or current.entry.state not in {"commit_started", "completed"}
                or current.entry.commit_revision is None):
            raise ValueError("siming_character_source_missing")
        entry = current.entry
        frozen = self.admissions.read(key, revision=entry.commit_revision)
        if frozen is None or frozen.entry.state != "commit_started":
            raise ValueError("siming_character_source_plan_missing")
        payload = {"event": event.model_dump(mode="json"), "delivery": delivery_input}
        effects = frozen.entry.transition.effects
        matches = [(index, effect) for index, effect in enumerate(effects)
            if effect.kind == "character_delivery" and effect.payload == payload]
        if len(matches) != 1 or entry.source["correlation_id"] != event.correlation_id:
            raise ValueError("siming_character_source_payload_mismatch")
        index, effect = matches[0]
        receipts = {item.effect_key: item.receipt for item in entry.transition.receipts}
        publications = [item for item in effects[:index] if item.kind == "publish_event"
            and item.payload == {"event": payload["event"]}]
        if (len(publications) != 1 or any(item.effect_key not in receipts for item in effects[:index])
                or receipts.get(publications[0].effect_key) != {"event_id": event.event_id,
                    "event_digest": digest(payload["event"])}):
            raise ValueError("siming_character_source_unconfirmed")
        return {"parent_key": key.model_dump(mode="json"), "commit_revision": entry.commit_revision,
            "effect_key": effect.effect_key, "payload_digest": digest(payload), "expires_at": entry.expires_at}

    def prepare_provider(self, key, *, now, timeout_seconds=30.0):
        self._owner()
        entry, head = self._entry_and_head(key)
        if now >= entry.expires_at:
            self._reconcile_only(entry, head, now=now, reason="wall_ttl_expired")
            return SimingAdvance(status="zero_write", reason="deadline")
        if entry.state == "requeued" and entry.transition.reason == CANDIDATE_TIMELINE_REQUEUE:
            return self._prepare_requeued(entry, head, now=now, timeout_seconds=timeout_seconds)
        if entry.state == "provider_pending":
            frame = SimingTurnFrame.model_validate_json(entry.transition.provider.frame_json)
            try:
                active = SimingTurnFrame.model_validate_json(self.runtime.export_turn(frame.turn_id))
            except KeyError:
                reason = self._invalidation(AuthorityEvent.model_validate(entry.source))
                if reason is not None:
                    self._reconcile_only(entry, head, now=now, reason=reason)
                    return SimingAdvance(status="zero_write", reason=reason)
                if head.after_state:
                    self.runtime.install_planned_state(SimingStageEffects.model_validate(head.after_state))
                advance = self.runtime.restore_turn(entry.transition.provider.frame_json.encode(),
                    timeout_seconds=timeout_seconds)
                if advance.status != "pending":
                    if advance.reason == "stale_pin" and self._can_requeue(frame, now):
                        self._requeue_candidate(entry, frame, now=now, completion_json=None)
                        return SimingAdvance(status="zero_write", reason="requeued")
                    self._reconcile_only(entry, head, now=now, reason=advance.reason)
                    return advance
                return self._save_provider(entry, advance, now=now, ordinal=entry.transition.ordinal)
            if active.job != frame.job:
                raise ValueError("siming_provider_token_mismatch")
            # 该 job 已交给调用方，重复读取不得再次启动 provider。
            return SimingAdvance(status="pending", job=frame.job, replayed=True)
        if entry.state != "commit_started":
            raise ValueError("siming_provider_plan_required")
        if {item.effect_key for item in entry.transition.receipts} != {item.effect_key for item in entry.transition.effects}:
            raise ValueError("siming_admission_outstanding_effect")
        reason = self._invalidation(AuthorityEvent.model_validate(entry.source))
        if reason is not None:
            self._reconcile_only(entry, head, now=now, reason=reason)
            return SimingAdvance(status="zero_write", reason=reason)
        plan = self.read_plan(key)
        self.runtime.install_planned_state(plan.effects)
        if not self._provider_plan_pin_is_current(entry, plan):
            self._reconcile_only(entry, head, now=now, reason="stale_pin")
            return SimingAdvance(status="zero_write", reason="stale_pin")
        advance = self.runtime.register_planned_turn(plan.after.model_dump_json().encode(),
            expires_at=entry.expires_at, timeout_seconds=timeout_seconds)
        if advance.status != "pending":
            return advance
        return self._save_provider(entry, advance, now=now, ordinal=entry.transition.ordinal + 1)

    def _can_requeue(self, frame, now):
        return (frame.stage == "candidate" and now < frame.expires_at
            and candidate_timeline_changed(frame.pin, self.runtime._capture_siming_pin(frame)))

    def _requeue_candidate(self, entry, frame, *, now, completion_json):
        # 原 job 留作被拒结果的身份，frame.pin 保存本次重排所观察到的读集。
        frame = frame.model_copy(deep=True)
        frame.pin = self.runtime._capture_siming_pin(frame)
        provider = entry.transition.provider.model_copy(update={
            "frame_json": frame.model_dump_json(), "pin_digest": digest(frame.pin)})
        receipt = self.admissions.advance(entry.key, expected_revision=entry.revision, now=now,
            transition=SimingAdmissionTransition(state="requeued", stage="candidate",
                ordinal=entry.transition.ordinal, due_at=now, provider=provider,
                completion_json=completion_json, reason=CANDIDATE_TIMELINE_REQUEUE))
        self.runtime.cancel_turn(frame.job.turn_id)
        return receipt

    def _prepare_requeued(self, entry, head, *, now, timeout_seconds):
        frame = SimingTurnFrame.model_validate_json(entry.transition.provider.frame_json)
        reason = self._invalidation(AuthorityEvent.model_validate(entry.source))
        if now >= min(entry.expires_at, frame.expires_at):
            reason = "wall_ttl_expired"
        if head.after_state:
            self.runtime.install_planned_state(SimingStageEffects.model_validate(head.after_state))
        if reason is None:
            current = self.runtime._capture_siming_pin(frame)
            if current != frame.pin and not candidate_timeline_changed(frame.pin, current):
                reason = "stale_pin"
        if reason is not None:
            self._reconcile_only(entry, head, now=now, reason=reason)
            return SimingAdvance(status="zero_write", reason=reason)
        advance = self.runtime.register_planned_turn(frame.model_dump_json().encode(),
            expires_at=min(entry.expires_at, frame.expires_at), timeout_seconds=timeout_seconds)
        if advance.status != "pending":
            return advance
        return self._save_provider(entry, advance, now=now, ordinal=entry.transition.ordinal + 1)

    def _provider_plan_pin_is_current(self, entry, plan):
        from copy import deepcopy
        committed = self.admissions.read(entry.key, revision=entry.commit_revision).entry
        expected = deepcopy(next(effect for effect in committed.transition.effects if effect.kind == "runtime_state").payload["plan_pin"])
        current = self.runtime.capture_plan_pin(plan)
        narrative = plan.effects.narrative_state
        if narrative is not None:
            expected["narrative"] = [narrative.revision, narrative.open_count]
        # 只有原冻结批次确切写出的最后节点版本可以作为自身变更扣除。
        latest = {(batch.scope.model_dump_json(), node.node_id): (batch.scope, node)
            for batch in plan.effects.batches for node in batch.nodes}
        for scope, node in latest.values():
            if self.graph.get_node(scope=scope, node_id=node.node_id,
                    valid_at=node.validity.valid_from) != node:
                return False
        for pin in (expected, current):
            heavenly = pin.get("heavenly")
            if heavenly is None:
                continue
            scope = heavenly["graph"]["scope"]
            own_ids = {node.node_id for batch_scope, node in latest.values()
                if batch_scope.model_dump(mode="json") == scope}
            for section in (heavenly["graph"], heavenly["semantic"]):
                section["nodes"] = [node for node in section["nodes"] if node["node_id"] not in own_ids]
            heavenly["staging"] = [item for item in heavenly["staging"] if item["entry_id"] not in own_ids]
        return digest(expected) == digest(current)

    def _save_provider(self, entry, advance, *, now, ordinal):
        try:
            frozen = self.runtime.export_turn(advance.job.turn_id).decode()
            frame = SimingTurnFrame.model_validate_json(frozen)
            self.admissions.advance(entry.key, expected_revision=entry.revision, now=now,
                transition=SimingAdmissionTransition(state="provider_pending", stage=frame.stage,
                    ordinal=ordinal,
                    provider=SimingAdmissionProvider(provider_identity=digest(frame.pin["provider"]),
                        request_json=advance.job.request_json.decode(), frame_json=frozen,
                        pin_digest=advance.job.pin_digest)))
        except BaseException:
            self.runtime.cancel_turn(advance.job.turn_id)
            raise
        return advance

    def accept_provider(self, key, job, completion_json, *, now, provider_revision=None):
        self._owner()
        current = self.admissions.read(key)
        if current is None or current.entry.provider_revision is None:
            raise ValueError("siming_provider_missing")
        entry = current.entry
        revision = entry.provider_revision if provider_revision is None else provider_revision
        provider_receipt = self.admissions.read(key, revision=revision)
        if provider_receipt is None or provider_receipt.entry.state != "provider_pending":
            raise ValueError("siming_provider_missing")
        provider_entry = provider_receipt.entry
        frame = SimingTurnFrame.model_validate_json(provider_entry.transition.provider.frame_json)
        if frame.job != job:
            raise ValueError("siming_provider_token_mismatch")
        completion = SimingProviderCompletion.model_validate_json(completion_json)
        canonical = completion.model_dump_json()
        accepted = self.admissions.read(key, revision=revision + 1)
        if accepted is not None and accepted.entry.state in {"result_ready", "requeued"}:
            if accepted.entry.transition.completion_json != canonical:
                raise ValueError("siming_completion_conflict")
            self.runtime.cancel_turn(job.turn_id)
            return accepted.model_copy(update={"replayed": True})
        if entry.provider_revision != revision:
            raise ValueError("siming_provider_token_mismatch")
        entry, head = self._entry_and_head(key)
        reason = "wall_ttl_expired" if now >= entry.expires_at else self._invalidation(AuthorityEvent.model_validate(entry.source))
        validation = None
        if reason is None:
            validation = self.runtime.validate_completion(job, completion_json)
            reason = validation.reason if validation.status == "zero_write" else None
        if reason is not None:
            if validation is not None and reason == "stale_pin" and self._can_requeue(frame, now):
                return self._requeue_candidate(entry, frame, now=now, completion_json=canonical)
            if (validation is not None and reason == "stale_pin"
                    and completion.error == "SimingLlmProviderTimeout"):
                receipt = self.admissions.advance(key, expected_revision=entry.revision, now=now,
                    transition=SimingAdmissionTransition(state="result_ready",
                        stage=provider_entry.transition.stage,
                        ordinal=provider_entry.transition.ordinal, completion_json=canonical))
                self.runtime.cancel_turn(job.turn_id)
                return receipt
            self.runtime.cancel_turn(job.turn_id)
            return self._reconcile_only(entry, head, now=now, reason=reason)
        receipt = self.admissions.advance(key, expected_revision=entry.revision, now=now,
            transition=SimingAdmissionTransition(state="result_ready", stage=provider_entry.transition.stage,
                ordinal=provider_entry.transition.ordinal, completion_json=canonical))
        self.runtime.cancel_turn(job.turn_id)
        return receipt

    def freeze_result(self, key, *, now):
        self._owner()
        entry, head = self._entry_and_head(key)
        if entry.state == "commit_started":
            return self.admissions.read(key)
        if entry.state != "result_ready":
            raise ValueError("siming_result_required")
        provider = self.admissions.read(key, revision=entry.provider_revision).entry.transition.provider
        frame = SimingTurnFrame.model_validate_json(provider.frame_json)
        if head.after_state:
            self.runtime.install_planned_state(SimingStageEffects.model_validate(head.after_state))
        reason = "wall_ttl_expired" if now >= min(entry.expires_at, frame.expires_at) else self._invalidation(AuthorityEvent.model_validate(entry.source))
        if reason is None and digest(self.runtime._capture_siming_pin(frame)) != provider.pin_digest:
            reason = "stale_pin"
        if reason is not None:
            return self._reconcile_only(entry, head, now=now, reason=reason)
        completion = SimingProviderCompletion.model_validate_json(entry.transition.completion_json)
        plan = self.runtime.plan_accepted(provider.frame_json.encode(), completion)
        if digest(self.runtime._capture_siming_pin(frame)) != provider.pin_digest:
            return self._reconcile_only(entry, head, now=now, reason="stale_pin")
        return self._freeze_plan(entry, plan, now=now, stage=entry.transition.stage,
            ordinal=entry.transition.ordinal, source_pin=frame.pin["source_live"], plan_pin=self.runtime.capture_plan_pin(plan))

    def read_plan(self, key):
        self._owner()
        receipt = self.admissions.read(key)
        if receipt is None or receipt.entry.commit_revision is None:
            raise ValueError("siming_plan_not_committed")
        committed = self.admissions.read(key, revision=receipt.entry.commit_revision)
        if committed is None or committed.entry.state != "commit_started":
            raise ValueError("siming_plan_revision_missing")
        effects = committed.entry.transition.effects
        states = [effect for effect in effects if effect.kind == "runtime_state"]
        if len(states) != 1:
            raise ValueError("siming_plan_schema_invalid")
        state = states[0]
        return SimingAcceptedPlan.model_validate({"after": state.payload["after"],
            "effects": {**state.payload["state"], "batches": [effect.payload for effect in effects if effect.kind == "graph_batch"]}})

    def resume_committed(self, key, *, now):
        self._owner()
        prior = self.admissions.read(key)
        if prior is not None and prior.entry.state in {"completed", "stale", "cancelled", "failed"}:
            return prior
        entry, head = self._entry_and_head(key)
        plan = self.read_plan(key)
        if now >= entry.expires_at:
            return self._reconcile_only(entry, head, now=now, reason="wall_ttl_expired")
        invalidation = self._invalidation(AuthorityEvent.model_validate(entry.source))
        if invalidation is not None:
            return self._reconcile_only(entry, head, now=now, reason=invalidation)
        receipts = {receipt.effect_key: receipt for receipt in entry.transition.receipts}
        for effect in entry.transition.effects:
            if effect.effect_key in receipts:
                if effect.kind == "runtime_state":
                    self.runtime.install_planned_state(plan.effects)
                elif effect.kind == "audit_bundle" and self.output_pipeline is not None:
                    self._apply_audits(effect.payload)
                continue
            next_head = None
            if effect.kind in {"graph_batch", "dispatch_record"}:
                batch = HeavenlyGraphWriteBatch.model_validate(effect.payload)
                self.graph.write_batch(batch)
                receipt = self._graph_receipt(batch, effect.payload)
            elif effect.kind == "runtime_state":
                next_head = head.model_copy(update={"revision": head.revision + 1, "after_state": effect.payload["state"]})
                receipt = {"state_digest": digest(effect.payload["state"])}
            elif effect.kind == "audit_bundle":
                if self.output_pipeline is None:
                    return self._outstanding(entry, now=now, reason="output_pipeline_unavailable")
                self._apply_audits(effect.payload)
                receipt = {"audit_digest": digest(effect.payload)}
            elif effect.kind == "publish_event":
                if self.output_pipeline is None:
                    return self._outstanding(entry, now=now, reason="output_pipeline_unavailable")
                if entry.transition.reason in {"publishing:" + effect.effect_key, "authority_unknown:" + effect.effect_key}:
                    return self._outstanding(entry, now=now, reason="authority_unknown:" + effect.effect_key)
                # 原 publisher 未提供跨重启完整回执；先持久记录尝试，禁止不明结果重发。
                entry = self._outstanding(entry, now=now, reason="publishing:" + effect.effect_key).entry
                event = AuthorityEvent.model_validate(effect.payload["event"])
                self.output_pipeline._producer.publish_events([event])
                receipt = {"event_id": event.event_id, "event_digest": digest(effect.payload["event"])}
            elif effect.kind == "character_delivery":
                if self.character_admissions is None:
                    return self._outstanding(entry, now=now, reason="character_admission_unavailable")
                child = self.character_admissions.admit_delivery(
                    dispatch_event=AuthorityEvent.model_validate(effect.payload["event"]),
                    delivery_input=effect.payload["delivery"], effect_key=effect.effect_key,
                    expires_at=entry.expires_at, now=now)
                receipt = {"child_key": child.child_key, "input_digest": child.input_digest}
            elif effect.kind == "character_delivery_unavailable":
                return self._outstanding(entry, now=now, reason="character_admission_unavailable")
            elif effect.kind == "character_delivery_audit":
                receipt = {"audit": effect.payload["audit"]}
            else:
                raise ValueError("siming_effect_kind_invalid")
            receipts[effect.effect_key] = SimingAdmissionEffectReceipt(effect_key=effect.effect_key, receipt=receipt)
            transition = entry.transition.model_copy(update={"receipts": list(receipts.values()), "room_head": next_head, "reason": ""})
            entry = self.admissions.advance(key, expected_revision=entry.revision, transition=transition, now=now).entry
            if next_head is not None:
                head = next_head
                self.runtime.install_planned_state(plan.effects)
        self.runtime.install_planned_state(plan.effects)
        if plan.after.stage == "completed" and any(effect.kind == "audit_bundle" for effect in entry.transition.effects):
            # 发布可同步入站同房间 ACK；保留真实队尾，不拿发布前的 head 覆盖新入站。
            entry, head = self._entry_and_head(key)
            # 全部输出/真实子入站已获回执；父 handoff 完成不等于子认知已完成。
            return self.admissions.advance(key, expected_revision=entry.revision, now=now,
                transition=SimingAdmissionTransition(state="completed", receipts=list(receipts.values()),
                    room_head=head.model_copy(update={"revision": head.revision + 1,
                        "completed_sequence": entry.room_sequence})))
        return self.admissions.read(key)

    def _outstanding(self, entry, *, now, reason):
        previous = entry.transition.reason
        if previous.startswith(("publishing:", "authority_unknown:")):
            effect_key = previous.split(":", 1)[1]
            if reason != "authority_unknown:" + effect_key:
                # 缺依赖等诊断不能覆盖尚无成功回执的发布尝试。
                return self.admissions.read(entry.key)
        if entry.transition.reason == reason:
            return self.admissions.read(entry.key)
        return self.admissions.advance(entry.key, expected_revision=entry.revision, now=now,
            transition=entry.transition.model_copy(update={"reason": reason, "room_head": None}))

    def _apply_audits(self, payload):
        from app.models.siming_event import SimingAuditRecord
        from app.models.siming_runtime_state import NarrativeReadModel, SimingCheckpoint
        writer = self.output_pipeline._audit_writer
        for item in payload["audits"]:
            audit = SimingAuditRecord.model_validate(item)
            previous = writer.get_record(audit.audit_id)
            if previous is not None and previous != audit:
                raise ValueError("siming_audit_conflict")
            if previous is None:
                writer.record(audit)
        for item in payload["checkpoints"]:
            writer.record_checkpoint(SimingCheckpoint.model_validate(item))
        if payload["read_model"] is not None:
            writer.record_read_model(NarrativeReadModel.model_validate(payload["read_model"]))

    @staticmethod
    def _graph_receipt(batch, payload):
        return {"transaction_id": batch.transaction_id, "idempotency_key": batch.idempotency_key,
            "batch_digest": digest(payload)}

    def _reconcile_only(self, entry, head, *, now, reason):
        if entry.state == "provider_pending":
            pending = SimingTurnFrame.model_validate_json(entry.transition.provider.frame_json)
            self.runtime.cancel_turn(pending.turn_id)
        receipts = {} if entry.transition is None else {item.effect_key: item for item in entry.transition.receipts}
        if entry.state == "commit_started":
            return self.admissions.reconcile_effect_receipts(entry.key, expected_revision=entry.revision,
                now=now, reason=reason,
                room_head=head.model_copy(update={"revision": head.revision + 1, "completed_sequence": entry.room_sequence}),
                read_existing=lambda effect: self._existing_effect_receipt(entry, effect))
        missing = [] if entry.transition is None else [effect.effect_key for effect in entry.transition.effects
            if effect.effect_key not in receipts]
        return self.admissions.advance(entry.key, expected_revision=entry.revision, now=now,
            transition=SimingAdmissionTransition(state="stale", reason=reason + ";missing_effects=" + ",".join(missing), receipts=list(receipts.values()),
                room_head=head.model_copy(update={"revision": head.revision + 1, "completed_sequence": entry.room_sequence})))

    def _existing_effect_receipt(self, entry, effect):
        if effect.kind in {"graph_batch", "dispatch_record"}:
            batch = HeavenlyGraphWriteBatch.model_validate(effect.payload)
            if self.graph.has_idempotency_key(scope=batch.scope, idempotency_key=batch.idempotency_key):
                # exact 原请求重提只能返回 replay；绝不以当前 revision 补造业务写。
                if not self.graph.write_batch(batch).replayed:
                    raise RuntimeError("siming_existing_receipt_not_replayed")
                return self._graph_receipt(batch, effect.payload)
        elif effect.kind == "character_delivery" and self.character_admissions is not None:
            child = self.character_admissions.read_delivery(
                dispatch_event=AuthorityEvent.model_validate(effect.payload["event"]),
                delivery_input=effect.payload["delivery"], effect_key=effect.effect_key, expires_at=entry.expires_at)
            if child is not None:
                return {"child_key": child.child_key, "input_digest": child.input_digest}
        return None

    def _invalidation(self, event):
        if self._invalidation_reader is None:
            raise ValueError("siming_invalidation_reader_required")
        reason = self._invalidation_reader(event.model_copy(deep=True))
        if reason not in {None, "branch_reset", "source_revoked", "authorization_revoked"}:
            raise ValueError("siming_invalidation_reason_invalid")
        return reason
