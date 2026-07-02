from __future__ import annotations

from app.models.raw_fact import RawFactEvent, RawFactObservability, RawFactSource, RawFactTargets, RawFactWorld
from app.world_runtime.l1_occupancy import SpatialOccupancySnapshot


class FactProjectionLayer:
    """Projects L1 foundation state into existing raw_fact_event shape."""

    def __init__(self) -> None:
        self._los_blocked: set[tuple[str, str]] = set()
        self._affordance_state: dict[str, tuple[str, ...]] = {}

    def project_actor_target_facts(
        self,
        occupancy: SpatialOccupancySnapshot,
        *,
        actor_id: str,
        producer_ts: int,
        target_actor_id: str = "",
        target_object_id: str = "",
    ) -> list[RawFactEvent]:
        zone_id = self._zone_for_actor(occupancy, actor_id)
        target_ref = target_actor_id or target_object_id
        if zone_id == "":
            zone_id = sorted(occupancy.zone_states.keys())[0] if occupancy.zone_states else "zone_focus"
        facts: list[RawFactEvent] = []
        zone = occupancy.zone_states.get(zone_id)
        target_exists = self._target_exists(occupancy, target_actor_id=target_actor_id, target_object_id=target_object_id)
        if target_ref and not target_exists:
            facts.append(
                self._fact(
                    "expected_target_missing",
                    actor_id=actor_id,
                    zone_id=zone_id,
                    producer_ts=producer_ts,
                    target_actor_id=target_actor_id,
                    target_object_id=target_object_id,
                    relation_type="negative_world_fact",
                    state_after=target_ref,
                    occluded=False,
                )
            )

        key = (actor_id, target_ref)
        blocked = bool(zone and zone.visibility in {"reduced", "blocked"})
        if target_object_id:
            object_state = occupancy.object_states.get(target_object_id)
            blocked = blocked or bool(object_state and object_state.occludes)

        if blocked:
            self._los_blocked.add(key)
            facts.append(
                self._fact(
                    "line_of_sight_blocked",
                    actor_id=actor_id,
                    zone_id=zone_id,
                    producer_ts=producer_ts,
                    target_actor_id=target_actor_id,
                    target_object_id=target_object_id,
                    relation_type="line_of_sight",
                    occluded=True,
                    state_after="blocked",
                )
            )
        elif key in self._los_blocked:
            self._los_blocked.remove(key)
            facts.append(
                self._fact(
                    "line_of_sight_restored",
                    actor_id=actor_id,
                    zone_id=zone_id,
                    producer_ts=producer_ts,
                    target_actor_id=target_actor_id,
                    target_object_id=target_object_id,
                    relation_type="line_of_sight",
                    state_after="clear",
                    occluded=False,
                )
            )

        if zone and zone.passability in {"blocked", "requires_detour"}:
            facts.append(
                self._fact(
                    "target_unreachable",
                    actor_id=actor_id,
                    zone_id=zone_id,
                    producer_ts=producer_ts,
                    target_actor_id=target_actor_id,
                    target_object_id=target_object_id,
                    relation_type="reachability",
                    state_after=zone.passability,
                    occluded=blocked,
                )
            )

        if target_object_id and target_object_id in occupancy.object_states:
            object_state = occupancy.object_states[target_object_id]
            next_affordances = tuple(object_state.affordances)
            if self._affordance_state.get(target_object_id) != next_affordances:
                self._affordance_state[target_object_id] = next_affordances
                facts.append(
                    self._fact(
                        "interaction_affordance_changed",
                        actor_id=actor_id,
                        zone_id=object_state.zone_id,
                        producer_ts=producer_ts,
                        target_actor_id=target_actor_id,
                        target_object_id=target_object_id,
                        relation_type="affordance",
                        state_after=",".join(next_affordances),
                        occluded=object_state.occludes,
                    )
                )

        return facts

    def _fact(
        self,
        fact_type: str,
        *,
        actor_id: str,
        zone_id: str,
        producer_ts: int,
        target_actor_id: str,
        target_object_id: str,
        relation_type: str,
        state_after: str,
        occluded: bool,
    ) -> RawFactEvent:
        return RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type=fact_type,
            relation_type=relation_type,
            producer_ts=producer_ts,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id=zone_id,
            source=RawFactSource(layer="L1", system="world_runtime.l1_fact_projection", actor_id=actor_id),
            targets=RawFactTargets(actor_id=target_actor_id, object_id=target_object_id),
            world=RawFactWorld(state_after=state_after),
            observability=RawFactObservability(visual=True, occluded=occluded),
            effect_kind="pulse",
            subject_key=fact_type,
            causation_id=f"l1_projection:{actor_id}:{producer_ts}",
            correlation_id=f"l1_projection:{actor_id}:{producer_ts}",
        )

    @staticmethod
    def _zone_for_actor(occupancy: SpatialOccupancySnapshot, actor_id: str) -> str:
        for zone_id, zone in occupancy.zone_states.items():
            if actor_id in zone.actor_ids:
                return zone_id
        return ""

    @staticmethod
    def _target_exists(
        occupancy: SpatialOccupancySnapshot,
        *,
        target_actor_id: str,
        target_object_id: str,
    ) -> bool:
        if target_actor_id:
            return any(target_actor_id in zone.actor_ids for zone in occupancy.zone_states.values())
        if target_object_id:
            return target_object_id in occupancy.object_states or any(
                target_object_id in zone.object_ids for zone in occupancy.zone_states.values()
            )
        return True
