from pydantic import BaseModel, ConfigDict


class RuntimeCadencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    perception_interval_ms: int
    cognition_interval_ms: int
    degraded_mode: bool = False


class RuntimeWakeUpCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    wake_up_requested: bool = False
    continuity_priority: int = 0
    salience: float = 0.0
    last_active_ts: int = 0


class RuntimePopulationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_active_actors_per_tick: int
    wake_up_batch_size: int
    degraded_population_threshold: int
    prioritize_continuity_recovery: bool = True


def select_schedulable_actor_ids(
    *,
    candidates: list[RuntimeWakeUpCandidate],
    policy: RuntimePopulationPolicy,
    actor_population: int,
) -> list[str]:
    degraded_population = actor_population >= policy.degraded_population_threshold
    active_limit = (
        policy.wake_up_batch_size
        if degraded_population
        else policy.max_active_actors_per_tick
    )

    def _sort_key(candidate: RuntimeWakeUpCandidate) -> tuple[float | int | str, ...]:
        continuity_priority = (
            candidate.continuity_priority
            if policy.prioritize_continuity_recovery
            else 0
        )
        return (
            -continuity_priority,
            -int(candidate.wake_up_requested),
            -candidate.salience,
            candidate.last_active_ts,
            candidate.actor_id,
        )

    selected = sorted(candidates, key=_sort_key)[:active_limit]
    return [candidate.actor_id for candidate in selected]
