"""已提交未解决冲突可申请后台 B2 唤醒；项目事实不转成角色感知。"""
from dataclasses import asdict, dataclass
import hashlib
import json

from app.gameplay.organization_government_social_platform_runtime import (
    OGS_SOCIAL_PRINCIPAL_REF, SocialNormConflictIntent,
)
from app.population_continuity.models import ActivationDecision


POLICY = "population-conflict-wake:v1"
PINS = (
    ("package_revision_pin", "package_revision"), ("content_digest_pin", "content_digest"),
    ("declaration_ref_pin", "declaration_ref"), ("declaration_digest_pin", "declaration_digest"),
    ("descriptor_pin", "descriptor_ref"), ("descriptor_revision_pin", "descriptor_revision"),
    ("active_set_digest_pin", "active_patch_set_revision"),
)


@dataclass(frozen=True)
class PopulationConflictWake:
    candidate_key: str
    actor_id: str
    source_event_id: str
    source_transaction_id: str
    source_revision_vector: tuple[tuple[str, int], ...]
    authored_identity_digest: str
    activation_policy_revision: str
    wake_policy_revision: str = POLICY
    source_kind: str = "run_background_cognition_tick"

    @property
    def decision(self) -> ActivationDecision:
        # 唤醒只允许已有私有 snapshot 的认知；并不向 L1 注入 case/subjects/project payload。
        return ActivationDecision(actor_id=self.actor_id, state="active", reason="committed_social_conflict",
            requires_activation_lock=True, load_private_memory=True, policy_revision=self.activation_policy_revision)


def prepare_conflict_activation(*, store, package_registry, profiles, policy,
                                source_event_id: str, actor_id: str, budget: int) -> PopulationConflictWake:
    """Owner 只读准备；新 opened/appealed 事件等待下一真实 cadence，不虚构领域 due_tick。"""
    if not profiles.contains(actor_id):
        raise ValueError("unsupported_actor")
    if type(budget) is not int or budget <= 0:
        raise ValueError("activation_budget_exhausted")
    event = store.get_event(source_event_id)
    batch = store.get_transaction(event.transaction_id)
    if (batch is None or batch.idempotency_record.principal_ref != OGS_SOCIAL_PRINCIPAL_REF
            or event not in batch.events or event.global_sequence <= 0
            or event.event_type != "gameplay.social.norm_conflict_recorded@1" or event.visibility_policy != "project"):
        raise ValueError("conflict_owner_proof_invalid")
    # Owner 填入的 package pin 使用 registry 的原始版本格式，逐项核对实际 binding；
    # 业务字段仍经原 intent schema 校验，不能把输入 intent 的可选 pin 格式当作存档格式。
    intent = SocialNormConflictIntent.model_validate({key: value for key, value in event.payload.items()
        if key not in dict(PINS)})
    if event.stream_id != f"gameplay:social:case:{intent.case_ref}" or store.get_stream_head(event.stream_id) != event.stream_revision:
        raise ValueError("conflict_source_stale")
    if "character:" + actor_id not in intent.subject_refs:
        raise ValueError("actor_not_subject")
    if intent.conflict_state not in {"opened", "appealed"}:
        raise ValueError("conflict_not_actionable")
    active = package_registry.active_patch_set
    matches = () if active is None else tuple(binding for binding in active.capability_bindings
        if binding.family_ref == "social_norm_conflict@1" and binding.descriptor_ref == "descriptor:social-norm-conflict@1"
        and all(event.payload.get(name) == getattr(binding, field) for name, field in PINS))
    if len(matches) != 1:
        raise ValueError("conflict_package_stale")
    identity = profiles.authored_identity_digest(actor_id)
    digest = hashlib.sha256(json.dumps([POLICY, policy.policy_revision, event.event_id, event.stream_revision,
                                       actor_id, identity], separators=(",", ":")).encode()).hexdigest()
    return PopulationConflictWake(candidate_key="population-conflict:" + digest, actor_id=actor_id,
        source_event_id=event.event_id, source_transaction_id=event.transaction_id,
        source_revision_vector=((event.stream_id, event.stream_revision),), authored_identity_digest=identity,
        activation_policy_revision=policy.policy_revision)


@dataclass(frozen=True)
class PopulationConflictRead:
    wakes: tuple[PopulationConflictWake, ...]
    diagnostics: tuple[tuple[str, str], ...]
    cursor: int


