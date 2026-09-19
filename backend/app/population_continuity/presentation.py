"""已确认人口状态的公开表现视图；布局坐标不代表权威空间位置。"""

from hashlib import sha256
import json
from dataclasses import dataclass
from typing import Callable

from app.gameplay.godot_mirror_delivery import (
    GameplayGodotProjectionPublisher, GameplayGodotProjectionRefreshResult,
    GameplayMirrorAfterCommitDelivery, GameplayMirrorSubscriptionRegistry,
)
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import CharacterGameRuntimeStateView, StateGroupConsumerViewPolicy, StateGroupViewProjector, combine_godot_views
from app.population_continuity.recovery import parse_population_checkpoint
from app.population_continuity.world import WorldContinuityRuntime


_FIELDS = ("actor_id", "confirmed_tick", "presentation_position", "animation_tag", "public_digest")
_ANIMATIONS = {"rest": "rest", "routine": "idle", "routine_work": "work", "leisure": "idle"}
_REGISTRY = StateGroupRegistry()
_REGISTRY.register(StateGroupDefinition(group_id="population_public", definition_version="1", projection_schema_version=1))
_BUILDER = CharacterGameRuntimeStateBuilder(_REGISTRY)
_PROJECTOR = StateGroupViewProjector([
    StateGroupConsumerViewPolicy(group_id="population_public", godot_allowed_fields=_FIELDS),
])


def build_population_actor_view(world: WorldContinuityRuntime, *, actor_id: str) -> CharacterGameRuntimeStateView:
    """逐 actor 授权由现有 session 层执行；这里只生成固定公开字段。"""
    if actor_id not in world.roster.actor_ids:
        raise ValueError("population_actor_unknown")
    return _build_population_actor_view(world, actor_id, _confirmed_population_state(world))


def _confirmed_population_state(world: WorldContinuityRuntime):
    receipt = world.latest_confirmation
    if receipt is None:
        return None
    checkpoint = world.store.get_projection_checkpoint(
        f"population-receipt:{world.mode.world_ref}:{receipt.cadence_id}",
    )
    if checkpoint is None:
        raise ValueError("population_presentation_unconfirmed")
    confirmed = parse_population_checkpoint(world, checkpoint)
    if confirmed.receipt != receipt:
        raise ValueError("population_presentation_unconfirmed")
    return confirmed


def _build_population_actor_view(world: WorldContinuityRuntime, actor_id: str, confirmed) -> CharacterGameRuntimeStateView:
    """仅在已授权actor及当前owner批次验证过的确认点上构建公开字段。"""
    tick, animation, revisions = 0, "idle", {}
    if confirmed is not None:
        receipt = confirmed.receipt
        row = world.population_hot_state.read(actor_id)
        if row["last_update_tick"] != receipt.window_end:
            raise ValueError("population_presentation_unconfirmed")
        # 此字段已由 cadence 的 public presentation_seed 明确公开；恢复后沿用同一确认值。
        # 不使用 fatigue、need、memory 或热表私有 revision 推导表现。
        animation = _ANIMATIONS.get(str(row["activity_phase"]), "idle")
        tick = receipt.window_end
        revisions = {f"population-cadence:{world.mode.world_ref}": confirmed.cadence_stream_revision}
    identity = sha256(actor_id.encode("utf-8")).digest()
    position = [round(int.from_bytes(identity[:4], "big") / 0xFFFFFFFF * 36 - 18, 5), 0.0,
                round(int.from_bytes(identity[4:8], "big") / 0xFFFFFFFF * 24 - 12, 5)]
    payload = dict(actor_id=actor_id, confirmed_tick=tick, presentation_position=position, animation_tag=animation)
    payload["public_digest"] = "sha256:" + sha256(json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    state = _BUILDER.build(
        actor_ref=f"character:{actor_id}", enabled_group_ids=("population_public",),
        group_payloads={"population_public": payload}, source_revision_vector=revisions,
        registry_revision="population_public:1", world_config_revision=world.mode.revision,
        active_patch_set_revision="population_public:1",
    )
    return _PROJECTOR.godot_view(state, allowed_group_ids=("population_public",))


@dataclass(frozen=True)
class _PopulationActorSource:
    mirror: "PopulationMirrorSource"
    actor_id: str
    base_source: Callable[[], CharacterGameRuntimeStateView] | None

    def __call__(self) -> CharacterGameRuntimeStateView:
        population = (build_population_actor_view(self.mirror.world, actor_id=self.actor_id)
                      if self.mirror._batch_confirmation is None else
                      _build_population_actor_view(self.mirror.world, self.actor_id, self.mirror._batch_confirmation))
        return population if self.base_source is None else combine_godot_views(self.base_source(), population)


class PopulationMirrorSource:
    """同一world的轻量来源注册与确认后有界fanout；不参与B0选择。"""

    def __init__(self, *, world: WorldContinuityRuntime, publisher: GameplayGodotProjectionPublisher,
                 registry: GameplayMirrorSubscriptionRegistry, delivery: GameplayMirrorAfterCommitDelivery) -> None:
        self.world, self.publisher, self.registry, self.delivery = world, publisher, registry, delivery
        self.actor_refs = frozenset(f"character:{actor}" for actor in world.roster.actor_ids)
        self.last_receipt_key = None
        self.last_refresh = GameplayGodotProjectionRefreshResult((), ())
        self.last_delivery = None
        self.last_error: str | None = None
        self._batch_confirmation = None
        registry.configure_population_actor_refs(self.actor_refs)
        for actor in world.roster.actor_ids:
            actor_ref = f"character:{actor}"
            base = publisher.actor_source(actor_ref=actor_ref)
            if isinstance(base, _PopulationActorSource):
                base = base.base_source
            publisher.register_actor_source(actor_ref=actor_ref, source=_PopulationActorSource(self, actor, base))

    def refresh_confirmed(self) -> None:
        receipt = self.world.latest_confirmation
        if receipt is None or self.last_receipt_key == (receipt.cadence_id, receipt.window_end):
            return
        confirmed = _confirmed_population_state(self.world)
        published, unavailable = [], []
        self._batch_confirmation = confirmed
        try:
            for actor_ref in sorted(self.actor_refs.intersection(self.registry.subscribed_actor_refs())):
                try:
                    self.publisher.refresh_actor(actor_ref=actor_ref)
                except Exception:
                    unavailable.append(actor_ref)
                else:
                    published.append(actor_ref)
        finally:
            # owner单命令内复用；异常、新订阅、显式snapshot都不能借用上次可信结果。
            self._batch_confirmation = None
        # 只保留最新诊断与去重切点；表现失败不重放已确认authority窗口。
        self.last_refresh = GameplayGodotProjectionRefreshResult(tuple(published), tuple(unavailable))
        self.last_error = None
        self.last_receipt_key = (receipt.cadence_id, receipt.window_end)
        self.last_delivery = self.delivery.deliver_for_committed_actor_refs(affected_actor_refs=published)
