"""Bounded canonical dispatch to the existing ESM object owner."""
from __future__ import annotations

import time
from threading import RLock
from uuid import uuid4

from app.models.player_input import InteractIntent


class CharacterObjectExecution:
    def __init__(self, *, runtime, owner, source, scopes, clock_ms=None, learning_world_ref=None,
                 combat_targets=None):
        self._runtime, self._owner, self._source = runtime, owner, source
        self._scopes = {scope.actor_id: scope for scope in scopes}
        self._clock_ms = clock_ms or (lambda: time.monotonic_ns() // 1_000_000)
        self._learning_world_ref = learning_world_ref
        self._combat_targets = combat_targets
        self._epoch = uuid4().hex
        self._lock = RLock()

    def _now(self):
        value = self._clock_ms()
        if type(value) is not int or value < 0:
            raise ValueError("execution_dispatch_clock_invalid")
        return value

    def offer(self, contract):
        """Called by backend egress only; ingress must never mint a lease."""
        return self._runtime.offer_execution_dispatch(contract,
            process_epoch=self._epoch, now_ms=self._now())

    def project_character_targets(self, snapshot):
        """Join owner eligibility with current admitted spatial evidence, read only."""
        descriptors = self._owner.project_character_targets(snapshot)
        authored = self._scopes.get(snapshot.actor_id)
        scope = {name: getattr(snapshot, name) for name in ("room_id", "scene_id", "zone_id")}
        evidence = None
        if authored is not None and all(getattr(authored, name) == value for name, value in scope.items()):
            try:
                evidence = self._source.read(actor_id=snapshot.actor_id, **scope,
                    scene_instance_id=authored.scene_instance_id, scene_revision=authored.scene_revision)
            except ValueError:
                # Source absence, expiry or revocation cannot become affirmative range evidence.
                pass
        for descriptor in descriptors:
            target = descriptor["target_ref"]
            range_status = "unknown"
            if evidence is not None and target in self._owner.OBJECT_POSITIONS:
                range_status = "satisfied" if self._owner._is_in_range(target, evidence.position) else "blocked"
                descriptor["source_refs"].append(f"spatial:{evidence.event_ref}")
            descriptor["required_conditions"] = dict(descriptor["required_conditions"], range=range_status)
        if self._combat_targets is not None:
            descriptors.extend(self._combat_targets.project_character_targets(snapshot))
        return descriptors

    def execute(self, contract):
        with self._lock:
            self._runtime.verify_recorded_execution_contract(contract)
            observation = contract.expected_observation
            scope = observation.get("execution_scope", {})
            target_refs = [ref.removeprefix("object:") for ref in contract.target_refs
                           if ref.startswith(("obj_", "object:"))]
            target = target_refs[0] if len(target_refs) == 1 and len(contract.target_refs) == 1 else ""
            intent_map = {"inspect_object": ("inspect", {"inspect", "action:inspect"}), "use_object": ("use", {"use", "action:use"}), "finish_use": ("finish_use", {"finish_use", "action:finish_use"})}
            interaction_type, actions = intent_map.get(contract.semantic_intent_id, ("", set()))
            allowed_targets = {"inspect_object": {"obj_plaque"},
                               "use_object": {"obj_worktable"},
                               "finish_use": {"obj_worktable"}}
            if (not interaction_type or contract.semantic_action_id not in actions or not target
                    or target not in allowed_targets.get(contract.semantic_intent_id, set())
                    or observation.get("owner_route") != "esm.interaction"
                    or not observation.get("candidate_id") or not observation.get("candidate_digest")
                    or set(scope) != {"room_id", "scene_id", "zone_id"}
                    or not all(isinstance(value, str) and value for value in scope.values())):
                raise ValueError("execution_object_route_or_pins_invalid")
            event = InteractIntent(player_id="character_agent", actor_id=contract.actor_id,
                room_id=scope["room_id"], scene_id=scope["scene_id"], zone_id=scope["zone_id"],
                producer_ts=contract.producer_ts, target_object_id=target, interaction_type=interaction_type,
                turn_id=contract.turn_id, execution_contract_ref=contract.idempotency_key)
            request = self._owner.build_action_request(event, source_system="character_agent_l4").model_copy(update={
                "request_id": f"{contract.idempotency_key}:0", "source": {
                    "layer": "L4", "system": "character_agent_l4", "actor_id": contract.actor_id},
                "causation_id": contract.causation_id, "correlation_id": contract.correlation_id,
                "expected_revision_vector": dict(contract.expected_revision_vector),
                "expected_memory_revision_vector": dict(contract.expected_memory_revision_vector),
                "expected_snapshot_revision": contract.expected_snapshot_revision,
            })
            prior = self._owner.find_object_settlement(event, action_request=request)
            if prior is None:
                self._runtime.verify_execution_dispatch(contract, process_epoch=self._epoch, now_ms=self._now())
                snapshot = self._runtime.get_private_snapshot(contract.actor_id)
                authored = self._scopes.get(contract.actor_id)
                if (snapshot is None or authored is None or snapshot.actor_id != contract.actor_id
                        or any(getattr(snapshot, name) != value or getattr(authored, name) != value
                               for name, value in scope.items())):
                    raise ValueError("execution_object_scope_mismatch")
                descriptors = self._owner.project_character_targets(snapshot)
                if not any(d["target_ref"] == target
                           and contract.semantic_intent_id in d["supported_intents"]
                           and d["target_admission_digest"] == observation.get("target_admission_digest")
                           and d["affordance_result"]["status"] == "available" for d in descriptors):
                    raise ValueError("execution_object_target_ineligible")
                evidence = self._source.read(actor_id=contract.actor_id, **dict(scope),
                    scene_instance_id=authored.scene_instance_id, scene_revision=authored.scene_revision)
                result, receipt = self._owner.settle_object_interaction(event, action_request=request,
                    actor_position=evidence.position, read_stream_revisions=evidence.read_stream_revisions)
            else:
                result, receipt = prior
            if receipt is not None and receipt.committed and result.settlement_status == "committed":
                if self._learning_world_ref is not None:
                    disclosed = self._owner.publish_learning_disclosure(event, action_request=request,
                        world_ref=self._learning_world_ref, receipt=receipt)
                    if not disclosed.committed:
                        raise ValueError("execution_learning_disclosure_commit_failed")
                self._runtime.record_settlement_result(actor_id=contract.actor_id,
                    producer_ts=result.producer_ts, payload=result.model_dump(exclude_none=True))
            return event, request, result, receipt