class PopulationConflictSource:
    """只保留未接管的当前冲突；Character 原子入站后才移除对应角色候选。"""

    EVENT = "gameplay.social.norm_conflict_recorded@1"

    def __init__(self, *, store, world_ref, roster, package_registry, profiles, policy, admissions):
        from app.population_continuity.store_projection_assembler import _digest
        if not world_ref:
            raise ValueError("conflict_world_required")
        self._store, self._packages, self._profiles = store, package_registry, profiles
        self._policy, self._admissions = policy, admissions
        self._actors = tuple(sorted(actor for actor in roster.actor_ids if profiles.contains(actor)))
        self._context = dict(world_ref=world_ref, roster_digest=_digest(roster.actor_ids), wake_policy=POLICY,
            activation_policy=policy.policy_revision, identities={actor: profiles.authored_identity_digest(actor) for actor in self._actors})
        self.checkpoint_id = "checkpoint:population-conflict:" + _digest(self._context).split(":", 1)[1]

    def _owner_event(self, event):
        batch = self._store.get_transaction(event.transaction_id)
        return (batch is not None and batch.idempotency_record.principal_ref == OGS_SOCIAL_PRINCIPAL_REF
            and event in batch.events and event.global_sequence > 0 and event.stream_revision > 0
            and event.event_type == self.EVENT and event.visibility_policy == "project"
            and event.stream_id == "gameplay:social:case:" + str(event.payload.get("case_ref", "")))

    def _admitted(self, wake, event):
        key = self._admissions.key_for(source_event_id=event.event_id, actor_id=wake.actor_id, delivery_id=wake.candidate_key)
        receipt = self._admissions.read(key)
        if receipt is None:
            return False
        if (receipt.actor_id != wake.actor_id or receipt.delivery_id != wake.candidate_key
                or receipt.source_event != event.model_dump(mode="json") or receipt.source_kind != wake.source_kind
                or receipt.payload != {} or receipt.source_pins.get("population_wake") != json.loads(json.dumps(asdict(wake)))):
            raise ValueError("conflict_child_receipt_mismatch")
        # 原子 admitted 只证明子链已接管；认知完成、过期、失败继续由子链独立记账。
        return True

    def read(self) -> PopulationConflictRead:
        from app.gameplay.models import ProjectionCheckpoint
        from app.population_continuity.store_projection_assembler import _checkpoint_digest, _digest
        prior = self._store.get_projection_checkpoint(self.checkpoint_id)
        high_water = self._store.get_last_global_sequence()
        cursor, anchor, sources = 0, None, {}
        if prior is not None:
            if (prior.projector_id != "population-conflict-source" or prior.projector_version != "1"
                    or prior.projection_schema_version != 1 or prior.state.get("context") != self._context
                    or prior.projection_hash != _checkpoint_digest(prior)
                    or not 0 <= prior.last_global_sequence <= high_water):
                raise ValueError("conflict_source_checkpoint_invalid")
            cursor, anchor = prior.last_global_sequence, prior.state.get("anchor")
            if cursor:
                if not isinstance(anchor, dict):
                    raise ValueError("conflict_source_anchor_invalid")
                event = self._store.get_event(anchor["event_id"])
                if event.global_sequence != cursor or _digest(event.model_dump(mode="json")) != anchor.get("digest"):
                    raise ValueError("conflict_source_anchor_invalid")
            elif anchor is not None:
                raise ValueError("conflict_source_anchor_invalid")
            ids = prior.state.get("source_event_ids")
            if not isinstance(ids, list) or any(not isinstance(key, str) for key in ids) or len(set(ids)) != len(ids):
                raise ValueError("conflict_source_entries_invalid")
            for key in ids:
                event = self._store.get_event(key)
                if event.global_sequence > cursor or not self._owner_event(event) or event.stream_id in sources:
                    raise ValueError("conflict_source_entries_invalid")
                sources[event.stream_id] = event
            if prior.source_revision_vector != {stream: event.stream_revision for stream, event in sources.items()}:
                raise ValueError("conflict_source_vector_invalid")
        while cursor < high_water:
            page = self._store.read_events(event_type=self.EVENT, global_sequence_after=cursor, limit=256)
            if not page:
                break
            for event in page:
                if not cursor < event.global_sequence <= high_water:
                    raise ValueError("conflict_source_cursor_invalid")
                if self._owner_event(event):
                    sources[event.stream_id] = event
                cursor = event.global_sequence
        # 稀疏类型游标跳过其他领域，仅点读水位锚点，不能解码全部 B0 历史。
        if high_water:
            last = self._store.read_events(global_sequence_from=high_water, limit=1)
            if len(last) != 1 or last[0].global_sequence != high_water:
                raise ValueError("conflict_source_watermark_invalid")
            anchor = dict(event_id=last[0].event_id, digest=_digest(last[0].model_dump(mode="json")))
        cursor = high_water
        wakes, diagnostics, pending = [], [], []
        for event in sorted(sources.values(), key=lambda row: row.global_sequence):
            if event.payload.get("conflict_state") not in {"opened", "appealed"}:
                continue
            retain = False
            for actor in self._actors:
                if "character:" + actor not in event.payload.get("subject_refs", []):
                    continue
                try:
                    wake = prepare_conflict_activation(store=self._store, package_registry=self._packages,
                        profiles=self._profiles, policy=self._policy, source_event_id=event.event_id, actor_id=actor, budget=4)
                except ValueError as error:
                    reason = str(error)
                    reason = reason if reason in {"conflict_package_stale", "conflict_source_stale", "conflict_owner_proof_invalid"} else "conflict_source_invalid"
                    diagnostics.append((event.event_id + ":" + actor, reason))
                    retain = True
                    continue
                if not self._admitted(wake, event):
                    wakes.append(wake)
                    retain = True
            if retain:
                pending.append(event)
        checkpoint = ProjectionCheckpoint(checkpoint_id=self.checkpoint_id, projector_id="population-conflict-source",
            projector_version="1", projection_schema_version=1, last_global_sequence=cursor,
            source_revision_vector={event.stream_id: event.stream_revision for event in pending},
            state=dict(context=self._context, anchor=anchor, source_event_ids=[event.event_id for event in pending]), projection_hash="pending")
        checkpoint.projection_hash = _checkpoint_digest(checkpoint)
        if self._store.get_last_global_sequence() != high_water:
            raise ValueError("conflict_source_changed")
        if checkpoint != prior:
            self._store.save_projection_checkpoint(checkpoint)
        return PopulationConflictRead(tuple(wakes), tuple(diagnostics), cursor)
